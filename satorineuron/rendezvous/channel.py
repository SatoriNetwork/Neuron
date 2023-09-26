import socket
import datetime as dt
from satorilib.api.time import datetimeToString
from satorilib.concepts import StreamId
from satorilib.api.disk.disk import Disk
from satorirendezvous.lib.lock import LockableList
from satorirendezvous.peer.p2p.channel import Channel as BaseChannel
from satorirendezvous.example.peer.structs.message import PeerMessage, PeerMessages
from satorirendezvous.example.peer.structs.protocol import PeerProtocol


class Channel(BaseChannel):
    ''' manages a single connection between two nodes over UDP '''

    def __init__(
        self,
        streamId: StreamId,
        ip: str,
        port: int,
        localPort: int,
        topicSocket: socket.socket,
    ):
        self.streamId = streamId
        self.messages: PeerMessages = PeerMessages([])
        self.disk = Disk(self.streamId)
        super().__init__(
            topic=self.streamId.topic(),
            ip=ip,
            port=port,
            localPort=localPort,
            topicSocket=topicSocket)

    # override
    def add(
        self,
        message: bytes,
        sent: bool,
        time: dt.datetime = None,
        **kwargs,
    ):
        with self.messages:
            self.messages.append(PeerMessage(
                sent=sent, raw=message, time=time))

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

    def giveOneObservation(self, time: dt.datetime):
        ''' 
        returns the observation prior to the time of the most recent observation
        '''
        if isinstance(time, dt.datetime):
            time = datetimeToString(time)
        observation = self.disk.lastRowStringBefore(timestap=time)
        if observation is None:
            self.send(PeerProtocol.respondNoObservation())
        else:
            self.send(PeerProtocol.respondObservation(
                time=observation[0],
                data=observation[1]))


class Channels(LockableList[Channel]):
    '''
    iterating over this list within a context manager is thread safe, example: 
        with channels:
            channels.append(channel)
    '''
