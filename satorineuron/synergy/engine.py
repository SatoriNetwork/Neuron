''' manages all synergy connections and messages '''

from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.synergy import SynergyProtocol
from satorilib.api.wallet import Wallet
from satorilib.api.wallet import RavencoinWallet
from satorineuron import config
from satorineuron.synergy.client import SynergyClient
from satorineuron.synergy.channel import SynergyChannel, SynergyPublisher, SynergySubscriber


def chooseRandomUnusedPortWitninDynamicRange():
    # actaully at this point we have to choose the same one specified in the
    # p2p script, so we've hard coded this just as we hardcoded 24601
    return 24600


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
        self.channels: dict[str, SynergyChannel] = {
            # localport: SynergyChannel
        }

    def connectToPeer(self, streamId: StreamId):
        ''' this can be called to initiate the connection to a peer '''
        self.handleMessage(SynergyProtocol(
            source=streamId.source,
            stream=streamId.stream,
            target=streamId.target,
            author=streamId.author,
            subscriber=self.pubkey,
            subscriberPort=None,
            subscriberIp=None,
            authorPort=None,
            authorIp=None,
        ))

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
            self.channels[msg.subscriberIp] = SynergyPublisher(
                streamId=msg.streamId,
                ip=msg.subscriberIp)
        elif msg.subscriber == self.pubkey:
            self.channels[msg.authorIp] = SynergySubscriber(
                streamId=msg.streamId,
                ip=msg.authorIp)

    def passMessage(self, remoteIp: str, message: bytes):
        ''' passes a message down to the correct channel '''
        conn = self.channels.get(remoteIp)
        if conn is not None:
            conn.receive(message)
        else:
            logging.debug('how? we have no channel for them.', color='magenta')
