'''
our connection to the rendezvous server and to other peers has to work like this:

0. we sync our topics peers with the rendezvous server client lists:
    1. we connect to the rendezvous server
    2. we tell the rendezvous server which streams we want to connect to:
1. for each stream:
    1. we create a topic (StreamId)
    2. we create a channel for each connection in that topic
    3. if a topic has a connection that was not provided by the server, we 
    drop that connection.
    4. we sync history 
        1. we broadcast a message to all channels in that topic asking for history
        2. we wait for a response from each channel, and take the most popular
        3. we receive a request
        
'''
from typing import Union
import time
import threading
from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.api.hash import generateCheckinTime
from satorirendezvous.client.structs.rest.message import FromServerMessage
from satorineuron.rendezvous.topic import Topic, Topics
from satorineuron.rendezvous.structs.domain import SignedStreamId
from satorineuron.rendezvous.rest import RendezvousByRest


class RendezvousPeer():
    '''
    manages connection to the rendezvous server and all our udp topics:
    authenticates and subscribes to our streams
    '''

    def __init__(
        self,
        signedStreamIds: list[SignedStreamId],
        rendezvousHost: str,
        signature: str,
        signed: str,
        handleCheckin: bool = True,
    ):
        self.signature = signature
        self.signed = signed
        self.signedStreamIds = signedStreamIds
        # need a lock? don't think so
        self.outbox: list[tuple[int, str, int, bytes]] = []
        self.topics: Topics = Topics()
        self.createTopics()
        self.connect(rendezvousHost)
        if handleCheckin:
            self.streamTimesCheckin()

    def toOutbox(self, message: tuple[int, str, int, bytes]):
        self.outbox.append(message)

    def periodicCheckinUsingThreading(self):
        ''' this is the old way of doing it '''
        self.checker = threading.Thread(target=self.checkin, daemon=True)
        self.checker.start()

    def checkinUsingThreading(self):
        while True:
            time.sleep(self.periodicCheckinSeconds)
            self.rendezvous.checkin()

    def periodicCheckin(self):
        ''' this is the newer old way of doing it '''
        from satorineuron.init.start import getStart
        asyncThread = getStart().asyncThread
        self.checker = asyncThread.repeatRun(
            task=self.checkin,
            interval=self.periodicCheckinSeconds)

    def streamTimesCheckin(self):
        ''' checking according to which streams we have '''
        from satorineuron.init.start import getStart
        asyncThread = getStart().asyncThread
        self.checker = asyncThread.dailyRun(
            task=self.checkin,
            times=[generateCheckinTime(s.streamId) for s in self.signedStreamIds])
        # self.checkin()

    def checkin(self):
        self.rendezvous.checkin()

    def createTopics(self):
        with self.topics:
            self.topics: Topics = Topics({
                s.topic(): Topic(s, outbox=self.toOutbox) for s in self.signedStreamIds})

    def connect(self, rendezvousHost: str):
        self.rendezvous: RendezvousByRest = RendezvousByRest(
            signature=self.signature,
            signed=self.signed,
            host=rendezvousHost,
            onMessage=self.handleRendezvousMessage)

    def handleRendezvousMessage(self, msg: FromServerMessage):
        ''' receives all messages from the rendezvous server '''
        if msg.isConnect:
            try:
                for subscribable in msg.messages:
                    for connection in subscribable:
                        topic = connection.get('topic')
                        ip = connection.get('peer.ip')
                        port = connection.get('peer.port')
                        localPort = connection.get('client.port')
                        if (
                            topic is not None and
                            ip is not None and
                            port is not None and
                            localPort is not None
                        ):
                            topic = str(connection.get('topic'))
                            with self.topics:
                                if topic in self.topics.keys():
                                    self.topics[topic].setLocalPort(localPort)
                                    self.topics[topic].createChannel(ip, port)
                                else:
                                    logging.error(
                                        'topic not found', topic, print=True)
            except ValueError as e:
                logging.error('error parsing message', e, print=True)

    # unused...

    def add(self, topic: str):
        with self.topics:
            self.topics[topic] = Topic(topic, outbox=self.toOutbox)

    def remove(self, topic: str):
        with self.topics:
            del (self.topics[topic])

    def topicFor(self, streamId: StreamId) -> Union[Topic, None]:
        # for name, topic in self.topics.items():
        #    if name == streamId.topic():
        #        return topic
        # return None
        return self.topics.get(streamId.topic(), None)

    def findTopic(self, localPort: int) -> Union[Topic, None]:
        ''' this should be the way we index them. '''
        for topic in self.topics.values():
            if topic.localPort == localPort:
                return topic
        return None
        # return self.topics.get(localPort, None)
