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
from satorirendezvous.client.structs.message import FromServerMessage
from satorirendezvous.peer.p2p.topic import Topic, Topics
from satorirendezvous.client.rest import RendezvousByRest
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
        handlePeriodicCheckin: bool = True,
        periodicCheckinSeconds: int = 60*60*1,
    ):
        self.signature = signature
        self.signed = signed
        self.signedStreamIds = signedStreamIds
        self.parent: 'RendezvousEngine' = None
        self.createTopics()
        self.connect(rendezvousHost)
        if handlePeriodicCheckin:
            self.periodicCheckinSeconds = periodicCheckinSeconds
            self.periodicCheckin()
        super().__init__(
            rendezvousHost=rendezvousHost,
            topics=[streamId.topic() for streamId in signedStreamIds],
            handlePeriodicCheckin=handlePeriodicCheckin,
            periodicCheckinSeconds=periodicCheckinSeconds)

    def periodicCheckin(self):
        self.checker = threading.Thread(target=self.checkin, daemon=True)
        self.checker.start()

    def checkin(self):
        while True:
            time.sleep(self.periodicCheckinSeconds)
            self.rendezvous.checkin()

    def createTopics(self):
        self.topics: Topics = Topics({
            s.topic(): Topic(s) for s in self.signedStreamIds})

    def connect(self, rendezvousHost: str):
        self.rendezvous: RendezvousByRest = RendezvousByRest(
            signature=self.signature,
            signed=self.signed,
            host=rendezvousHost,
            onMessage=self.handleRendezvousMessage)

    def handleRendezvousMessage(self, msg: FromServerMessage):
        ''' receives all messages from the rendezvous server '''
        logging.debug('Rendezvous FromServerMessage: ', msg, print='teal')
        if msg.isConnect:
            logging.debug('isConnect', print='teal')
            try:
                topic = msg.payload.get('topic')
                logging.debug('topic', topic, print='teal')
                ip = msg.payload.get('peerIp')
                logging.debug('ip', ip, print='teal')
                port = int(msg.payload.get('peerPort'))
                logging.debug('port', port, print='teal')
                localPort = int(msg.payload.get('clientPort'))
                logging.debug('localPort', localPort, print='teal')
                if topic is not None and ip is not None:
                    with self.topics:
                        if topic in self.topics.keys():
                            self.topics[topic].create(
                                ip=ip,
                                port=port,
                                localPort=localPort)
                        else:
                            logging.error('topic not found', topic, print=True)
            except ValueError as e:
                logging.error('error parsing message', e, print=True)

    # unused...

    def add(self, topic: str):
        with self.topics:
            self.topics[topic] = Topic(topic)

    def remove(self, topic: str):
        with self.topics:
            del (self.topics[topic])

    def topicFor(self, streamId: StreamId) -> Union[Topic, None]:
        for name, topic in self.topics.items():
            if name == streamId.topic():
                return topic
        return None
