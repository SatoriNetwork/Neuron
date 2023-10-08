import socket
import datetime as dt
from satorilib.api.time import datetimeToString
from satorilib.concepts import StreamId
from satorilib.api.disk.disk import Disk
from satorineuron.rendezvous.structs.message import PeerMessage, PeerMessages
from satorineuron.rendezvous.structs.protocol import PeerProtocol
from satorirendezvous.lib.lock import LockableList
from satorirendezvous.peer.p2p.channel import Channel as BaseChannel
# from satorineuron.rendezvous.topic import Topic


class Channel(BaseChannel):
    ''' manages a single connection between two nodes over UDP '''

    def __init__(
        self,
        streamId: StreamId,
        ip: str,
        port: int,
        localPort: int,
        topicSocket: socket.socket,
        parent: 'Topic',
    ):
        self.streamId = streamId
        self.messages: PeerMessages = PeerMessages([])
        self.disk = Disk(self.streamId)
        self.parent = parent
        super().__init__(
            topic=self.streamId.topic(),
            ip=ip,
            port=port,
            localPort=localPort,
            topicSocket=topicSocket)

    # override
    def onMessage(
        self,
        message: bytes,
        sent: bool,
        time: dt.datetime = None,
        **kwargs,
    ):
        message = PeerMessage(sent=sent, raw=message, time=time)
        self.add(message=message)
        self.router(message=message, **kwargs)

    # override
    def add(self, message: PeerMessage):
        with self.messages:
            self.messages.append(message)

    def router(self, message: PeerMessage, **kwargs):
        ''' routes the message to the appropriate handler '''
        # if message.isPing(): do nothing
        if message.isRequest(subcmd=PeerProtocol.observationSub):
            self.giveOneObservation(timestamp=message.data)
        if message.isRequest(subcmd=PeerProtocol.countSub):
            self.giveCount(timestamp=message.data)
        if message.isRequest(subcmd=PeerProtocol.hashSub):
            self.giveHash(timestamp=message.data)
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

    def giveHash(self, timestamp: str):
        ''' 
        returns the hash associated with the observation prior to the time of 
        the most recent observation or prior to timestamp
        '''
        if isinstance(timestamp, dt.datetime):
            timestamp = datetimeToString(timestamp)
        hash = self.parent.getLocalHash(timestamp=timestamp)
        if hash is None:
            pass  # send nothing: we don't know.
        else:
            self.send(PeerProtocol.respond(
                subcmd=PeerProtocol.hashSub,
                time=timestamp,
                data=hash))

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


class Channels(LockableList[Channel]):
    '''
    iterating over this list within a context manager is thread safe, example: 
        with channels:
            channels.append(channel)
    '''
