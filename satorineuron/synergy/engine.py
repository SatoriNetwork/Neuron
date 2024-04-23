''' manages all synergy connections and messages '''
import threading
from satorilib import logging
from satorilib.concepts import StreamId
from satorilib.synergy import SynergyProtocol
from satorilib.api.wallet import Wallet
from satorilib.api.wallet import RavencoinWallet
from satorisynapse.lib.domain import SYNAPSE_PORT
from satorineuron import config
from satorineuron.synergy.client import SynergyClient
from satorineuron.synergy.channel import Axon, SynapsePublisher, SynapseSubscriber


class SynergyManager():
    def __init__(self, wallet: Wallet, onConnect: callable = None):
        self.wallet = wallet
        self.pubkey = wallet.publicKey
        self.synergy = SynergyClient(
            url='https://satorinet.io:24602',
            router=self.handleMessage,
            wallet=wallet,
            onConnected=onConnect)
        self.channels: dict[str, Axon] = {
            # remoteIp: Axon
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
            msg.subscriberPort = SYNAPSE_PORT
            return msg
        if msg.author == self.pubkey:
            msg.authorPort = SYNAPSE_PORT
            self.createChannel(msg)
            return msg
        raise Exception('invalid message state')

    def createChannel(self, msg: SynergyProtocol):
        ''' completes the next part of the msg and returns '''
        if msg.author == self.pubkey and (self.channels.get(msg.subscriberIp) is None or not self.channels[msg.subscriberIp].running):
            logging.info(
                'creating channel to new subscribing peer for stream:',
                f'{msg.stream}.{msg.target}', color='green')
            self.channels[msg.subscriberIp] = SynapsePublisher(
                streamId=msg.streamId,
                ip=msg.subscriberIp)
        elif msg.subscriber == self.pubkey:
            logging.info(
                'creating channel to new publishing peer:',
                f'{msg.stream}.{msg.target}', color='green')
            self.channels[msg.authorIp] = SynapseSubscriber(
                streamId=msg.streamId,
                ip=msg.authorIp)

    def passMessage(self, remoteIp: str, message: bytes):
        ''' passes a message down to the correct channel '''
        conn = self.channels.get(remoteIp)
        if conn is not None:
            conn.receive(message)
