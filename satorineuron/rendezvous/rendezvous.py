import time
import threading
from satorilib.concepts import StreamId, Observation
from satorilib.utils.eq import eq
from satorilib.api import disk
from satorilib.api.time import datetimeFromString, now
from satorirendezvous.example.peer.structs.message import PeerMessage
from satorirendezvous.server.rest.constants import rendezvousPort
from satorineuron.rendezvous.peer import RendezvousPeer
from satorineuron.rendezvous.structs.domain import SignedStreamId
# from satorineuron.init.start import StartupDag # circular import...


class RendezvousEngine():
    def __init__(self, peer: RendezvousPeer, start):  # 'StartupDag'
        self.peer: RendezvousPeer = peer
        self.start = start  # 'StartupDag'
        self.peer.parent = start

    def getHistoryOf(self, streamId: StreamId):

        def tellModelsAboutNewHistory():
            tellEm = False
            for model in self.start.engine.models:
                if model.variable == streamId:
                    tellEm = True
                else:
                    for target in model.targets:
                        if target == streamId:
                            tellEm = True
            if tellEm:
                model.inputsUpdated.on_next(True)

        def gatherUnknownHistory() -> list[PeerMessage]:

            def lookThoughIncrementals(timestamp: str, value: str):
                ''' gets a df of the incrementals and looks for the observation'''
                df = diskApi.read(aggregate=False)
                if timestamp in df.index:
                    return eq(df.loc[timestamp].values[0], value)
                return False

            def lookThoughAggregates(timestamp: str, value: str):
                ''' sees if the timestamp exists in the aggregate '''
                # only checks to see if the timestamp exists, not the value
                # if we want to check the value to we have to read in the full file
                return diskApi.timeExistsInAggregate(timestamp)

            msg: PeerMessage = topic.getOneObservation(time=now())
            incrementalsChecked = False
            msgsToSave = []
            while msg is not None and not msg.isNoneResponse():
                # here we have a situation. we should tell the data manager about
                # this and let it handle it. but this stream isnt' the best way to
                # do that because it is built for only new realtime data in mind:
                # start.engine.data.newData.on_next(
                #    ObservationFromPeerMessage.fromPeerMessage(msg))
                # well. we have history datapoints that we may or may not already
                # have, furthermore, if we do already have it, we should probably
                # top asking... so what do we do here? technically all ipfs sync
                # is save the entire ipfs history to disk using:
                # diskApi.path(aggregate=None, temp=True)
                # then combines it with what is currently known, on disk, using:
                # diskApi.compress(includeTemp=True)
                # but we don't want to do that because we dont' want to download the
                # entire history. we want to stop once we start seeing data we
                # already have. so we really need 2-way communication with the data
                # manager of the engine... so we need to listen to a stream on which
                # it can respond. which is pretty nasty. so we'll think about it...
                # ok, I think I know what to do. we don't ask or notify the data
                # manager at all. instead we look at the data, one row at a time
                # until we find this observation or don't. if we don't find it, we
                # we know we can stop asking, if we don't find it, we save it as an
                # incremental, and loop until we reach the end or find one we have.
                # then we combine the incrementals with the aggregate and compress
                # and if we have to do that, we tell the models to update. done.
                # we'll have to look through the incrementals first, then the
                # aggregates. and keep a flag if we get into aggregates, so we don't
                # hit incrementals each time we loop.
                if not incrementalsChecked:
                    incrementalsChecked = True  # only on the first loop
                    if lookThoughIncrementals(msg.observationTime, msg.data):
                        break
                    else:
                        found = lookThoughAggregates(
                            msg.observationTime, msg.data)
                        if found:
                            break
                        else:
                            msgsToSave.append(msg)
                msg = topic.getOneObservation(
                    time=datetimeFromString(msg.observationTime))
            return msgsToSave

        def findTopic():
            return self.peer.topicFor(streamId)
            # if topic is None: return False  # error?

        topic = findTopic()
        if topic:
            diskApi = disk.Disk(id=streamId)
            msgs = gatherUnknownHistory()
            if len(msgs) > 0:
                # save
                diskApi.append(msgsToDataframe(msgs))
                tellModelsAboutNewHistory()

    def runForever(self, interval=60*60):
        relayStreamIds = [
            stream.streamId for stream in self.start.relay.streams]
        while True:
            for signedStreamId in self.peer.signedStreamIds:
                if signedStreamId.streamId not in relayStreamIds:
                    time.sleep(interval)
                    # TODO NEXT
                    # instead of this we should ask peers for a count of their
                    # history, compare the count to our count and then if its
                    # different we do this starting with the most recent data,
                    # if we don't find anything then we start at the oldest data,
                    # if we don't find anyting we just ask for everything.
                    # (for that) we could use ipfs or something.
                    # if it's the same, we do nothing.
                    self.getHistoryOf(streamId=signedStreamId.streamId)

    def run(self):
        self.thread = threading.Thread(target=self.runForever, daemon=True)
        self.thread.start()


def generatePeer(signature: str, signed: str, signedStreamIds: list[SignedStreamId]):
    ''' generates a p2p peer '''
    # ws 161.35.238.159:49152
    return RendezvousPeer(
        signedStreamIds=signedStreamIds,
        rendezvousHost=f'https://satorinet.io:{rendezvousPort}/api/v0/raw/',
        signature=signature,  # 'my signature, encrypted by the server',
        signed=signed,  # 'my public key and magic salt')
    )


def msgsToDataframe(messages: list[PeerMessage]):
    import pandas as pd
    return pd.DataFrame({
        'observationTime': [message.observationTime for message in messages],
        'data': [message.data for message in messages]
    }).set_index('observationTime', inplace=True)


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
