'''
creating a custom design for the synergy server allows us to avoid issues 
stemming from broadcast messages, even guaranteeing identity between clients.

in this case the publisher of a datastream maintains a persistent websocket
connection and listens for incoming data from the client. the client can make a
request through rest api and check back for a response a few seconds later.

TODO: 
DONE use wss and https for secure connections on special ports.
DONE simplify
login logic to verify pubkey of both publisher and subscriber: pull from server

'''
import json
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from satorilib import logging
from satorineuron.synergy.protocol.server import SynergyProtocol

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)

sessionByClient = {
    # 'pubkey': Socket.IO session IDs (request.sid)
}


@app.route('/api/data', methods=['GET', 'POST'])
def handle_data():
    if request.method == 'POST':
        data = request.json
        return jsonify({'received': data}), 201
    else:  # GET
        return jsonify({'data': 'Sample data'})

# I've decided both publisher and subscribers can connect to the server via
# websocket, the subscribers will just disconnect after they've received the
# data they need. This way, we don't need to make a separate mailbox for the
# subscribers. But we do need them to authenticate, proving their pubkey, so no
# one can just claim to be them. or they could just use a random uid...
# everyone who publishes data will always be here. so perhaps they should all be
# persistent connections. Yes that's best. but we need to map their pubkey to
# all their published datastreams. this way subscribers can send the request
# to the datastream and the message will be routed to the correct publisher.
# @app.route('/msg4user', methods=['POST'])
# def msg4user():
#    data = request.json
#    pubkey = data.get('pubkey')
#    msg = data.get('msg')
#    # Check if the user is connected and has a session
#    if pubkey in sessionByClient:
#        emit('response', {'data': msg}, room=sessionByClient[pubkey])
#        return jsonify({'relayed': True, 'to': pubkey}), 200
#    else:
#        return jsonify({'error': 'User not connected'}), 404


@socketio.on('connect')
def handleConnect():
    '''Expect the client to send their pubkey upon connection'''
    pubkey = request.args.get('pubkey')
    if pubkey:
        sessionByClient[pubkey] = request.sid
        join_room(request.sid)
        emit('response', {'data': f'{pubkey} connected.'})
    else:
        emit('error', {'data': 'provide valid pubkey.'})
        disconnect()


@socketio.on('disconnect')
def handleDisconnect():
    '''find which pubkey is associated with the disconnecting SID and remove it'''
    pubkeyToRemove = [
        pubkey for pubkey, sid in sessionByClient.items() if sid == request.sid]
    if pubkeyToRemove:
        del sessionByClient[pubkeyToRemove[0]]
        leave_room(request.sid)


@socketio.on('message')
def handleMessage(message):
    print('handleMessage:', message)
    try:
        msg = SynergyProtocol.fromJson(json.loads(message))
    except Exception as e:
        logging.error(e)
        emit('error', {'relayed': False, 'error': 'Invalid message format'})
        return
    if msg.subscriberIp is None:
        msg.subscriberIp = request.remote_addr
        if msg.author in sessionByClient:
            emit(
                'response',
                {'message': msg.toJson()},
                room=sessionByClient[msg.author])
            emit('response', {'relayed': True}), 200
    elif msg.authorPort is None:
        emit('error', {'relayed': False, 'error': 'author port?'}), 404
    elif msg.authorIp is None:
        msg.authorIp = request.remote_addr
        if msg.subscriber in sessionByClient:
            emit(
                'response',
                {'message': msg.toJson()},
                room=sessionByClient[msg.subscriber])
            emit('response', {'relayed': True}), 200
    else:
        emit('error', {'relayed': False, 'error': 'User not connected'}), 404


if __name__ == '__main__':
    socketio.run(app, port=3300, debug=True)

    # # use wss and https for secure connections on special ports.
    # socketio.run(
    #     app,
    #     host='0.0.0.0',
    #     port=3300,
    #     keyfile='path/to/privkey.pem',
    #     certfile='path/to/cert.pem',
    #     use_reloader=False, debug=True, log_output=True)
