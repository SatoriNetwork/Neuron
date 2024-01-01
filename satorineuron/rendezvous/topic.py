from typing import Union, Callable
import time
import datetime as dt
import pandas as pd
from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.api.disk import Cached
from satorilib.api.time import datetimeFromString, now, earliestDate
from satorirendezvous.lib.lock import LockableDict
from satorineuron.rendezvous.structs.message import PeerMessage
from satorineuron.rendezvous.structs.protocol import PeerProtocol
from satorineuron.rendezvous.structs.domain import SignedStreamId
from satorineuron.rendezvous.structs.domain import SingleObservation
from satorineuron.rendezvous.channel import Channel, Channels


class Gatherer():
    '''
    manages the the process of getting the history of this topic incrementally.
    the process works like this: 
        0. this process can be restarted by a supervisor here or above
        1. ask all channels for the root observation
        2. get last datapoint tied to the root, delete what's not in chain
        3. repeat 2 until we never get an answer
    '''

    def __init__(self, parent: 'Topic'):
        self.parent = parent
        self.refresh()

    def refresh(self):
        self.lastAsk = None
        # self.lastTime = None
        self.timeout = None
        self.messages: dict[str, list[PeerMessage]] = {}

    @property
    def data(self):
        return self.parent.data

    @property
    def hashes(self):
        if self.data is not None:
            return self.data.hash.values
        return []

    def prepare(self, withSupervisor: bool = True):
        ''' we verify that our first row (the root) matches the consensus '''
        self.cleanup()
        self.request(datetime=earliestDate())
        if withSupervisor:
            self.startSupervisor()

    def startSupervisor(self):
        ''' incase we lose connection, try again in 60 seconds '''
        from satorineuron.init.start import getStart
        asyncThread = getStart().asyncThread
        # if hasattr(self, 'supervisor') and self.supervisor is not None:
        #    asyncThread.cancelTask(self.supervisor)
        self.supervisor = asyncThread.repeatRun(
            task=self.initiateIfIdle,
            interval=60)

    def initiateIfIdle(self):
        if hasattr(self, 'lastTime') and self.lastTime < time.time() - 28:
            if hasattr(self, 'root') and self.root is not None:
                self.cleanup()
                self.initiate()
                self.lastAsk = ''
            else:
                self.prepare(withSupervisor=False)

    def initiate(self, message: PeerMessage = None):
        ''' here we decide what to ask for '''

        def askForNextData():
            return self.request(message)

        if self.data is None or self.data.empty:
            return askForNextData()
        if (
            hasattr(self, 'root') and
            isinstance(self.root, pd.DataFrame) and
            self.parent.disk.matchesRoot(self.root, localDf=self.data)
        ):
            success, row = self.parent.disk.validateAllHashes(self.data)
            if not success:
                return self.request(datetime=datetimeFromString(row.index[0]))
            lastTimeStamp = datetimeFromString(self.data.index[-1])
            if lastTimeStamp != self.lastAsk:
                return self.request(datetime=lastTimeStamp)
            return self.finishProcess()
        return askForNextData()

    # def makeTimeout(self, msgId: str):
    #    ''' handles cancel the existing timeout task before reassigning '''
    #    from satorineuron.init.start import getStart
    #    asyncThread = getStart().asyncThread
    #    if hasattr(self, 'timeout') and self.timeout is not None:
    #        asyncThread.cancelTask(self.timeout)
    #    self.timeout = asyncThread.delayedRun(
    #        task=self.finish,
    #        delay=60,
    #        msgId=msgId)

    def request(self, message: PeerMessage = None, datetime: dt.datetime = None):
        datetime = datetime or (
            datetimeFromString(message.observationTime)
            if message is not None else now())
        self.lastAsk = datetime
        msgId = self.parent.nextBroadcastId()
        # self.makeTimeout(msgId) # timeout pattern unreliable
        self.parent.requestOneObservation(
            datetime=datetime,
            msgId=msgId)
        self.messages[msgId]: list[PeerMessage] = []
        self.lastTime = time.time()

    def onResponse(self, message: PeerMessage):
        # we're running in to a problem, we're not always connected to everyone
        # in the group. so what we need to do instead is take the first response
        # and if there's a problem with this, we'll make it so the publisher of
        # the stream can sign every observation or something, just as we has the
        # chain of observations. So for now we're removing the popular method,
        # and we'll just trust the first person to respond.
        msg = self.inspectResponse(message)
        if msg is not None:
            self.handleMostPopular(msg)

    def inspectResponse(self, message: PeerMessage) -> Union[PeerMessage, None]:
        ''' if seen a response to this already, we discard, otherwise return '''
        if len(self.messages.get(message.msgId, [])) > 0:
            return None
        self.messages[message.msgId].append(message)
        return message

    def discoverPopularResponse(self, message: PeerMessage) -> Union[PeerMessage, None]:
        ''' 
        dep. superceded by inspectResponse.
        here we used to accumulate all responses and take the most popular
        but we're not using this anymore. 
        '''
        self.messages[message.msgId].append(message)
        messages = self.messages[message.msgId]
        mostPopularResponse = max(
            messages,
            key=lambda message: len([
                r for r in messages if r == message]))
        mostPopularResponseCount = len(
            [r for r in messages if r == mostPopularResponse])
        if (
            mostPopularResponseCount < len(self.parent.channels) / 2 or
            mostPopularResponse.data in [None, 'None', b'None']
        ):
            return None
        return mostPopularResponse

    def handleMostPopular(self, message: PeerMessage):
        '''
        if we don't have this observation yet:
            saves it to disk, and repeats the process with new time
        else: it tells the models data is updated, and cleans up.
        '''
        df = message.asDataFrame
        df.columns = ['value', 'hash']
        if self.parent.disk.isARoot(df):
            self.root = df
            if not self.parent.disk.matchesRoot(self.root, localDf=self.data):
                self.parent.disk.write(self.root)
        if message.hash not in self.hashes:
            self.parent.disk.append(df)
        # self.messagesToSave.append(message)
        # self.parent.tellModelsAboutNewHistory()
        self.initiate(message)

    def finishProcess(self):
        self.cleanup()

    def cleanup(self):
        ''' cleans up the gatherer '''
        # clean up messages
        self.parent.cleanChannels([key for key in self.messages.keys()])
        # clean up dataset
        success, df = self.parent.disk.cleanByHashes()
        if success and df is not None:
            # in order to have eventual consistency, we need to make sure that
            # if we have discovered a problem in our dataset we wipe the last
            # clean row this is because we may have a row missing in our dataset
            # that causes our dataset to look like it has good hashes, but it
            # actually doesn't. so we erase the last row, and if it was bad, we
            # will eventaully get to the point where we have a good row, common
            # to everyone, and move forwards from there. Not efficient but it
            # works for now.
            df = df.iloc[:-1]
            self.parent.disk.write(df)
        # self.refresh()


class Topic(Cached):
    ''' manages all our udp channels for a single topic '''

    def __init__(
        self,
        signedStreamId: SignedStreamId,
        localPort: int = None,
        outbox: Callable = None,
    ):
        self.channels: Channels = Channels({})
        self.localPort = localPort
        self.outbox = outbox
        # super().__init__(name=signedStreamId.topic(), port=localPort)
        self.name = signedStreamId.topic()
        self.signedStreamId = signedStreamId
        self.rows = -1
        self.broadcastId = 0
        self.gatherer = Gatherer(self)
        # self.periodicPurge()

    @property
    def streamId(self) -> StreamId:
        return self.signedStreamId.streamId

    def nextBroadcastId(self) -> str:
        self.broadcastId += 1
        return str(self.broadcastId)

    # no need to set socket because thats moved outside.
    # def setPort(self, port: int):
    #    self.port = port
    #    self.setSocket()
    #
    # def setSocket(self):
    #    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #    self.sock.bind(('0.0.0.0', self.port))

    def cleanChannels(self, msgIds: list[str]):
        for channel in self.channels.values():
            channel.cleanMessagesByIds(msgIds)

    def findChannel(self, remoteIp: str, remotePort: int) -> Union[Channel, None]:
        return self.channels.get((remoteIp, remotePort), None)

    def broadcast(self, cmd: str, msgs: list[str] = None):
        for channel in self.channels.values():
            channel.send(cmd, msgs)

    def setLocalPort(self, localPort: int):
        self.localPort = localPort

    # override
    def createChannel(self, remoteIp: str, remotePort: int):
        if self.findChannel(remoteIp, remotePort) is None:
            with self.channels:
                self.channels[(remoteIp, remotePort)] = Channel(
                    streamId=self.streamId,
                    remoteIp=remoteIp,
                    remotePort=remotePort,
                    parent=self)

    def send(self, remoteIp: str, remotePort: int, cmd: str, msgs: list[str] = None):
        # def makePayload(cmd: str, msgs: list[str] = None) -> Union[bytes, None]:
        #     if not PeerProtocol.isValidCommand(cmd):
        #         logging.error('command not valid', cmd, print=True)
        #         return None
        #     try:
        #         return PeerProtocol.compile([
        #             x for x in [cmd, *(msgs or [])]
        #             if isinstance(x, int) or (x is not None and len(x) > 0)])
        #     except Exception as e:
        #         logging.warning('err w/ payload', e, cmd, msgs)

        # def send(self, cmd: str, msg: PeerMessage = None):
        #     # TODO: make this take a PeerMessage object and do that everywhere
        #     payload = cmd
        #     self.topicSocket.sendto(payload, (self.peerIp, self.port))
        #     self.topicSocket.sendto(msg.asJsonStr.decode(),
        #                             (self.peerIp, self.port))
        # convert to bytes message

        # print('in send', remoteIp, remotePort, cmd, msgs)
        logging.info(
            'outgoing peer message',
            (self.localPort, remoteIp, remotePort, cmd),
            print=True)
        self.outbox((self.localPort, remoteIp, remotePort, cmd))

    def requestOneObservation(self, datetime: dt.datetime, msgId: int):
        '''
        ask all the channels for the latest observation before the datetime
        '''
        msg = PeerProtocol.request(
            datetime,
            subcmd=PeerProtocol.observationSub,
            msgId=msgId)
        # with self.channels:
        for channel in self.channels.values():
            channel.send(msg)

    def getLocalObservation(self, timestamp: str) -> SingleObservation:
        ''' returns the observation after the timestamp '''
        if (
            self.data is None or
            (isinstance(self.data, pd.DataFrame) and self.data.empty)
        ):
            return SingleObservation(None, None, None)
        df = self.data[self.data.index > timestamp]
        if df.empty:
            return SingleObservation(None, None, None)
        success, _ = self.disk.validateAllHashes(self.data)
        if not success:
            if self.signedStreamId.publish:
                self.disk.write(self.disk.hashDataFrame(self.data))
            return SingleObservation(None, None, None)
        return SingleObservation(df.index[0], df['value'].values[0], df['hash'].values[0])

    def getLocalObservationBefore(self, timestamp: str) -> SingleObservation:
        ''' returns the observation before the timestamp '''
        # this should insdead get one from the engine. or if that fails,
        # pull it directly from disk without a caching mechanism
        # the reason we have a caching mechanism in the disk is to know where
        # to pull (what chunk) rather than reading in the whole file each time
        # we want one row. so we should get that working first, then point to
        # the engine data manager, if we want.

        before = self.disk.getObservationBefore(timestamp)
        if (
            before is None or
            (isinstance(before, pd.DataFrame) and before.empty)
        ):
            return SingleObservation(None, None, None)
        # value, hash are the only columns in the dataframe now
        # if self.streamId.stream in before.columns:
        #    column = self.streamId.stream
        # elif self.streamId.target in before.columns:
        #    column = self.streamId.stream
        # else:
        #    column = before.columns[0]
        try:
            # row = before.loc[before.index < timestamp].iloc[-1]
            row = before.loc[before.index < timestamp].tail(1)
            if (row.shape[0] == 0):
                return SingleObservation(None, None, None)
            if (row.shape[0] == 1):
                return SingleObservation(row.index[0], row['value'].values[0], row['hash'].values[0])
            # only send 1 row?
            return SingleObservation(row.index[-1], row['value'].values[-1], row['hash'].values[-1])
        except IndexError as _:
            return SingleObservation(None, None, None)

    def getLocalCount(self, timestamp: str) -> Union[int, None]:
        ''' returns the count of observations before the timestamp '''
        if timestamp is None:
            return self.disk.getRowCounts()
        try:
            rows = self.data.loc[self.data.index < timestamp]
            return rows.shape[0]
        except IndexError as _:
            return 0

    def getLocalHash(self, timestamp: str) -> Union[int, None]:
        ''' returns the count of observations before the timestamp '''
        if self.disk.exists():
            self.disk.getHashBefore(timestamp)
        else:
            if self.data is None or (
                isinstance(self.data, pd.DataFrame) and self.data.empty
            ):
                return None
            try:
                rows = self.data.loc[self.data.index < timestamp]
                return rows.shape[0]
            except IndexError as _:
                return 0

    def updateHistoryIncrementally(self):
        ''' 
        starts the process of getting the history of this topic incrementally.
        '''
        self.gatherer.prepare()

    def tellModelsAboutNewHistory(self):
        ''' 
        tells the models to go get their data again.
        (this should probably be in model manager or engine or something)
        '''
        from satorineuron.init.start import getStart
        for model in getStart().engine.models:
            if (
                model.variable == self.streamId or
                self.streamId in model.targets
            ):
                model.inputsUpdated.on_next(True)


class Topics(LockableDict[str, Topic]):
    '''
    iterating over this dictionary within a context manager is thread safe, 
    example: 
        with topics:
            topics['topic'] = Topic('name', 1234)
    '''
