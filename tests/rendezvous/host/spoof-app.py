import secrets
import random
import webbrowser
import time
from flask import Flask, jsonify
from flask import request
from flask import Response, stream_with_context
from satorineuron import config

###############################################################################
## Globals ####################################################################
###############################################################################


# development flags
debug = True
darkmode = False
badForm = {}
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
updating = False


@app.route('/udp/ports', methods=['GET'])
def udpPorts():
    ''' recieves data from udp relay '''
    return str({
        5001: [('165.232.81.173', 5000)],
        # 3: [('ip4', 4), ('ip5', 5)],
        # 6: [('ip7', 7), ('ip8', 8)],
    })


@app.route('/udp/stream')
def udpStream():

    def event_stream():
        '''
        here we gather all the messages from the rendezvous object
        it will be a list of tuples (address, message)
        then we have to organize it into a dictionary for the udp relay
        then make it a string. will be interpretted this way:
        literal: dict[str, object] = ast.literal_eval(message)
        data = literal.get('data', None)
        localPort = literal.get('localPort', None)
        '''
        while True:
            time.sleep(1)
            messages = random.choice(
                [b'a', b'b', b'c', [b'1', b'2', b'3'], [], [(5001, '165.232.81.173', 5000, b'message for you')]])
            if len(messages) > 0:
                yield 'data:' + str(messages) + '\n'
            yield '\n'

    return Response(
        stream_with_context(event_stream()),
        content_type='text/event-stream')


@app.route('/udp/message', methods=['POST'])
def udpMessage():
    ''' recieves data from udp relay '''
    payload = request.json
    data = payload.get('data', None)
    localPort = payload.get('address', {}).get('local', {}).get('port', None)
    remoteIp = payload.get('address', {}).get('remote', {}).get('ip', None)
    remotePort = payload.get('address', {}).get('remote', {}).get('port', None)
    if any(v is None for v in [localPort, remoteIp, remotePort, data]):
        return 'fail'
    # start.peer.passMessage(localPort, remoteIp, remotePort, message=data)
    print('localPort:', localPort, 'remoteIp:', remoteIp,
          'remotePort:', remotePort, 'data:', data, )
    return 'ok'


###############################################################################
## Entry ######################################################################
###############################################################################


if __name__ == '__main__':
    # if False:
    #    spoofStreamer()

    # serve(app, host='0.0.0.0', port=config.get()['port'])
    if not debug:
        webbrowser.open('http://127.0.0.1:24601', new=0, autoraise=True)
    app.run(
        host='0.0.0.0',
        port=config.flaskPort(),
        threaded=True,
        debug=debug,
        use_reloader=False)
