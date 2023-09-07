''' manages our websocket connection to the server '''
from time import sleep
import threading 
import websocket


class ClientConnection(object):
    def __init__(self, timeout=5, url='ws://localhost:8000', payload=None):
        self.received = None
        self.sent = None
        self.thread = None
        self.timeout = timeout
        self.url = url
        self.payload = payload
        self.establishConnection()
        
    def onMessage(self, ws, message):
        ''' send message to flask or correct actor '''
        self.received = message
        print(f'message:{message}')

    def onError(self, ws, error):
        ''' send message to flask to re-establish connection '''
        print(error)
        # exit thread

    def onClose(self, ws, close_status_code, close_msg):
        ''' send message to flask to re-establish connection '''
        print('### closed ###')
        # exit thread

    def onOpen(self, ws):
        print('Opened connection')
        self.send(self.payload)

    def send(self, message: str):
        self.sent = message
        self.ws.send(message)

    def establishConnection(self):
        #websocket.enableTrace(True)
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.onOpen,
            on_message=self.onMessage,
            on_error=self.onError,
            on_close=self.onClose)
        self.thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.thread.start()
        while (self.ws.sock == None or not self.ws.sock.connected) and self.timeout:
            sleep(1)
            self.timeout -= 1