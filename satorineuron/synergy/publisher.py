'''
publishers of datastreams connect to the synergy server through socketio 
connections 
'''
# pip install python-socketio[client]
import socketio
import time
import logging
import threading


class SynergyClient:
    def __init__(self, url, uid):
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=5,
            reconnection_delay=5)
        self.url = url
        self.uid = uid
        self.connect_event = threading.Event()
        self.setup_handlers()

    def setup_handlers(self):
        @self.sio.event
        def connect():
            self.on_connect()

        @self.sio.event
        def disconnect():
            self.on_disconnect()

        @self.sio.on('response')
        def on_message(data):
            self.router(data)

    def on_connect(self):
        print('connection established')
        self.connect_event.set()

    def on_disconnect(self):
        print('disconnected from server')
        self.connect_event.clear()

    def router(self, data):
        # Placeholder for message routing logic
        print('Routing message:', data)

    def connect(self):
        try:
            self.sio.connect(f'{self.url}?uid={self.uid}')
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
    client = SynergyClient(url='http://localhost:3300', uid='user123')
    # client.run_forever()

    # Run the client in a separate thread
    client_thread = threading.Thread(target=client.run_forever)
    client_thread.start()

    # Wait for the connection to be established
    time.sleep(5)  # Adjust this based on how quickly your client connects

    # Send a message
    client.send("Hello, World!")

    # Keep the main thread alive to maintain the client connection
    # You can use a more sophisticated condition for running here based on your application's needs
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        client.disconnect()
        print('Disconnected by user')
