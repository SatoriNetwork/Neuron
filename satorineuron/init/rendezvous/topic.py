from time import sleep
from typing import Union
import datetime as dt
from satorilib.api.time import now
from satorilib.concepts import StreamId
from satorirendezvous.example.peer.structs.message import PeerMessage
from satorirendezvous.example.peer.structs.protocol import PeerProtocol
from satorirendezvous.peer.channel import Channel
from satorirendezvous.lib.lock import LockableDict
from satorirendezvous.peer.topic import Topic as BaseTopic


class Topic(BaseTopic):
    ''' manages all our udp channels for a single topic '''

    def __init__(self, streamId: StreamId, port: int):
        super().__init__(name=streamId.topic(), port=port)
        self.streamId = streamId

    # override
    def create(self, ip: str, port: int, localPort: int):
        print(f'CREATING: {ip}:{port},{localPort}')
        self.channels.append(Channel(self.streamId, ip, port, localPort))

    def getOneObservation(self, time: dt.datetime):
        ''' time is of the most recent observation '''
        msg = PeerProtocol.requestObservationBefore(time)
        sentTime = now()
        with self.channels:
            for channel in self.channels:
                channel.send(msg)
        sleep(5)  # wait for responses, natural throttle
        with self.channels:
            responses: list[Union[PeerMessage, None]] = [
                channel.mostRecentResponse(channel.responseAfter(sentTime))
                for channel in self.channels]
        responseMessages = [
            response.raw for response in responses
            if response is not None]
        mostPopularResponseMessage = max(
            responseMessages,
            key=lambda response: len([
                r for r in responseMessages if r == response]))
        # here we could enforce a threshold, like super majority or something,
        # by saying this message must make up at least 67% of the responses
        # but I don't think it's necessary for now.
        return mostPopularResponseMessage


class Topics(LockableDict[str, Topic]):
    '''
    iterating over this dictionary within a context manager is thread safe, 
    example: 
        with topics:
            topics['topic'] = Topic('name', 1234)
    '''
