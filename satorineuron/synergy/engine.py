''' manages all synergy connections and messages '''

from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.synergy import SynergyProtocol
from satorilib.api.wallet import Wallet
from satorilib.api.wallet import RavencoinWallet
from satorineuron import config
from satorineuron.synergy.client import SynergyClient
from satorineuron.synergy.channel import SynergyChannel, SynergyPublisher, SynergySubscriber
from satorilib.api.time import datetimeToTimestamp, earliestDate


def chooseRandomUnusedPortWitninDynamicRange():
    # actaully at this point we have to choose the same one specified in the
    # p2p script, so we've hard coded this just as we hardcoded 24601
    return 24600


# class SynergyManager():
#    def __init__(self, wallet: Wallet):
#        self.wallet = wallet
#        self.pubkey = wallet.publicKey
#        self.channel = SynergyChannel(StreamId(
#            source='satori', stream='neuron', target='synergy', author='satori'), ip='37.19.210.29')
#        import threading
#        threading.Thread(target=self.main).start()
#
#    def main(self):
#        import time
#        while True:
#            time.sleep(10)
#            self.channel.send(data='hello world')


class SynergyManager():
    def __init__(self, wallet: Wallet):
        self.wallet = wallet
        self.pubkey = wallet.publicKey
        self.synergy = SynergyClient(
            url='https://satorinet.io:24602',
            router=self.handleMessage,
            wallet=RavencoinWallet(config.walletPath('wallet.yaml'))())
        self.channels: dict[str, SynergyChannel] = {
            # localport: SynergyChannel
        }
        self.runForever()
        self.testing()

    def testing(self):
        # testing
        import time
        time.sleep(30)
        self.synergy.ping("Hello, World!")
        self.connectToPeer(StreamId(
            source='satori',
            stream='test',
            target='price',
            author='03b4127dd21b6ee0528cb4126dbdcb093e50a04e00c7209f867995265d4d9a5c37',
        ))

        def pinging():
            while True:
                time.sleep(60)
                for channel in self.channels.values():
                    channel.send(datetimeToTimestamp(earliestDate()))

        import threading
        self.connThread = threading.Thread(target=pinging)
        self.connThread.start()

    def runForever(self):
        import threading
        self.synergyThread = threading.Thread(target=self.synergy.runForever)
        self.synergyThread.start()
        # testing
        # import time
        # time.sleep(30)
        # self.synergy.ping("Hello, World!")

    def connectToPeer(self, streamId: StreamId):
        ''' this can be called to initiate the connection to a peer '''
        self.handleMessage(SynergyProtocol.fromStreamId(streamId, self.pubkey))

    def handleMessage(self, msg: SynergyProtocol):
        print('handleMessage:', msg.toJson())
        if not msg.completed:
            msg = self.buildMessage(msg)
            self.synergy.send(msg.toJson())
        else:
            self.createChannel(msg)

    def buildMessage(self, msg: SynergyProtocol):
        ''' completes the next part of the msg and returns '''
        print('buildMessage:', msg.toJson())
        if msg.subscriber == self.pubkey and msg.subscriberIp is None:
            print('buildMessage:', 1)
            msg.subscriberPort = chooseRandomUnusedPortWitninDynamicRange()
            return msg
        if msg.author == self.pubkey:
            print('buildMessage:', 2)
            msg.authorPort = chooseRandomUnusedPortWitninDynamicRange()
            self.createChannel(msg)
            return msg
        raise Exception('invalid message state')

    def createChannel(self, msg: SynergyProtocol):
        ''' completes the next part of the msg and returns '''
        print('createChannel:', msg.toJson())
        if msg.author == self.pubkey:
            self.channels[msg.subscriberIp] = SynergyPublisher(
                streamId=msg.streamId,
                ip=msg.subscriberIp)
        elif msg.subscriber == self.pubkey:
            self.channels[msg.authorIp] = SynergySubscriber(
                streamId=msg.streamId,
                ip=msg.authorIp)

    def passMessage(self, remoteIp: str, message: bytes):
        ''' passes a message down to the correct channel '''
        print('passMessage:', remoteIp, message.decode('utf-8'))
        conn = self.channels.get(remoteIp)
        if conn is not None:
            conn.receive(message)
        else:
            logging.debug('how? we have no channel for them.', color='magenta')
