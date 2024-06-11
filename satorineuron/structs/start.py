from typing import Union
import threading
from queue import Queue
from reactivex.subject import BehaviorSubject
from satorilib.concepts.structs import StreamId, Stream
from satorilib.api.wallet import RavencoinWallet, EvrmoreWallet
# from satorilib.api.ipfs import Ipfs
from satorilib.server import SatoriServerClient
from satorilib.pubsub import SatoriPubSubConn
from satorilib.asynchronous import AsyncThread


class StartupDagStruct(object):
    ''' a DAG of startup tasks. '''

    def __init__(
        self,
        env: str = None,
        urlServer: str = None,
        urlPubsub: str = None,
        urlSynergy: str = None,
        *args
    ):
        super(StartupDagStruct, self).__init__(*args)
        self.workingUpdates: Queue = None
        self.chatUpdates: Queue = None
        self.connectionsStatusQueue: Queue = None
        self.latestConnectionStatus: dict = None
        self.env: str = None
        self.urlServer: str = None
        self.urlPubsub: str = None
        self.urlSynergy: str = None
        self.paused: bool = None
        self.pauseThread: Union[threading.Thread, None] = None
        self.ravencoinWallet: RavencoinWallet = None
        self.evrmoreWallet: EvrmoreWallet = None
        self.details: dict = None
        self.key: str = None
        self.idKey: str = None
        self.subscriptionKeys: str = None
        self.publicationKeys: str = None
        # self.ipfs: Ipfs = None
        self.signedStreamIds: list['SignedStreamId'] = None
        self.relayValidation: 'ValidateRelayStream' = None
        self.server: SatoriServerClient = None
        self.pubsub: SatoriPubSubConn = None
        self.relay: 'RawStreamRelayEngine' = None
        self.engine: 'satoriengine.Engine' = None
        self.publications: list[Stream] = None
        self.subscriptions: list[Stream] = None
        self.asyncThread: AsyncThread = None
        self.udpQueue: Queue

    def cacheOf(self, streamId: StreamId):
        ''' returns the reference to the cache of a stream '''

    @property
    def wallet(self) -> RavencoinWallet:
        return self.ravencoinWallet

    def networkIsTest(self, network: str = None) -> bool:
        return network.lower().strip() in ('testnet', 'test', 'ravencoin', 'rvn', 'ravencoin')

    def getWallet(self, test: bool = False, network: str = None) -> Union[EvrmoreWallet, RavencoinWallet]:
        if test or self.networkIsTest(network):
            return self.ravencoinWallet
        return self.evrmoreWallet

    def start(self):
        ''' start the satori engine. '''

    def createRelayValidation(self):
        ''' creates relay validation engine '''

    def openWallet(self):
        ''' opens the local wallet. '''

    def checkin(self):
        ''' checks in with the Satori Server '''

    def buildEngine(self):
        ''' start the engine, it will run w/ what it has til ipfs is synced '''

    def pubsubConnect(self):
        ''' establish a pubsub connection. '''

    def startSynergyEngine(self):
        ''' establish a synergy connection. '''

    def startRelay(self):
        ''' starts the relay engine '''

    # def downloadDatasets(self):
    #    '''
    #    '''
    #    pass
    def autosecure(self):
        ''' starts autosecure process '''

    def pause(self, timeout: int = 60):
        ''' pause the engine. '''

    def unpause(self):
        ''' pause the engine. '''
