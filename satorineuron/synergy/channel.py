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
from satorineuron.synergy.domain.objects import Vesicle, SingleObservation, ObservationRequest
from satorisynapse import Envelope, Ping


class Axon(Cached):
    ''' get messages from the peer and send messages to them '''

    def __init__(self, streamId: StreamId, ip: str):
        self.streamId = streamId
        self.ip = ip
        self.send(Ping())

    def send(self, data: Vesicle):
        ''' sends data to the peer '''
        # logging.debug('sending synapse message:', data.toDict, color='yellow')
        from satorineuron.init.start import getStart
        getStart().udpQueue.put(Envelope(ip=self.ip, vesicle=data))

    def receive(self, message: bytes) -> Union[Vesicle, None]:
        '''Handle incoming messages. Must be implemented by subclasses.'''
        # logging.info('received synapse message:',
        #             message.decode(), color='grey')
        vesicle = None
        try:
            vesicle = Vesicle.build(message)
        except Exception as e:
            logging.error('unable to prase peer message:', e, message)
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
        self.requested: dict[str, bool] = {}
        self.main()

    def receive(self, message: bytes):
        ''' message that will contain data to save, add to inbox '''
        vesicle: Vesicle = super().receive(message)
        if not isinstance(vesicle, SingleObservation) or not vesicle.isValid:
            # 2024-04-20 15:37:07,419 - ERROR - peer msg failure <class 'satorisynapse.lib.domain.Ping'> True b'{"className": "Ping", "ping": false}'
            # logging.error('peer msg failure', type(
            #    vesicle), vesicle.isValid, message)
            return  # unable to parse
        # here we can extract some context or something from vesicle.context
        self.inbox.put(vesicle)

    def request(self, observationRequest: ObservationRequest):
        ''' request the last known good hash from the peer '''
        self.requested[observationRequest.time] = False
        self.send(observationRequest)

    def main(self):
        ''' send the data to the subscriber '''
        self.thread = threading.Thread(target=self.processObservations)
        self.thread.start()

    def processObservations(self):
        ''' save them all to disk '''

        def lastTime() -> ObservationRequest:
            if self.disk.cache.empty:
                return ObservationRequest(time='', first=True)
            return ObservationRequest(time=self.disk.cache.index[-1])

        def validateCache():
            self.disk.modifyBasedValidation(
                *self.disk.performValidation(entire=True))

        def save(observation: SingleObservation) -> bool:
            ''' save the data to disk, if anything goes wrong request a time '''

            def lastHash():
                if self.disk.cache.empty:
                    return ''
                else:
                    return self.disk.cache.iloc[-1].hash

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
                if observation.responseTo in self.requested and self.requested[observation.responseTo] == False:
                    self.requested[observation.responseTo] = True
                cachedResult = self.disk.appendByAttributes(
                    timestamp=observation.time,
                    value=observation.data,
                    observationHash=observation.hash)
                if cachedResult.success and cachedResult.validated:
                    return True
            elif self.requested.get(observation.responseTo, False):
                self.requested[observation.responseTo] = False
            validateCache()
            self.request(lastTime())
            self.clearIt = clearQueue()
            return False

        def handle(observation: SingleObservation):
            if observation.isFirst and not self.disk.cache.empty:
                if (
                    observation.time == self.disk.cache.index[0] and
                    str(observation.data) == str(self.disk.cache.iloc[0].value) and
                    observation.hash == self.disk.cache.iloc[0].hash
                ):
                    validateCache()
                    self.request(lastTime())
                else:
                    self.disk.clear()
                    self.request(ObservationRequest(time='', first=True))
            else:
                if observation.responseTo in self.requested and self.requested[observation.responseTo] == True and observation.hash in self.disk.cache.hash.values:
                    # ignore, we've already received an answer on to this request
                    return
                if save(observation) and observation.isLatest:
                    from satorineuron.init.start import getStart
                    getStart().repullFor(self.streamId)

        if self.inbox.empty():
            self.request(ObservationRequest(time='', first=True))
        i = 0
        while True:
            handle(self.inbox.get())
            i += 1
            if i % 100 == 0:
                self.send(Ping())


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
        self.last = self.disk.cache.index[-1] if not self.disk.cache.empty else None
        self.sentCountWithoutPing = 0
        self.respondingTo = None
        # self.main()

    def receive(self, message: bytes):
        ''' message will be the timestamp after which to start sending data '''
        if len(self.disk.cache.index) == 0:
            return  # nothing to send
        vesicle: Vesicle = super().receive(message)
        if isinstance(vesicle, Ping):
            self.sentCountWithoutPing = 0
            return
        if not isinstance(vesicle, ObservationRequest) or not vesicle.isValid:
            return
        ts = vesicle.time
        if vesicle.isValid:
            self.pause = 3
            if isValidTimestamp(ts):
                self.respondingTo = vesicle.time
                self.ts = vesicle.time
            elif vesicle.first:
                self.respondingTo = 'frst'
                self.ts = datetimeToTimestamp(earliestDate())
            elif vesicle.latest and len(self.disk.cache.index) > 1:
                self.respondingTo = 'latest'
                self.ts = self.disk.cache.index[-2]
            elif vesicle.middle:
                self.respondingTo = 'middle'
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

        def coolDown():
            '''
            mainly so that we don't get too far ahead of the subscriber, as 
            they must validate and save the data sequentially
            '''
            time.sleep(.375)

        def getObservationAfter(timestamp: str) -> SingleObservation:
            ''' get the next observation after the time '''
            def isLatest(index):
                '''
                updates the last index if we've reached what we thought 
                might be the last index
                '''
                if index == self.last:
                    if self.last is not None and not self.disk.cache.empty:
                        self.last = self.disk.cache.index[-1]
                        if index == self.last:
                            return True
                    else:
                        self.last = None
                return False

            after = self.disk.getObservationAfter(timestamp)
            if (
                after is None or
                (isinstance(after, pd.DataFrame) and after.empty)
            ):
                raise Exception('no data')
            row = after.loc[after.index > timestamp].head(1)
            if (row.shape[0] == 0):
                raise Exception('no data')
            # if (row.shape[0] == 1): # same as else:
            return SingleObservation(
                time=row.index[0],
                data=row['value'].values[0],
                hash=row['hash'].values[0],
                isFirst=row.index[0] == self.first,
                isLatest=isLatest(row.index[0]),
                responseTo=self.respondingTo)

        self.running = True
        self.sentCountWithoutPing = 0
        while self.ts != self.disk.cache.index[-1] and self.sentCountWithoutPing < 500:
            ts = self.ts
            coolDown()
            try:
                observation = getObservationAfter(ts)
            except Exception as _:
                break
            self.send(observation)
            self.sentCountWithoutPing += 1
            if self.ts == ts:
                self.ts = observation.time
            if self.pause > 1:
                time.sleep(self.pause)
                self.pause /= 2
        self.running = False
