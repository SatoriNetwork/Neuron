'''
once connected, the publisher will begin sending data to the subscriber starting
with the hash request. it will not wait for a response. it will merely continue 
to send the data to the subscriber until interrupted, at which time it will 
restart the process from the hash requested (in the interruption message).

the subscriber will accept data, checking that the new hash and data match the 
running hash and if it doesn't the subscriber will send a message to the server
with the lastest good hash received. it will ignore incoming data until it 
receives that hash.
'''

import time
import threading
import pandas as pd
from queue import Queue, Empty
from satorilib.concepts import StreamId
from satorilib.api.disk import Cached
from satorilib.api.hash import hashRow
from satorilib.api.time import datetimeToTimestamp, earliestDate, isValidTimestamp
from satorineuron.synergy.domain import SingleObservation, SynergyMsg


class SynergyChannel(Cached):
    ''' get messages from the peer and send messages to them '''

    def __init__(self, streamId: StreamId, ip: str):
        self.streamId = streamId
        self.ip = ip
        self.send('punch')

    def send(self, data: str):
        ''' sends data to the peer '''
        from satorineuron.init.start import getStart
        getStart().udpQueue.put(SynergyMsg(ip=self.ip, data=data).toJson())

    def receive(self, message: bytes):
        '''Handle incoming messages. Must be implemented by subclasses.'''
        pass


class SynergySubscriber(SynergyChannel):
    ''' 
    get messages from the peer and send messages to them, takes messages and 
    saves the data to disk using Cached, if there's a problem it sends a message
    back to the peer asking for it to start over at the last known good hash.
    '''

    def __init__(self, streamId: StreamId, ip: str):
        super().__init__(streamId, ip)
        self.inbox = Queue()
        self.main()

    def receive(self, message: bytes):
        ''' message that will contain data to save, add to inbox '''
        print('received message:', message)
        observation = SingleObservation.fromMessage(message)
        if observation.isValid:
            self.inbox.put(observation)

    def main(self):
        ''' send the data to the subscriber '''
        self.thread = threading.Thread(target=self.processObservations)
        self.thread.start()

    def processObservations(self):
        ''' save them all to disk '''

        def lastTime():
            if self.disk.cache.empty:
                return datetimeToTimestamp(earliestDate())
            else:
                return self.disk.cache.index[-1]

        def save(observation: SingleObservation):
            ''' save the data to disk, if anything goes wrong request a time '''

            def lastHash():
                if self.disk.cache.empty:
                    return ''
                else:
                    return self.disk.cache.iloc[[-1]].hash

            def validateCache():
                success, _ = self.disk.validateAllHashes()
                if not success:
                    self.disk.saveHashes()

            def clearQueue():
                try:
                    while True:
                        self.inbox.get_nowait()
                except Empty:
                    pass

            if hashRow(
                priorRowHash=lastHash(),
                ts=observation.time,
                value=observation.data,
            ) == observation.hash:
                success, _, _, = self.disk.appendByAttributes(
                    timestamp=observation.time,
                    value=observation.data,
                    observationHash=observation.hash)
            if not success:
                validateCache()
                self.send(lastTime())
                clearQueue()
                # success, df = self.disk.verifyHashesReturnLastGood()
                # if isinstance(df, pd.DataFrame) and len(df) > 0:
                #    self.send(df.index[-1])

        if self.inbox.empty():
            self.send(lastTime())
        while True:
            save(self.inbox.get())


class SynergyPublisher(SynergyChannel):
    ''' 
    get messages from the peer and send messages to them. the message will 
    contain the last known good data. this publisher will then take that as a
    starting point and send all the data after that to the subscriber. that is
    until it gets interrupted.
    '''

    def __init__(self, streamId: StreamId, ip: str):
        super().__init__(streamId, ip)
        self.ts: str = datetimeToTimestamp(earliestDate())
        self.thread = None
        # self.main()

    def receive(self, message: bytes):
        ''' message will be the timestamp after which to start sending data '''
        print('received message:', message)
        if isinstance(message, bytes):
            ts = message.decode()
        if isinstance(message, str):
            ts = message
        if isValidTimestamp(ts):
            self.ts = ts
            if self.thread is not None:
                self.main()

    def main(self):
        ''' send the data to the subscriber '''
        self.thread = threading.Thread(target=self.runUntilFinished)
        self.thread.start()

    def runUntilFinished(self):
        ''' send the data to the subscriber '''

        def getObservationAfter(timestamp: str) -> SingleObservation:
            ''' get the next observation after the time '''
            after = self.disk.getObservationAfter(timestamp)
            if (
                after is None or
                (isinstance(after, pd.DataFrame) and after.empty)
            ):
                raise Exception('no data')
            row = after.loc[after.index > timestamp].head(1)
            if (row.shape[0] == 0):
                raise Exception('no data')
            if (row.shape[0] == 1):
                return SingleObservation(row.index[0], row['value'].values[0], row['hash'].values[0])
            return SingleObservation(row.index[0], row['value'].values[0], row['hash'].values[0])

        # wait for the subscriber to be ready (or trigger only on msg)
        # time.sleep(15)
        while self.ts != self.disk.cache.index[-1]:
            ts = self.ts
            time.sleep(0.33)  # cool down
            try:
                observation = getObservationAfter(ts)
            except Exception as _:
                break
            self.send(observation.toJson())
            if self.ts == ts:
                self.ts = observation.time
