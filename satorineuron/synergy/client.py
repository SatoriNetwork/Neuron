''' connects to the synergy server through socketio '''

import time
import requests
import socketio
import threading
from urllib.parse import quote_plus
from satorilib import logging
from satorilib.api.wallet import Wallet
from satorilib.synergy import SynergyProtocol


class SynergyRestClient(object):
    def __init__(self, url, *args, **kwargs):
        self.url = url

    def getChallenge(self):
        return requests.get(self.url + '/challenge').text


# TODO: this seems to have some kind of silent failure after it's been
# connected for a while. don't know if it's the server or the client, or even
# if it's just a problem with the synapse. so we need to troubleshoot this, if
# it's the client we could increase hte reconnection_attempts - perhaps it runs
# out of reconnection attempts after 10 minutes or so. Or we could add a heart
# beat, but the server is supposed to heart beat the client every 25 seconds
# anyway. Or we could explicitly reconnect to the server every 10 minutes or so.
# we already added a reconnect call after .wait(), and I don't think that solved
# the problem, though I didn't get any error on this end anymore (was getting
# the empty packet queue error before). Perhaps it was solved on this end but
# another problem still exists on the synapse? that is one explanation. so we
# need to print out more logs about whats going on exactly.

class SynergyClient:
    def __init__(
        self,
        url,
        wallet: Wallet,
        router: callable = None,
        onConnected: callable = None
    ):
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=5)
        self.url = url
        self.router = router or SynergyClient.defaultRouter
        self.wallet = wallet
        self.pubkey = wallet.publicKey
        self.connected = threading.Event()
        self.onConnected = onConnected
        self.setupHandlers()
        print('synergy client end...')

    def setupHandlers(self):
        @self.sio.event
        def connect():
            self.onConnect()

        @self.sio.event
        def disconnect():
            self.onDisconnect()

        @self.sio.on('error')
        def onError(data):
            logging.info('synergy error:', data)

        @self.sio.on('response')
        def onResponse(data):
            logging.info('synergy response:', data)

        @self.sio.on('message')
        def onMessage(data):
            message = data.get('message')
            try:
                msg = SynergyProtocol.fromJson(message)
                self.router(msg)
            except Exception as e:
                logging.error('error parsing synergy message:',
                              message, e, color='red')

    @property
    def isConnected(self) -> bool:
        return self.connected.isSet()

    def onConnect(self):
        logging.info('connection established')
        self.connected.set()
        if self.onConnected:
            self.onConnected()

    def onDisconnect(self):
        logging.info('disconnected from server')
        self.connected.clear()

    @staticmethod
    def defaultRouter(msg: SynergyProtocol):
        logging.info('Routing message:', msg)

    def connect(self):
        '''connect to the server with a challenge and signature'''
        challenge = SynergyRestClient(url=self.url).getChallenge()
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
            logging.error('Failed to connect to Synergy.', e)
            # self.reconnect()

    def send(self, payload):
        if self.connected.is_set():
            try:
                self.sio.emit('message', payload)
            except Exception as e:
                logging.error('Failed to send message.', e)
                # self.reconnect()
        else:
            logging.warning(
                'Connection to Synergy not established. Message not sent.')

    def ping(self, payload):
        if self.connected.is_set():
            try:
                self.sio.emit('ping', payload)
            except Exception as e:
                logging.error('Failed to send message.', e)
                # self.reconnect()
        else:
            logging.warning('Connection not established. Message not sent.')

    def listen(self):
        # Handled by the socketio.Client() event loop
        pass

    def disconnect(self):
        logging.info('Disconnected...')
        self.sio.disconnect()

    def reconnect(self):
        logging.info('Attempting to reconnect...')
        time.sleep(30)
        self.connect()

    def runForever(self):
        # Initiates the connection and enters the event loop
        while True:
            self.connect()
            try:
                self.sio.wait()
            except KeyboardInterrupt:
                self.disconnect()
                logging.info('Disconnected by user')
                break
            except Exception as e:
                logging.error('Satori Synergy error:', e, print=True)
                self.disconnect()
                logging.info('Attempting to reconnect...')
        time.sleep(30)
