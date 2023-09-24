import datetime as dt
from satorilib.api.time import datetimeToString
from satorilib.concepts import StreamId
from satorilib.api.disk.disk import Disk
from satorirendezvous.peer.connect import Connection
from satorirendezvous.peer.structs.message import PeerMessage
from satorirendezvous.peer.structs.protocol import PeerProtocol


class Channel():
    ''' manages a single connection between two nodes over UDP '''

    # todo:
    # 0. we should be using topics not streamIds
    # 1. why must we filter down to ready channels?
    # 2. why ever have ready channels?
    # 3. why not have a callback for getOneObservation?
    # 4. shouldn't every msg have a unique id?
    # 5. if we had a unique id on messages we could match them to a request.

    def __init__(self, streamId: StreamId, ip: str, port: int, localPort: int):
        self.streamId = streamId
        self.disk = Disk(self.streamId)
        self.connection = Connection(
            peerIp=ip,
            peerPort=port,
            port=localPort,
            # todo: messageCallback= function to handle messages
        )
        self.messages: list[PeerMessage] = []
        self.connect()

    def add(self, message: bytes, sent: bool, time: dt.datetime = None):
        self.messages.append(PeerMessage(sent, message, time))
        self.messages = self.orderedMessages()

    def orderedMessages(self):
        ''' returns the messages ordered by PeerMessage.time '''
        return sorted(self.messages, key=lambda msg: msg.time)

    def connect(self):
        self.connection.establish()

    def isReady(self):
        return (
            len([
                msg for msg in self.messages
                if msg.isConfirmedReady() and msg.sent]) > 0 and
            len([
                msg for msg in self.messages
                if msg.isConfirmedReady() and not msg.sent]) > 0)

    def send(self, message: bytes):
        self.connection.send(message)

    def readies(self):
        return [msg for msg in self.messages if msg.isReady()]

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
