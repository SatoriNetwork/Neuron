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
import json
from satorilib.concepts import StreamId
from satorirendezvous.example.client.structs.protocol import ToServerSubscribeProtocol
from satorirendezvous.example.peer.rest import SubscribingPeer
from satorineuron.rendezvous.topic import Topic, Topics
from satorineuron.rendezvous.structs.domain import SignedStreamId
from satorineuron.rendezvous.rest import RendezvousByRest


class RendezvousPeer(SubscribingPeer):
    '''
    manages connection to the rendezvous server and all our udp topics:
    authenticates and subscribes to our streams
    '''
    # TODO: I need to provide my signed wallet id, to prove who I am, just as I
    # do for the pubsub or sometihng. then the rendezvous server will know I'm
    # allowed by the server and that my ip is who I say I am. then it will take
    # my signed stream ids and subscribe me to those streams.

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
        super().__init__(
            rendezvousHost=rendezvousHost,
            topics=[streamId.topic() for streamId in signedStreamIds],
            handlePeriodicCheckin=handlePeriodicCheckin,
            periodicCheckinSeconds=periodicCheckinSeconds)

    # override
    def createTopics(self, _: list[str]):
        self.topics: Topics = Topics({
            s.topic(): Topic(s) for s in self.signedStreamIds})

    def topicFor(self, streamId: StreamId) -> Union[Topic, None]:
        for name, topic in self.topics.items():
            if name == streamId.topic():
                return topic
        return None

    # override
    def connect(self, rendezvousHost: str):
        self.rendezvous: RendezvousByRest = RendezvousByRest(
            signature=self.signature,
            signed=self.signed,
            host=rendezvousHost,
            onMessage=self.handleRendezvousMessage)

    # never called
    def sendTopics(self):
        ''' send our topics to the rendezvous server to get peer lists '''
        for topic in self.topics.keys():
            self.sendTopic(topic)

    def sendTopic(self, topic: str):
        self.rendezvous.send(
            cmd=ToServerSubscribeProtocol.subscribePrefix,
            msgs=[
                "signature doesn't matter during testing",
                json.dumps({
                    **{'pubkey': 'wallet.pubkey'},
                    # **(
                    #    {
                    #        'publisher': [topic]}
                    # ),
                    **(
                        {
                            'subscriptions': [topic]
                        }
                    )})])
