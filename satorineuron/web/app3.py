from flask import Flask
from flask_sockets import Sockets

app = Flask(__name__)
sockets = Sockets(app)


@app.route('/ping/', methods=['GET'])
def ping():
    from datetime import datetime
    return str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@sockets.route('/websocket')
def handle_websocket(ws):
    while not ws.closed:
        message = ws.receive()
        print('Received message:', message)
        ws.send('Response message')


@sockets.route('/listen')
def handle_listen(ws):
    while not ws.closed:
        message = ws.receive()
        print('Received message:', message)
        ws.send('Response message')


@sockets.route('/speak')
def handle_speak(ws):
    import time
    while not ws.closed:
        print('speaking')
        ws.send('speaking')
        time.sleep(10)


if __name__ == '__main__':
    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler

    server = pywsgi.WSGIServer(
        ('127.0.0.1', 24603), app, handler_class=WebSocketHandler)
    server.serve_forever()
