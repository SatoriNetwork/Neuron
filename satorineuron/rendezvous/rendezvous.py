import time
import threading
from satorilib import logging
from satorilib.concepts import StreamId, Observation
from satorilib.api.time import datetimeFromString, now
from satorineuron.rendezvous.structs.message import PeerMessage, PeerMessages
from satorirendezvous.server.rest.constants import rendezvousPort
from satorineuron.rendezvous.peer import RendezvousPeer
from satorineuron.rendezvous.structs.domain import SignedStreamId
# from satorineuron.init.start import StartupDag # circular import...


class RendezvousEngine():
    def __init__(self, peer: RendezvousPeer, start):  # 'StartupDag'
        self.peer: RendezvousPeer = peer
        self.start = start  # 'StartupDag'

    def gatherMessages(self) -> list[tuple[int, str, int, bytes]]:
        ''' empties and returns whatever messages are in the queue '''
        messages = self.peer.outbox
        self.peer.outbox = []
        return messages

    def gatherChannels(self) -> dict[int, list[tuple[str, int]]]:
        '''
        gets the localPort of all the topics, get's the remoteIp and remotePort
        of all channels per topic 
        '''
        structure = {}
        for topic in self.peer.topics.values():
            structure[topic.localPort] = []
            for channel in topic.channels.values():
                structure[topic.localPort].append(
                    (channel.remoteIp, channel.remotePort))
        return structure

    def passMessage(self, localPort: int, remoteIp: str, remotePort: int, message: bytes):
        ''' passes a message down to the correct channel '''
        # TODO: organize topics by localPort because that's the only way we
        # filter them right? that's the way the outside knows them by.
        topic = self.peer.findTopic(localPort)
        if topic is None:
            return
        channel = topic.findChannel(remoteIp, remotePort)
        if channel is None:
            return
        channel.onMessage(message=message, sent=False)

    def tellModelsAboutNewHistory(self, streamId: StreamId):
        ''' 
        tells the models to go get their data again.
        (this should probably be in model manager or engine or something)
        '''
        for model in self.start.engine.models:
            if model.variable == streamId or streamId in model.targets:
                model.inputsUpdated.on_next(True)

    def runForever(self, interval=60*60):
        '''
        for all of our streams (subscribe to (predict, subscribe but not 
        predict), publish to (predict, relay)) we '''
        relayStreamIds = [
            stream.streamId
            for stream in self.start.relay.streams]
        while True:
            for topic in self.peer.topics.values():
                streamId = topic.signedStreamId.streamId
                if streamId not in relayStreamIds:
                    time.sleep(interval)
                    newDataFound = topic.getHistory()
                    if newDataFound:
                        self.tellModelsAboutNewHistory(streamId)
            # yes, we should move getHistory into Topic itself...
            # we would have to give it self.start.engine.models so it can tell
            # them to go get their data again. or it just returns True if there
            # was new data and we tell the models here.
            # for signedStreamId in self.peer.signedStreamIds:
            #    if signedStreamId.streamId not in relayStreamIds:
            #        time.sleep(interval)
            #        # TODO NEXT
            #        # actually we implemented hashed history. so new plan - we
            #        # ask the peers for the latest hash - if it doesn't match
            #        # our own we ask for history from the most recent to the
            #        # oldest. if at any point we find a match we stop asking.
            #        # if we reach the end stop asking. done.
            #        self.getHistoryOf(streamId=signedStreamId.streamId)

    def run(self):
        self.thread = threading.Thread(target=self.runForever, daemon=True)
        self.thread.start()


def generatePeer(
    signature: str,
    signed: str,
    signedStreamIds: list[SignedStreamId],
) -> RendezvousPeer:
    ''' generates a p2p peer '''
    logging.debug('generatePeer', print='magenta')
    return RendezvousPeer(
        signedStreamIds=signedStreamIds,
        # rendezvousHost = 161.35.238.159:49152, #ws
        rendezvousHost=f'https://satorinet.io:{rendezvousPort}/api/v0/raw/',
        signature=signature,
        signed=signed)


class ObservationFromPeerMessage(Observation):
    ''' observation object that is created from a peer message '''

    def __init__(self, raw, **kwargs):
        super().__init__(raw, **kwargs)

    @staticmethod
    def fromPeerMessage(message: PeerMessage):
        return Observation(
            raw=message.raw,
            sent=message.sent,
            time=message.time,
            prefix=message.prefix,
            observationTime=message.observationTime,
            data=message.data)


#########################
#########################
# '''
# this should probably be moved to the node
# this needs to be re-thought.
# listen we have a connection to the Rendezvous server
# we also have many streams which represent a topic
# we need to make many connections per topic
#
# modularize this
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
