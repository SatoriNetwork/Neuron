import time
import socket
import threading
import datetime as dt
from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.api.time import datetimeToString, now
from satorineuron.rendezvous.structs.protocol import PeerProtocol
from satorineuron.rendezvous.structs.message import PeerMessage, PeerMessages
# from satorineuron.rendezvous.connect import Connection
from satorirendezvous.lib.lock import LockableDict
# from satorineuron.rendezvous.topic import Topic # circular import


class Channel:
    ''' manages a single connection between two nodes over UDP '''

    def __init__(
        self,
        streamId: StreamId,
        remoteIp: str,
        remotePort: int,
        parent: 'Topic',
        ping: bool = True,
    ):
        self.streamId = streamId
        self.messages: PeerMessages = PeerMessages([])
        self.parent = parent
        self.topic = self.streamId.topic()
        self.pingInterval = 28  # seconds
        self.setupConnection(remoteIp, remotePort)
        if ping:
            self.setupPing()

    def setupConnection(
        self,
        remoteIp: str,
        remotePort: int,
    ):
        # connection object is handled outside.
        # self.connection = Connection(
        #    topicSocket=parent.sock,
        #    peerIp=ip,
        #    peerPort=port,
        #    port=localPort,
        #    onMessage=self.onMessage)
        # self.connection.establish()
        self.remoteIp = remoteIp
        self.remotePort = remotePort

    def setupPing(self):

        def pingForever(interval=self.pingInterval):
            while True:
                time.sleep(interval)
                self.send(
                    cmd=PeerProtocol.ping())
                # a ping shouldn't be a request, I'm not requesting anything
                # cmd=PeerProtocol.request(
                #    time=datetimeToString(now()),
                #    subcmd=PeerProtocol.pingSub))

        self.pingThread = threading.Thread(target=pingForever)
        self.pingThread.start()

    # override
    def onMessage(
        self,
        message: bytes,
        sent: bool,
        time: dt.datetime = None,
        **kwargs,
    ):
        if (message is None):
            return
        logging.debug('ON MESSAGE:', message, sent, time, print='magenta')
        message = PeerMessage(sent=sent, raw=message, time=time)
        logging.debug('ON MESSAGE0:', message, print='magenta')
        self.clean(stale=now() - dt.timedelta(minutes=90))
        logging.debug('ON MESSAGE1:', print='magenta')
        self.add(message=message)
        logging.debug('ON MESSAGE2:', print='magenta')
        self.router(message=message, **kwargs)
        logging.debug('ON MESSAGE3:', print='magenta')

    # override
    def add(self, message: PeerMessage):
        with self.messages:
            self.messages.append(message)

    def clean(self, stale: dt.datetime):
        '''
        since we're incrementally sharing entire history datasets, we need
        to clean up these messages periodically. otherwise they'll eat up ram.
        for now, it's called every time we get a new message. hopefully that's
        sufficient.
        '''
        with self.messages:
            for message in self.messages:
                if message.time < stale:
                    self.messages.remove(message)

    def send(self, cmd: str, msgs: list[str] = None):
        # connection is outside...
        # self.connection.send(cmd, msgs)
        # so route messages back to parent:
        self.parent.send(
            self.remoteIp,
            self.remotePort,
            cmd,
            msgs)

    def router(self, message: PeerMessage, **kwargs):
        ''' routes the message to the appropriate handler '''
        # if message.isPing(): do nothing
        if message.isRequest(subcmd=PeerProtocol.observationSub):
            self.giveOneObservation(timestamp=message.data)
        if message.isRequest(subcmd=PeerProtocol.countSub):
            self.giveCount(timestamp=message.data)
        # elif message.isResponse():
        #    self.handleResponse(message=message, **kwargs)

    def giveOneObservation(self, timestamp: str):
        ''' 
        returns the observation prior to the time of the most recent observation
        '''
        if isinstance(timestamp, dt.datetime):
            timestamp = datetimeToString(timestamp)
        # observation = self.disk.lastRowStringBefore(timestap=time)
        observation = self.parent.getLocalObservation(timestap=timestamp)
        if observation is None:
            pass  # send nothing: we don't know.
        elif observation == (None, None):
            self.send(PeerProtocol.respondNone(
                subcmd=PeerProtocol.observationSub))
        else:
            self.send(PeerProtocol.respond(
                subcmd=PeerProtocol.observationSub,
                time=observation[0],
                data=observation[1]))

    def giveCount(self, timestamp: str):
        ''' 
        returns the observation prior to the time of the most recent observation
        '''
        if isinstance(timestamp, dt.datetime):
            timestamp = datetimeToString(timestamp)
        # observation = self.disk.lastRowStringBefore(timestap=time)
        count = self.parent.getLocalCount(timestamp=timestamp)
        if count is None:
            pass  # send nothing: we don't know.
        else:
            self.send(PeerProtocol.respond(
                subcmd=PeerProtocol.countSub,
                time=timestamp,
                data=count))

    def requests(self):
        return [msg for msg in self.messages if msg.isRequest()]

    def responses(self):
        return [msg for msg in self.messages if msg.isResponse()]

    def myRequests(self):
        return [msg for msg in self.requests() if msg.sent]

    def theirResponses(self):
        return [msg for msg in self.responses() if not msg.sent]

    def mostRecentResponse(self, responses: list[PeerMessage] = None):
        responses = responses or self.theirResponses()
        if len(responses) == 0:
            return None
        return responses[-1]

    def responseAfter(self, time: dt.datetime):
        return [msg for msg in self.theirResponses() if msg.time > time]

    def orderedMessages(self) -> list[PeerMessage]:
        ''' most recent last messages by PeerMessage.time '''
        return sorted(self.messages, key=lambda msg: msg.time)

    def messagesAfter(self, time: dt.datetime) -> list[PeerMessage]:
        return [msg for msg in self.messages if msg.time > time]

    def receivedAfter(self, time: dt.datetime) -> list[PeerMessage]:
        return [
            msg for msg in self.messages
            if msg.time > time and not msg.sent]

    def isReady(self) -> bool:
        return len(self.receivedAfter(time=dt.datetime.now() - dt.timedelta(minutes=28))) > 0


class Channels(LockableDict[tuple[str, int], Channel]):
    '''
    iterating over this list within a context manager is thread safe, example: 
        with channels:
            channels.append(channel)
    '''
