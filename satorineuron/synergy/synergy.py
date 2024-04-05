# TODO: move to Central server repo
'''
creating a custom design for the synergy server allows us to avoid issues 
stemming from broadcast messages, even guaranteeing identity between clients.
'''
import json
import secrets
import datetime as dt
from flask import Flask, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from satoriwallet import ravencoin
from satorilib import logging
# from satoricentral import logging
from satorilib.api.time.time import timestampToDatetime, datetimeToTimestamp, now
from satorilib.synergy import SynergyProtocol


class SessionTime:
    def __init__(self, time: str, room: str):
        self.time = time
        self.room = room  # Socket.IO session IDs (request.sid)

    @staticmethod
    def expiry() -> int:
        return 30

    @property
    def expired(self):
        return timestampToDatetime(self.time) < now() - dt.timedelta(seconds=SessionTime.expiry())


app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
socketio = SocketIO(app)
challengeSalt: str = 'synergy'
sessionTimeByClient: dict[str, SessionTime] = {}


@app.route('/challenge', methods=['GET'])
def timeEndpoint():
    ''' test time route '''
    return challengeSalt + datetimeToTimestamp(now()), 200


@socketio.on('connect')
def handleConnect():
    '''Expect the client to send their pubkey upon connection'''

    def verifyTimestamp(ts, seconds: float = None):
        if seconds is None:
            seconds = SessionTime.expiry()
        timestamp = timestampToDatetime(ts)
        rightNow = now()
        if seconds > 0:
            recentPast = rightNow - dt.timedelta(seconds=seconds)
            return timestamp > recentPast
        if seconds == 0:
            return timestamp < rightNow
        if seconds < 0:
            nearFuture = rightNow - dt.timedelta(seconds=seconds)
            return timestampToDatetime(ts) < nearFuture

    def validateChallenge(challenge):
        ts = challenge[len(challengeSalt):]
        if (not verifyTimestamp(ts)) or (not verifyTimestamp(ts, seconds=0)):
            logging.error('auth ts error', ts, (not verifyTimestamp(ts)),
                          (not verifyTimestamp(ts, seconds=0)), 'now:', dt.datetime.utcnow())
            return False
        return ts

    def authenticate(challenge, signature, pubkey):
        if not ravencoin.verify(
            message=challenge,
            signature=signature,
            publicKey=pubkey,
        ):
            return 'unable to verify signature', 400
        return '', 200

    def saveUser(ts: str):
        if pubkey in sessionTimeByClient and not sessionTimeByClient[pubkey].expired:
            emit('error', {'data': "don't do that."})
            disconnect()
            return
        room = request.sid
        sessionTimeByClient[pubkey] = SessionTime(time=ts, room=room)
        join_room(room)
        emit('response', {'data': f'{pubkey} connected.'})

    pubkey = request.args.get('pubkey')
    signature = request.args.get('signature')
    challenge = request.args.get('challenge')
    if pubkey:
        if signature:
            if challenge:
                ts = validateChallenge(challenge)
                if ts:
                    if authenticate(challenge, signature, pubkey):
                        saveUser(ts)
                    else:
                        emit('error', {'data': 'unable to authenticate.'})
                        disconnect()
                else:
                    emit('error', {'data': 'invalid challenge.'})
                    disconnect()
            else:
                emit('error', {'data': 'no challenge.'})
                disconnect()
        else:
            emit('error', {'data': 'no signature.'})
            disconnect()
    else:
        emit('error', {'data': 'no pubkey.'})
        disconnect()


@socketio.on('disconnect')
def handleDisconnect():
    '''find which pubkey is associated with the disconnecting SID and remove it'''
    pubkeyToRemove = [
        pubkey for pubkey, sessionTime in sessionTimeByClient.items()
        if sessionTime.room == request.sid]
    if pubkeyToRemove:
        del sessionTimeByClient[pubkeyToRemove[0]]
        leave_room(request.sid)


@socketio.on('ping')
def handlePing(message):
    print('handlePing:', message)
    emit('response', message)


@socketio.on('message')
def handleMessage(message):
    print('handleMessage:', message)
    try:
        msg = SynergyProtocol.fromJson(message)
    except Exception as e:
        logging.error(e)
        emit('error', {'relayed': False, 'error': 'Invalid message format'})
        return
    if msg.subscriberPort is None:
        emit('error', {'relayed': False, 'error': 'subscriber port?'})
    elif msg.source is None or msg.stream is None or msg.target is None or msg.author is None:
        emit('error', {'relayed': False, 'error': 'stream?'})
    elif msg.subscriberIp is None:
        msg.subscriberIp = request.remote_addr
        if msg.author in sessionTimeByClient:
            emit(
                'message',
                {'message': msg.toJson()},
                room=sessionTimeByClient[msg.author].room)
            emit('response', {'relayed': True})
        else:
            emit('error', {'relayed': False, 'error': 'author not connected'})
    elif msg.authorPort is None or msg.subscriberPort is None:
        emit('error', {'relayed': False, 'error': 'author port?'})
    elif msg.authorIp is None:
        msg.authorIp = request.remote_addr
        if msg.subscriber in sessionTimeByClient:
            emit(
                'message',
                {'message': msg.toJson()},
                room=sessionTimeByClient[msg.subscriber].room)
            emit('response', {'relayed': True})
        else:
            emit('error', {'relayed': False,
                 'error': 'subscriber not connected'})


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
