import websocket
import threading
import time


def on_message(ws, message):
    print("Received message from server:", message)


def on_error(ws, error):
    print("Error:", error)


def on_close(ws, close_status_code, close_msg):
    print("Connection closed")


def on_open(ws):
    def run(*args):
        for i in range(3):
            time.sleep(1)
            message = f"Message {i}"
            print("Sending message:", message)
            ws.send(message)
        time.sleep(1)
        ws.close()
    threading.Thread(target=run).start()


if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp("ws://127.0.0.1:24603/websocket",
                                on_open=on_open,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
    ws.run_forever()
