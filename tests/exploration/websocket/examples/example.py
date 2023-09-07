import websocket
import time
try:
    import thread
except ImportError:
    import _thread as thread

f = open("webSocketTester.log", "a")

def on_message(ws, message):
    print(message)
    f.write(message + "\n")
    f.flush()

def on_error(ws, error):
    print(error)

def on_close(ws, close_status_code, close_msg):
    print("### closed ###")

def on_open(ws):
    def run(*args):
        ws.send('{"userKey":"USER_KEY", "symbol" :"GBPUSD"}')
    thread.start_new_thread(run, ())

if __name__ == "__main__":
    ws = websocket.WebSocketApp("wss://marketdata.tradermade.com/feedadv",
                              on_message = on_message,
                              on_error = on_error,
                              on_close = on_close)
    ws.on_open = on_open
    ws.run_forever()