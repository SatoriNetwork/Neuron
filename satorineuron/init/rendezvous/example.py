from satorineuron.init.rendezvous.peer import AuthenticatedSubscribingPeer
from satorirendezvous.example.server.behaviors.subscribe import SubscribingClientConnect


def exampleUse():
    ''' 
    example of how to extend and thereby use the satorirendezvous package
    '''
    peer = AuthenticatedSubscribingPeer(
        behavior=SubscribingClientConnect(),
        rendezvousHost='161.35.238.159',
        rendezvousPort=49152,
        topics=['topic1', 'topic2'],
        signature='',
        key='',
    )
    peer.topics['topic1'].broadcast('hello world')
    # use peer, etc...


#########################
#########################
# '''
# this should probably be moved to the node
# this needs to be re-thought.
# listen we have a connection to the Rendezvous server
# we also have many streams which represent a topic
# we need to make many connections per topic
#
# todo: modularize this
# also remove the hard coded functionality and make a new layer that manages the
# topic synchronization. we have a design now that stays connected to the server
# and only asks for our peers per topic once. No. we should ask for our peers
# a few times a day. and just send in all our topics each time. but that should
# be handled by a layer above this. we have to plan it out.
# '''
# import json
# from satorilib.concepts import StreamId
# from satorirendezvous.example.client.structs.protocol import ToServerSubscribeProtocol
# from satorirendezvous.client.connection import RendezvousConnection
# from satorirendezvous.peer.topic import Topic
# from satorirendezvous.peer.peer import Peer
#
#
# class AuthenticatedPeer(Peer):
#    ''' manages connection to the rendezvous server and all our udp topics '''
#
#    def __init__(self, streamIds: list[StreamId], signature: None, key: None):
#        '''
#        1. await - set up your connection to the rendezvous server
#        2. tell the rendezvous server which streams you want to connect to
#        3. for each set up a topic, and all the channels for that topic
#        '''
#        self.streamIds = self._mapStreamIds(streamIds or [
#            StreamId(
#                source='s',
#                stream='s1',
#                author='a',
#                target='t',),
#            StreamId(
#                source='s',
#                stream='s2',
#                author='a',
#                target='t',),
#        ])
#        self.rendezvous: RendezvousConnection = RendezvousConnection(
#            signature=signature,
#            key=key,
#            host='161.35.238.159',
#            port=49152,
#            onMessage=self.handleRendezvousResponse,
#        )
#        # self.topics: dict[str, Topic] = {
#        #    topic: Topic(streamId)
#        #    for topic, streamId in self.streamIds
#        # }
#        self.topics: dict[str, Topic] = {}
#        self.rendezvous.establish()
#        self.sendTopics()
#        # for streamId in streamIds:
#        # add a new channel - this might be done elsewhere. or in a method.
#
#    def _mapStreamIds(self, streamIds: list[StreamId]):
#        return {streamId.topic(): streamId for streamId in streamIds}
#
#    def handleRendezvousResponse(self, data: bytes, address: bytes):
#        '''
#        this is called when we receive a message from the rendezvous server
#        '''
#        print('received: ', data, address)
#        data = data.decode().split('|')
#        if data[0] == 'CONNECTION':
#            try:
#                print('data[1]')
#                print(data[1])
#                print('self.topics.keys()')
#                print(self.topics.keys())
#                self.topics.get(data[1]).create(
#                    ip=data[2],
#                    port=int(data[3]),
#                    localPort=int(data[4]))
#            except ValueError as e:
#                # logging.error('error parsing port', e)
#                print(e)
#
#    def sendTopics(self):
#        ''' send our topics to the rendezvous server to get peer lists '''
#        for topic in self.topics.keys():
#            self.rendezvous.behavior.send(
#                cmd=ToServerSubscribeProtocol.subscribePrefix,
#                msgs=[
#                    "signature doesn't matter during testing",
#                    json.dumps({
#                        **{'pubkey': 'wallet.pubkey'},
#                        # **(
#                        #    {
#                        #        'publisher': [topic]}
#                        # ),
#                        **(
#                            {
#                                'subscriptions': [topic]
#                            }
#                        )})])
