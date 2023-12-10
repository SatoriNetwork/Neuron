from typing import Union, Callable
import datetime as dt
import pandas as pd
from satorilib import logging
from satorilib.api.disk import Disk
from satorilib.api.time import datetimeFromString, now
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
        1. ask all channels for the observation
        2. give every channel a call back once they get a messge
        3. on the call back get the most popular message from all replies
        4. have a timeout here which will force it to move on (using timer)
        5. once it has the most popular reply it either:
            if we don't have this observation yet:
                saves it to disk, and repeats the process with new time
            else: it tells the models data is updated, and cleans up.    
    '''

    def __init__(self, parent: 'Topic'):
        self.parent = parent
        self.refresh()

    def refresh(self):
        self.timeout = None
        self.messages: dict[str, list[PeerMessage]] = {}
        self.messagesToSave = PeerMessages([])
        self.getHashes()

    def getHashes(self):
        self.data = self.parent.disk.read()
        if self.data is not None:
            self.hashes = self.data.hash.values
        else:
            self.hashes = []

    def request(self, message: PeerMessage = None, datetime: dt.datetime = None):
        from satorineuron.init.start import getStart
        msgId = self.parent.nextBroadcastId()
        self.timeout = getStart().asyncThread.delayedRun(
            task=self.finish, delay=60, args=[msgId])
        self.parent.requestOneObservation(
            datetime=datetime or (
                datetimeFromString(message.observationTime)
                if message is not None else now()),
            msgId=msgId)
        self.messages[msgId]: list[PeerMessage] = []

    def onResponse(self, message: PeerMessage):
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
        if message.hash in self.hashes:
            self.finishProcess()
        else:
            self.messagesToSave.append(message)
            self.request(message)

    def finishProcess(self):
        self.parent.disk.append(self.messagesToSave.msgsToDataframe())
        self.parent.tellModelsAboutNewHistory()
        self.cleanup()

    def finish(self, msgId: int):
        '''
        if we haven't recieved enough responses by now, we just move on. 
        '''
        if (
            len(self.messagesToSave) > 0 and
            msgId not in [msg.msgId for msg in self.messagesToSave]
        ):
            self.finishProcess()

    def cleanup(self):
        ''' cleans up the gatherer '''
        self.parent.cleanChannels([key for key in self.messages.keys()])
        self.refresh()


class Topic():
    ''' manages all our udp channels for a single topic '''

    def __init__(
        self,
        signedStreamId: SignedStreamId,
        localPort: int = None,
        outbox: Callable = None,
    ):
        logging.debug('---TOPIC---', signedStreamId.stream, print='magenta')
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

        # self.periodicPurge()

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
        logging.debug('in create', remoteIp, remotePort, print='blue')
        if self.findChannel(remoteIp, remotePort) is None:
            logging.debug('find channel', print='magenta')
            with self.channels:
                logging.debug('making channel', print='magenta')
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
        payload = b'payload'
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
        ''' returns the observation before the timestamp '''
        self.data = self.disk.getObservationBefore(timestamp)
        if (
            not hasattr(self, 'data') or
            not hasattr(self, 'hash') or
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
            if (row.shape[0] == 0):
                return SingleObservation(None, None, None)
            if (row.shape[0] == 1):
                return SingleObservation(row.index, row['value'].values[0], row['hash'].values[0])
            row = self.data.loc[self.data.index < timestamp].iloc[-1]
            return SingleObservation(row.index, row['value'], row['hash'])
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
        self.gatherer.request()

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
