'''publishers of datastreams connect to the synergy server through socketio'''
# pip install python-socketio[client]
import json
import time
import requests
import socketio
import threading
from urllib.parse import quote_plus
from satorilib import logging
from satorilib.api.wallet import Wallet
from satorilib.api.wallet import RavencoinWallet
from satorineuron import config
from satorilib.synergy import SynergyProtocol


class SynergyRestClient(object):
    def __init__(
        self,
        url: str = None,
        *args, **kwargs
    ):
        super(SynergyRestClient, self).__init__(*args, **kwargs)
        self.url = url or 'https://satorinet.io:3300'

    def getChallenge(self):
        print(self.url + '/challenge')
        return requests.get(self.url + '/challenge').text


class SynergyClient:
    def __init__(self, url, wallet: Wallet, router: callable = None):
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=5)
        self.url = url
        self.router = router or SynergyClient.defaultRouter
        self.wallet = wallet
        self.pubkey = wallet.publicKey
        self.connect_event = threading.Event()
        self.setup_handlers()

    def setup_handlers(self):
        @self.sio.event
        def connect():
            self.onConnect()

        @self.sio.event
        def disconnect():
            self.onDisconnect()

        @self.sio.on('error')
        def onError(data):
            logging.error('synergy error:', data, color='red')

        @self.sio.on('response')
        def onResponse(data):
            print('synergy response:', data)

        @self.sio.on('message')
        def onMessage(data):
            try:
                msg = SynergyProtocol.fromJson(data)
                self.router(msg)
            except Exception as e:
                logging.error('error parsing synergy message:',
                              data, e, color='red')

    def onConnect(self):
        print('connection established')
        self.connect_event.set()

    def onDisconnect(self):
        print('disconnected from server')
        self.connect_event.clear()

    @staticmethod
    def defaultRouter(msg: SynergyProtocol):
        print('Routing message:', msg)

    def connect(self):
        '''connect to the server with a challenge and signature'''
        challenge = SynergyRestClient(url=self.url).getChallenge()
        print('challenge:', challenge)
        signature = self.wallet.authPayload(
            challenge=challenge,
            asDict=True)['signature']
        try:
            # Construct the connection URL with additional query parameters
            connection_url = (
                f'{self.url}?pubkey={quote_plus(self.pubkey)}'
                f'&challenge={quote_plus(challenge)}'
                f'&signature={quote_plus(signature)}')
            self.sio.connect(connection_url)
        except socketio.exceptions.ConnectionError as e:
            logging.error('Failed to connect to server: %s', e)
            time.sleep(30)
            self.reconnect()

    def send(self, payload):
        if self.connect_event.is_set():
            try:
                self.sio.emit('message', payload)
            except Exception as e:
                logging.error('Failed to send message: %s', e)
                self.reconnect()
        else:
            logging.warning('Connection not established. Message not sent.')

    def ping(self, payload):
        if self.connect_event.is_set():
            try:
                self.sio.emit('ping', payload)
            except Exception as e:
                logging.error('Failed to send message: %s', e)
                self.reconnect()
        else:
            logging.warning('Connection not established. Message not sent.')

    def listen(self):
        # Handled by the socketio.Client() event loop
        pass

    def disconnect(self):
        self.sio.disconnect()

    def reconnect(self):
        logging.info('Attempting to reconnect...')
        self.connect()

    def run_forever(self):
        # Initiates the connection and enters the event loop
        self.connect()
        try:
            self.sio.wait()
        except KeyboardInterrupt:
            self.disconnect()
            print('Disconnected by user')


if __name__ == "__main__":
    client = SynergyClient(
        url='http://localhost:3300',
        wallet=RavencoinWallet(
            config.walletPath('wallet.yaml'),
            reserve=0.01,
            isTestnet=True)())
    # client.run_forever()

    # Run the client in a separate thread
    client_thread = threading.Thread(target=client.run_forever)
    client_thread.start()

    # Wait for the connection to be established
    time.sleep(30)  # Adjust this based on how quickly your client connects

    # Send a message
    client.ping("Hello, World!")

    # Keep the main thread alive to maintain the client connection
    # You can use a more sophisticated condition for running here based on your application's needs
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.disconnect()
        print('Disconnected by user')
