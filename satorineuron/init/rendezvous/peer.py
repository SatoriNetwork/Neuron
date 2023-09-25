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
import json
from satorilib.concepts import StreamId
from satorirendezvous.example.client.structs.protocol import ToServerSubscribeProtocol
from satorirendezvous.example.client.rest import RendezvousByRestAuthenticated
from satorirendezvous.example.peer.rest import SubscribingPeer
from satorineuron.init.rendezvous.topic import Topic, Topics


class AuthenticatedSubscribingPeer(SubscribingPeer):
    ''' manages connection to the rendezvous server and all our udp topics '''

    def __init__(
        self,
        streamIds: list[StreamId],
        rendezvousHost: str,  # https://satorinet.io/rendezvous
        rendezvousPort: int,
        signature: str = None,
        key: str = None,
        handlePeriodicCheckin: bool = True,
        periodicCheckinSeconds: int = 60*60*1,
    ):
        self.signature = signature
        self.key = key
        self.streamIds = streamIds
        super().__init__(
            rendezvousHost=rendezvousHost,
            rendezvousPort=rendezvousPort,
            topics=[streamId.topic() for streamId in streamIds],
            handlePeriodicCheckin=handlePeriodicCheckin,
            periodicCheckinSeconds=periodicCheckinSeconds)

    # override
    def createTopics(self, topics: list[str]):
        self.topics: Topics = Topics({
            s.topic(): Topic(s) for s in self.streamIds})

    def topicFor(self, streamId: StreamId):
        for name, topic in self.topics.items():
            if name == streamId.topic():
                return topic
        return None

    # override

    def connect(self, rendezvousHost: str, rendezvousPort: int):
        self.rendezvous: RendezvousByRestAuthenticated = RendezvousByRestAuthenticated(
            signature=self.signature,
            key=self.key,
            host=rendezvousHost,
            port=rendezvousPort,
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
