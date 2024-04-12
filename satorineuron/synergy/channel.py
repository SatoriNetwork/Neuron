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
from typing import Union
import time
import threading
import pandas as pd
from queue import Queue, Empty
from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.api.disk import Cached
from satorilib.api.hash import hashRow
from satorilib.api.time import datetimeToTimestamp, earliestDate, isValidTimestamp
from satorineuron.synergy.domain.objects import Vesicle, Punch, SingleObservation, ObservationRequest
from satorineuron.synergy.domain.envelope import Envelope, Vesicle


class Axon(Cached):
    ''' get messages from the peer and send messages to them '''

    def __init__(self, streamId: StreamId, ip: str):
        self.streamId = streamId
        self.ip = ip
        self.send(Punch())

    def send(self, data: Vesicle):
        ''' sends data to the peer '''
        from satorineuron.init.start import getStart
        getStart().udpQueue.put(Envelope(ip=self.ip, vesicle=data))

    def receive(self, message: bytes) -> Union[Vesicle, None]:
        '''Handle incoming messages. Must be implemented by subclasses.'''
        logging.debug('received message:', message, color='teal')
        vesicle = None
        try:
            vesicle = Vesicle.build(message)
        except Exception as e:
            logging.debug('unable to prase peer message:', e, message)
        return vesicle


class SynapseSubscriber(Axon):
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
        vesicle: Vesicle = super().receive(message)
        if not isinstance(vesicle, SingleObservation) or not vesicle.isValid:
            logging.error('peer msg failure', type(vesicle), vesicle.isValid)
            return  # unable to parse
        # here we can extract some context or something from vesicle.context
        self.inbox.put(vesicle)

    def main(self):
        ''' send the data to the subscriber '''
        self.thread = threading.Thread(target=self.processObservations)
        self.thread.start()

    def processObservations(self):
        ''' save them all to disk '''

        def lastTime() -> ObservationRequest:
            if self.disk.cache.empty:
                print('sending beginning of time...')
                return ObservationRequest(time='', first=True)
            print('sending latest...')
            return ObservationRequest(time=self.disk.cache.index[-1])

        def save(observation: SingleObservation):
            ''' save the data to disk, if anything goes wrong request a time '''

            def lastHash():
                if self.disk.cache.empty:
                    return ''
                else:
                    return self.disk.cache.iloc[-1].hash

            def validateCache():
                success, df = self.disk.validateAllHashes()
                print(df)
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
                value=str(observation.data),
            ) == observation.hash:
                success, _, _, = self.disk.appendByAttributes(
                    timestamp=observation.time,
                    value=observation.data,
                    observationHash=observation.hash)
                if not success:
                    logging.debug('not success',
                                  observation.hash, color='red')
                    validateCache()
                    self.send(lastTime())
                    clearQueue()
                    # success, df = self.disk.verifyHashesReturnLastGood()
                    # if isinstance(df, pd.DataFrame) and len(df) > 0:
                    #    self.send(df.index[-1])
            else:
                logging.debug('doing nothing', color='teal')
                # self.disk.overwriteClean()
                # self.send(lastTime())

        def handle(observation: SingleObservation):
            logging.debug('handling:', observation.hash, color='green')
            if not self.disk.cache.empty and observation.isFirst:
                if (
                    observation.time == self.disk.cache.index[0] and
                    observation.data == str(self.disk.cache.iloc[0].value) and
                    observation.hash == self.disk.cache.iloc[0].hash
                ):
                    logging.debug('overwriting!',
                                  observation.hash, color='red')
                    self.disk.overwriteClean()
                    self.send(lastTime())
                else:
                    logging.debug('clearing!', observation.hash, color='red')
                    self.disk.clear()
                    self.send(ObservationRequest(time='', first=True))
            else:
                save(observation)

        if self.inbox.empty():
            self.send(ObservationRequest(time='', first=True))
        while True:
            handle(self.inbox.get())


class SynapsePublisher(Axon):
    ''' 
    get messages from the peer and send messages to them. the message will 
    contain the last known good data. this publisher will then take that as a
    starting point and send all the data after that to the subscriber. that is
    until it gets interrupted.
    '''

    def __init__(self, streamId: StreamId, ip: str):
        super().__init__(streamId, ip)
        self.ts: str = datetimeToTimestamp(earliestDate())
        self.running = False
        self.first = self.disk.cache.index[0] if not self.disk.cache.empty else None
        # self.main()

    def receive(self, message: bytes):
        ''' message will be the timestamp after which to start sending data '''
        if len(self.disk.cache.index) == 0:
            return  # nothing to send
        vesicle: Vesicle = super().receive(message)
        if not isinstance(vesicle, ObservationRequest) or not vesicle.isValid:
            return
        ts = vesicle.time
        if vesicle.isValid:
            if isValidTimestamp(ts):
                self.ts = vesicle.time
            elif vesicle.first:
                self.ts = datetimeToTimestamp(earliestDate())
            elif vesicle.latest and len(self.disk.cache.index) > 1:
                self.ts = self.disk.cache.index[-2]
            elif vesicle.middle:
                middle_index = len(self.disk.cache.index) // 2
                self.ts = self.disk.cache.index[middle_index]
            if not self.running:
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
                logging.debug(
                    'first', self.first, row.index[0], self.first == row.index[0], color='yellow')
                return SingleObservation(
                    time=row.index[0],
                    data=row['value'].values[0],
                    hash=row['hash'].values[0],
                    isFirst=self.first == row.index[0])
            logging.debug(
                'first', self.first, row.index[0], self.first == row.index[0], color='magenta')
            return SingleObservation(
                time=row.index[0],
                data=row['value'].values[0],
                hash=row['hash'].values[0],
                isFirst=self.first == row.index[0])

        self.running = True
        while self.ts != self.disk.cache.index[-1]:
            ts = self.ts
            time.sleep(0.33)  # cool down
            try:
                observation = getObservationAfter(ts)
            except Exception as _:
                break
            self.send(observation)
            if self.ts == ts:
                self.ts = observation.time
        self.running = False
