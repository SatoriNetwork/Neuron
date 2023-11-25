from flask import Flask, Response, stream_with_context
import time

app = Flask(__name__)


def event_stream():
    count = 0
    while True:
        time.sleep(1)
        count += 1
        yield f"data: {count}\n\n"


@app.route('/stream')
def stream():
    return Response(
        stream_with_context(event_stream()),
        content_type='text/event-stream')


if __name__ == '__main__':
    app.run('0.0.0.0', port=24604, debug=True)
