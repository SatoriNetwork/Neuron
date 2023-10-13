from typing import Union
from time import sleep
import datetime as dt
import pandas as pd
from satorilib.api.disk import Disk
from satorilib.api.time import now
from satorineuron.rendezvous.structs.message import PeerMessage
from satorineuron.rendezvous.structs.protocol import PeerProtocol
from satorineuron.rendezvous.structs.domain import SignedStreamId
from satorineuron.rendezvous.channel import Channel, Channels
from satorirendezvous.lib.lock import LockableDict
from satorirendezvous.peer.p2p.topic import Topic as BaseTopic


class Topic(BaseTopic):
    ''' manages all our udp channels for a single topic '''

    def __init__(self, signedStreamId: SignedStreamId, port: int, parent: 'RendezvousPeer'):
        self.channels: Channels = Channels([])
        super().__init__(name=signedStreamId.topic(), port=port)
        self.signedStreamId = signedStreamId
        self.disk = Disk(id=self.signedStreamId.streamId)
        self.rows = -1
        self.parent = parent

    # override
    def create(self, ip: str, port: int, localPort: int):
        if self.port is None:
            self.setPort(localPort)
        if self.findChannel(ip, port, localPort) is None:
            with self.channels:
                self.channels.append(Channel(
                    streamId=self.signedStreamId.streamId,
                    ip=ip,
                    port=port,
                    localPort=localPort,
                    topicSocket=self.sock,
                    parent=self))

    def getOneObservation(self, time: dt.datetime) -> PeerMessage:
        # todo: giving an observation must include hash.
        ''' time is of the most recent observation '''
        msg = PeerProtocol.request(time, subcmd=PeerProtocol.observationSub)
        sentTime = now()
        with self.channels:
            for channel in self.channels:
                channel.send(msg)
        sleep(5)  # wait for responses, natural throttle
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
        rendezvousEngine = self.parent.parent  # todo remove parents.
        hashes = rendezvousEngine.start.engine.data.hashes[self.signedStreamId.streamId.generateHash]
        # get the row of the dataframe with a timestamp index that is just before the given timestamp
        # get the rows between that timestamp and the given timestamp from disk
        # generate all the hashes
        # return the hash just before the given timestamp
        # jesus Christ, we should keep all these hashes in memory? just pull from the disk everytime?
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
