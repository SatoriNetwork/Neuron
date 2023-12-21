from typing import Union, Callable
import time
import datetime as dt
import pandas as pd
from satorilib import logging
from satorilib.api.disk import Disk
from satorilib.api.time import datetimeFromString, now, earliestDate
from satorirendezvous.lib.lock import LockableDict
from satorineuron.rendezvous.structs.message import PeerMessage, PeerMessages
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
        # self.lastHeard = None
        self.timeout = None
        self.messages: dict[str, list[PeerMessage]] = {}
        self.getData()

    def getData(self):
        self.parent.getData()

    @property
    def data(self):
        return self.parent.data

    @property
    def hashes(self):
        if self.data is not None:
            return self.data.hash.values
        return []

    def prepare(self):
        ''' we verify that our first row (the root) matches the consensus '''
        self.request(datetime=earliestDate())
        # if self.data is None or self.data.empty:
        # if self.data.shape[0] > 1:
        #    trunk = self.data.iloc[[1]]
        #    logging.debug('in prepare', trunk, print='blue')
        #    self.request(datetime=earliestDate())
        # else:
        #    self.request(datetime=earliestDate())
        self.startSupervisor()

    def startSupervisor(self):
        ''' incase we lose connection, try again in 60 seconds '''
        from satorineuron.init.start import getStart
        asyncThread = getStart().asyncThread
        if hasattr(self, 'supervisor') and self.supervisor is not None:
            asyncThread.cancelTask(self.supervisor)
        self.supervisor = asyncThread.repeatRun(
            task=self.initiateIfIdle,
            interval=60)

    def initiateIfIdle(self):
        if hasattr(self, 'lastHeard') and self.lastHeard < time.time() - 60:
            logging.debug('inititating from idle', self.lastHeard,
                          time.time() - 60, print='blue')
            self.cleanup()
            self.initiate()

    def initiate(self, message: PeerMessage = None):

        def askForNextData():
            return self.request(message)

        if self.data is None or self.data.empty:
            logging.debug('NONE or EMPTY???', print='magenta')
            return askForNextData()
        if (
            isinstance(self.root, pd.DataFrame) and
            self.parent.disk.matchesRoot(self.root, localDf=self.data)
        ):
            success, row = self.parent.disk.validateAllHashes(self.data)
            if not success:
                logging.debug('NOT SUCCESS - Row', row, print='magenta')
                return self.request(datetime=datetimeFromString(row.index[0]))
            lastTimeStamp = datetimeFromString(self.data.index[-1])
            logging.debug('lastTimeStamp ?= self.lastAsk', lastTimeStamp,
                          '==' if lastTimeStamp == self.lastAsk else '!=', self.lastAsk, print='red')
            if lastTimeStamp != self.lastAsk:
                return self.request(datetime=lastTimeStamp)
            return self.finishProcess()
        logging.debug('BAD ROOT???', print='magenta')
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

    def onResponse(self, message: PeerMessage):
        self.lastHeard = time.time()
        msg = self.discoverPopularResponse(message)
        if msg is not None:
            self.handleMostPopular(msg)

    def discoverPopularResponse(self, message: PeerMessage) -> Union[PeerMessage, None]:
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
        if self.parent.streamId.stream == 'coinbaseADA-USD':
            logging.debug('handleMostPopular 1:',
                          df,
                          self.parent.disk.isARoot(df),
                          hasattr(self, 'root'), (
                              hasattr(self, 'root') and
                              isinstance(self.root, pd.DataFrame) and
                              self.data.sort_index().iloc[[0]].equals(self.root)),
                          self.parent.disk.matchesRoot(df, localDf=self.data),
                          self.parent.disk.validateAllHashes(),
                          print='teal')
        if self.parent.disk.isARoot(df):
            self.root = df
            if not self.parent.disk.matchesRoot(self.root, localDf=self.data):
                self.parent.disk.write(self.root)
        if message.hash not in self.hashes:
            self.parent.disk.append(df)
        self.getData()
        # self.messagesToSave.append(message)
        # self.parent.tellModelsAboutNewHistory()
        self.initiate(message)

    def finishProcess(self):
        logging.debug('FINISHING PROCESS', print='red')
        self.cleanup()

    def cleanup(self):
        ''' cleans up the gatherer '''
        # clean up messages
        self.parent.cleanChannels([key for key in self.messages.keys()])
        # clean up dataset
        success, df = self.parent.disk.cleanByHashes()
        logging.debug('strema:', self.parent.streamId, print='red')
        logging.debug('CLEANING BY HASH -- success df',
                      success,
                      df.head() if isinstance(df, pd.DataFrame) else 'None',
                      print='red')
        if success and df is not None:
            logging.debug('writing', print='red')
            self.parent.disk.write(df)
        # self.refresh()


class Topic():
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
        self.streamId = signedStreamId.streamId
        self.disk = Disk(id=self.streamId)
        self.rows = -1
        self.broadcastId = 0
        self.gatherer = Gatherer(self)
        self.getData()
        # self.periodicPurge()

    def getData(self):
        self.data = self.disk.read()
    #    self.verifyData()

    # def verifyData(self):
    #    if not self.disk.validateAllHashes(self.data):
    #        if self.disk.write(self.disk.hashDataFrame(self.data)):
    #            self.getData()

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
        #     logging.debug('make payload cmd', cmd, print='red')
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
        #     logging.debug('sent pyaload:', payload, print='magenta')
        #     self.topicSocket.sendto(payload, (self.peerIp, self.port))
        #     self.topicSocket.sendto(msg.asJsonStr.decode(),
        #                             (self.peerIp, self.port))
        # convert to bytes message
        print('in send', remoteIp, remotePort, cmd, msgs)
        self.outbox((self.localPort, remoteIp, remotePort, cmd))

    def requestOneObservation(self, datetime: dt.datetime, msgId: int):
        '''
        ask all the channels for the latest observation before the datetime
        '''
        msg = PeerProtocol.request(
            datetime,
            subcmd=PeerProtocol.observationSub,
            msgId=msgId)
        with self.channels:
            for channel in self.channels.values():
                channel.send(msg)

    def getLocalObservation(self, timestamp: str) -> SingleObservation:
        ''' returns the observation after the timestamp '''
        # TODO: instead of getting the data all the time we should have a cache
        # that is the middle layer between the code and hte disk, in ram. We can
        # access it, and the engine can access it. it should be the source of
        # truth.
        self.getData()
        logging.debug('getLocalObservation', self.data,
                      timestamp, print='magenta')
        if (
            not hasattr(self, 'data') or
            self.data is None or
            (isinstance(self.data, pd.DataFrame) and self.data.empty)
        ):
            logging.debug('getLocalObservation1', print='magenta')
            return SingleObservation(None, None, None)
        df = self.data[self.data.index > timestamp]
        if df.empty:
            logging.debug('getLocalObservation2', print='magenta')
            return SingleObservation(None, None, None)
        logging.debug('getLocalObservation3', print='magenta')
        return SingleObservation(df.index[0], df['value'].values[0], df['hash'].values[0])

    def getLocalObservationBefore(self, timestamp: str) -> SingleObservation:
        ''' returns the observation before the timestamp '''
        # this should insdead get one from the engine. or if that fails,
        # pull it directly from disk without a caching mechanism
        # the reason we have a caching mechanism in the disk is to know where
        # to pull (what chunk) rather than reading in the whole file each time
        # we want one row. so we should get that working first, then point to
        # the engine data manager, if we want.

        self.data = self.disk.getObservationBefore(timestamp)
        if (
            not hasattr(self, 'data') or
            # not hasattr(self, 'hash') or
            self.data is None or
            (isinstance(self.data, pd.DataFrame) and self.data.empty)
        ):
            return SingleObservation(None, None, None)
        # value, hash are the only columns in the dataframe now
        # if self.streamId.stream in self.data.columns:
        #    column = self.streamId.stream
        # elif self.streamId.target in self.data.columns:
        #    column = self.streamId.stream
        # else:
        #    column = self.data.columns[0]
        try:
            # row = self.data.loc[self.data.index < timestamp].iloc[-1]
            row = self.data.loc[self.data.index < timestamp].tail(1)
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
        if self.disk.exists() and self.disk.getRowCounts() > self.rows:
            self.data = self.disk.read()
        if not hasattr(self, 'data') or self.data is None or (
            isinstance(self.data, pd.DataFrame) and self.data.empty
        ):
            return None
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
            if not hasattr(self, 'data') or self.data is None or (
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
