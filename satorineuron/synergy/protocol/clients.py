'''
contains the protocol to communicate with clients once connected

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
from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.api.disk import Cached
from satorilib.api.hash import hashRow
from satorilib.api.wallet import Wallet
from satorilib.api.wallet import RavencoinWallet
from satorilib.api.time import datetimeToTimestamp, earliestDate
from satorineuron import config
from satorineuron.synergy.domain import SingleObservation
from satorineuron.synergy.protocol.server import SynergyProtocol
from satorineuron.synergy.publisher import SynergyClient


def chooseRandomUnusedPortWitninDynamicRange():
    # todo: implement
    return 12345


class SynergyManager():
    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self.pubkey = wallet.publicKey
        self.synergy = SynergyClient(
            url='http://localhost:3300',
            router=self.handleMessage,
            wallet=RavencoinWallet(
                config.walletPath('wallet.yaml'),
                reserve=0.01,
                isTestnet=True)())
        self.conns: dict[int, SynergyChannel] = {
            # localport: SynergyChannel
        }

    def handleMessage(self, msg: SynergyProtocol):
        # if the msg is not complete, continue to build it, pass it back
        if not msg.completed:
            msg = self.buildMessage(msg)
            self.synergy.send(msg.toJson())
        # if the msg is complete, then it is time to make a p2p connection
        self.createChannel(msg)

    def buildMessage(self, msg: SynergyProtocol):
        ''' completes the next part of the msg and returns '''
        # subscriber is requesting connection so...
        if msg.author == self.pubkey:
            # extract their information and...
            self.createChannel(msg)
            # provide a port to connect on...
            # (choose random )
            msg.authorPort = chooseRandomUnusedPortWitninDynamicRange()
            return msg
        # as the subscriber, I am getting ready to request connection so...
        if msg.subscriber == self.pubkey and msg.subscriberIp is None:
            # provide a port to connect on...
            # (choose random )
            msg.subscriberPort = chooseRandomUnusedPortWitninDynamicRange()
            return msg
        raise Exception('invalid message state')

    def createChannel(self, msg: SynergyProtocol):
        ''' completes the next part of the msg and returns '''
        if msg.author == self.pubkey:
            self.conns[msg.subscriberPort] = SynergyPublisher(
                streamId=msg.stream,  # should probably have entire stream in here
                ip=msg.subscriberIp,
                port=msg.subscriberPort,
                localPort=msg.authorPort)
        elif msg.subscriber == self.pubkey:
            self.conns[msg.subscriberPort] = SynergySubscriber(
                streamId=msg.stream,  # should probably have entire stream in here
                ip=msg.authorIp,
                port=msg.authorPort,
                localPort=msg.subscriberPort)

    def receive(self, localPort: int, remoteIp: str, remotePort: int, message: bytes):
        ''' passes a message down to the correct channel '''
        conn = self.conns.get(localPort)
        if conn is not None:
            conn.receive(message)
        # topic = self.peer.findTopic(localPort)
        # if topic is None:
        #    return
        # channel = topic.findChannel(remoteIp, remotePort)
        # if channel is None:
        #    return
        # channel.onMessage(message=message, sent=False)


class SynergyChannel(Cached):
    ''' get messages from the peer and send messages to them '''

    def __init__(self, streamId: StreamId, ip: str, port: int, localPort: int):
        super().__init__()
        from satorineuron.init.start import getStart
        self.streamId = streamId
        self.localPort = localPort
        self.ip = ip
        self.port = port
        self.start = getStart()

    def send(self, data: str):
        ''' sends data to the peer '''
        # todo: must send correct format data correctly
        self.start.udpQueue.put(data)

    def receive(self, message: bytes):
        '''Handle incoming messages. Must be implemented by subclasses.'''
        pass


class SynergySubscriber(SynergyChannel):
    ''' 
    get messages from the peer and send messages to them, takes messages and 
    saves the data to disk using Cached, if there's a problem it sends a message
    back to the peer asking for it to start over at the last known good hash.
    '''

    def __init__(self, streamId: StreamId, ip: str, port: int, localPort: int):
        super().__init__(streamId, ip, port, localPort)
        self.inbox = Queue()
        self.main()

    def receive(self, message: bytes):
        ''' message that will contain data to save, add to inbox '''
        observation = SingleObservation.fromMessage(message)
        if observation.isValid:
            self.inbox.put(observation)

    def main(self):
        ''' send the data to the subscriber '''
        self.thread = threading.Thread(target=self.processObservations)
        self.thread.start()

    def processObservations(self):
        ''' save them all to disk '''

        def save(observation: SingleObservation):
            ''' save the data to disk, if anything goes wrong request a time '''

            def lastHash():
                if self.disk.cache.empty:
                    return ''
                else:
                    return self.disk.cache.iloc[[-1]].hash

            def lastTime():
                if self.disk.cache.empty:
                    return datetimeToTimestamp(earliestDate())
                else:
                    return self.disk.cache.index[-1]

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

        while True:
            save(self.inbox.get())


class SynergyPublisher(SynergyChannel):
    ''' 
    get messages from the peer and send messages to them. the message will 
    contain the last known good data. this publisher will then take that as a
    starting point and send all the data after that to the subscriber. that is
    until it gets interrupted.
    '''

    def __init__(self, streamId: StreamId, ip: str, port: int, localPort: int):
        super().__init__(streamId, ip, port, localPort)
        self.ts: str = datetimeToTimestamp(earliestDate())
        self.main()

    def receive(self, message: bytes):
        ''' message will be the timestamp after which to start sending data '''
        self.ts = message.decode()

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

        while self.ts != self.disk.cache.index[-1]:
            ts = self.ts
            time.sleep(0.33)  # cool down
            try:
                observation = getObservationAfter(ts)
            except Exception as e:
                break
            self.send(observation.toJson())
            if self.ts == ts:
                self.ts = observation.time
