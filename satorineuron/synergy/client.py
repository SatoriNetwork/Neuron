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
    def __init__(
        self,
        url: str = None,
        *args, **kwargs
    ):
        super(SynergyRestClient, self).__init__(*args, **kwargs)
        self.url = url or 'https://satorinet.io:24602'

    def getChallenge(self):
        return requests.get(self.url + '/challenge').text


class SynergyClient:
    def __init__(self, url, wallet: Wallet, router: callable = None, onConnected: callable = None):
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
            logging.error('Failed to connect to server: %s', e)
            time.sleep(30)
            self.reconnect()

    def send(self, payload):
        if self.connected.is_set():
            try:
                self.sio.emit('message', payload)
            except Exception as e:
                logging.error('Failed to send message: %s', e)
                self.reconnect()
        else:
            logging.warning('Connection not established. Message not sent.')

    def ping(self, payload):
        if self.connected.is_set():
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
        logging.info('Disconnected...')
        self.sio.disconnect()

    def reconnect(self):
        logging.info('Attempting to reconnect...')
        self.connect()

    def runForever(self):
        # Initiates the connection and enters the event loop
        self.connect()
        try:
            self.sio.wait()
        except KeyboardInterrupt:
            self.disconnect()
            logging.info('Disconnected by user')
        except Exception as e:
            logging.error('Satori Synergy error:', e, print=True)
            self.disconnect()
            self.reconnect()
