from typing import Union, Callable
import time
import datetime as dt
import pandas as pd
from satorilib import logging
from satorilib.api.disk import Disk
from satorilib.api.time import now
from satorirendezvous.lib.lock import LockableDict
from satorineuron.rendezvous.structs.message import PeerMessage
from satorineuron.rendezvous.structs.protocol import PeerProtocol
from satorineuron.rendezvous.structs.domain import SignedStreamId
from satorineuron.rendezvous.channel import Channel, Channels


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
        self.disk = Disk(id=self.signedStreamId.streamId)
        self.rows = -1
        # self.periodicPurge()

    # don't need to perge because we don't save these messages anymore
    # def periodicPurge(self):
    #    self.purger = threading.Thread(target=self.purge, daemon=True)
    #    self.purger.start()
    #
    # def purge(self):
    #    while True:
    #        then = now()
    #        time.sleep(60*60*24)
    #        with self.channels:
    #            self.channels = [
    #                channel for channel in self.channels
    #                if len(channel.messagesAfter(time=then)) > 0]

    # no need to set socket because thats moved outside.
    # def setPort(self, port: int):
    #    self.port = port
    #    self.setSocket()
    #
    # def setSocket(self):
    #    self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    #    self.sock.bind(('0.0.0.0', self.port))

    def findChannel(self, remoteIp: str, remotePort: int) -> Union[Channel, None]:
        return self.channels.get((remoteIp, remotePort), None)

    def broadcast(self, cmd: str, msgs: list[str] = None):
        for channel in self.channels:
            channel.send(cmd, msgs)

    def setLocalPort(self, localPort: int):
        self.localPort = localPort

    # override
    def create(self, remoteIp: str, remotePort: int):
        logging.debug('in create', remoteIp, remotePort, print='blue')
        if self.findChannel(remoteIp, remotePort) is None:
            logging.debug('find channel', print='magenta')
            with self.channels:
                logging.debug('making channel', print='magenta')
                self.channels[(remoteIp, remotePort)] = Channel(
                    streamId=self.signedStreamId.streamId,
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
        payload = b'payload'
        self.outbox((self.localPort, remoteIp, remotePort, payload))

    def getOneObservation(self, datetime: dt.datetime) -> PeerMessage:
        # todo: giving an observation must include hash.
        ''' time is of the most recent observation '''
        msg = PeerProtocol.request(
            datetime, subcmd=PeerProtocol.observationSub)
        sentTime = now()
        with self.channels:
            for channel in self.channels:
                channel.send(msg)
        time.sleep(5)  # wait for responses, natural throttle
        with self.channels:
            responses: list[Union[PeerMessage, None]] = [
                channel.mostRecentResponse(channel.responseAfter(sentTime))
                for channel in self.channels]
        responses = [
            response for response in responses
            if response is not None]
        mostPopularResponse = max(
            responses,
            key=lambda response: len([
                r for r in responses if r == response]))
        # here we could enforce a threshold, like super majority or something,
        # by saying this message must make up at least 67% of the responses
        # but I don't think it's necessary for now.
        return mostPopularResponse

    def getLocalObservation(
        self, timestamp: str,
    ) -> Union[tuple[Union[str, None], Union[str, None], Union[str, None]], None]:
        ''' returns the observation before the timestamp '''
        self.data = self.disk.getObservationBefore(timestamp)
        if (
            not hasattr(self, 'data') or
            not hasattr(self, 'hash') or
            self.data is None or
            (isinstance(self.data, pd.DataFrame) and self.data.empty)
        ):
            return None
        # value, hash are the only columns in the dataframe now
        # if self.signedStreamId.streamId.stream in self.data.columns:
        #    column = self.signedStreamId.streamId.stream
        # elif self.signedStreamId.streamId.target in self.data.columns:
        #    column = self.signedStreamId.streamId.stream
        # else:
        #    column = self.data.columns[0]
        try:
            if (row.shape[0] == 0):
                return (None, None, None)
            if (row.shape[0] == 1):
                return (row.index, row['value'].values[0], row['hash'].values[0])
            row = self.data.loc[self.data.index < timestamp].iloc[-1]
            return (row.index, row['value'], row['hash'])
        except IndexError as _:
            return (None, None, None)

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


class Topics(LockableDict[str, Topic]):
    '''
    iterating over this dictionary within a context manager is thread safe, 
    example: 
        with topics:
            topics['topic'] = Topic('name', 1234)
    '''
