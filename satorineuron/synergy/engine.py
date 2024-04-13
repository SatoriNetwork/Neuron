''' manages all synergy connections and messages '''
import threading
from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.synergy import SynergyProtocol
from satorilib.api.wallet import Wallet
from satorilib.api.wallet import RavencoinWallet
from satorineuron import config
from satorineuron.synergy.client import SynergyClient
from satorineuron.synergy.channel import Axon, SynapsePublisher, SynapseSubscriber
from satorilib.api.time import datetimeToTimestamp, earliestDate


def chooseRandomUnusedPortWitninDynamicRange():
    # actaully at this point we have to choose the same one specified in the
    # p2p script, so we've hard coded this just as we hardcoded 24601
    return 24600


# class SynergyManager():
#    def __init__(self, wallet: Wallet):
#        self.wallet = wallet
#        self.pubkey = wallet.publicKey
#        self.channel = Axon(StreamId(
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
    def __init__(self, wallet: Wallet, onConnect: callable = None):
        self.wallet = wallet
        self.pubkey = wallet.publicKey
        self.synergy = SynergyClient(
            url='https://satorinet.io:24602',
            router=self.handleMessage,
            wallet=RavencoinWallet(config.walletPath('wallet.yaml'))(),
            onConnected=onConnect)
        self.channels: dict[str, Axon] = {
            # localport: Axon
        }
        self.runForever()

    @property
    def isConnected(self) -> bool:
        return self.synergy.isConnected

    def runForever(self):
        self.synergyThread = threading.Thread(target=self.synergy.runForever)
        self.synergyThread.start()

    def connectToPeer(self, streamId: StreamId):
        ''' this can be called to initiate the connection to a peer '''
        self.handleMessage(SynergyProtocol.fromStreamId(streamId, self.pubkey))

    def handleMessage(self, msg: SynergyProtocol):
        if not msg.completed:
            msg = self.buildMessage(msg)
            self.synergy.send(msg.toJson())
        else:
            self.createChannel(msg)

    def buildMessage(self, msg: SynergyProtocol):
        ''' completes the next part of the msg and returns '''
        if msg.subscriber == self.pubkey and msg.subscriberIp is None:
            msg.subscriberPort = chooseRandomUnusedPortWitninDynamicRange()
            return msg
        if msg.author == self.pubkey:
            msg.authorPort = chooseRandomUnusedPortWitninDynamicRange()
            self.createChannel(msg)
            return msg
        raise Exception('invalid message state')

    def createChannel(self, msg: SynergyProtocol):
        ''' completes the next part of the msg and returns '''
        if msg.author == self.pubkey:
            self.channels[msg.subscriberIp] = SynapsePublisher(
                streamId=msg.streamId,
                ip=msg.subscriberIp)
        elif msg.subscriber == self.pubkey:
            self.channels[msg.authorIp] = SynapseSubscriber(
                streamId=msg.streamId,
                ip=msg.authorIp)

    def passMessage(self, remoteIp: str, message: bytes):
        ''' passes a message down to the correct channel '''
        conn = self.channels.get(remoteIp)
        if conn is not None:
            conn.receive(message)
