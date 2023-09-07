import websocket
from threading import Thread
import time
import sys


def on_message(ws, message):
    print('on_message')
    #ws.on_message = on_message2
    print(message)


def on_message2(ws, message):
    print('on_message2')
    ws.on_message = on_message
    print(message)


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    def run(*args):
        for i in range(3):
            # send the message, then wait
            # so thread doesn't exit and socket
            # isn't closed
            ws.on_message = on_message2
            ws.send("Hello %d" % i)
            time.sleep(5)

        time.sleep(1)
        ws.close()
        print("Thread terminating...")

    Thread(target=run).start()


if __name__ == "__main__":
    websocket.enableTrace(True)
    if len(sys.argv) < 2:
        host = "ws://localhost:8000/"
    else:
        host = sys.argv[1]
    ws = websocket.WebSocketApp(
        host,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close)
    ws.run_forever()
