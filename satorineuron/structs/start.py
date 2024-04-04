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

    def __init__(self, urlServer: str = None, urlPubsub: str = None, *args):
        super(StartupDagStruct, self).__init__(*args)
        self.workingUpdates: BehaviorSubject = None
        self.urlServer: str = None
        self.urlPubsub: str = None
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
        self.peer: 'rendezvous.RendezvousEngine' = None
        self.relay: 'RawStreamRelayEngine' = None
        self.engine: 'satoriengine.Engine' = None
        self.publications: list[Stream] = None
        self.subscriptions: list[Stream] = None
        self.asyncThread: AsyncThread = None
        self.udpQueue: Queue

    def cacheOf(self, streamId: StreamId):
        ''' returns the reference to the cache of a stream '''
        pass

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
        pass

    def createRelayValidation(self):
        pass

    def openWallet(self):
        pass

    def checkin(self):
        pass

    def buildEngine(self):
        ''' start the engine, it will run w/ what it has til ipfs is synced '''
        pass

    def pubsubConnect(self):
        ''' establish a pubsub connection. '''
        pass

    def rendezvousConnect(self):
        ''' establish a rendezvous connection. '''
        pass

    def startRelay(self):
        pass

    def downloadDatasets(self):
        '''
        download pins (by ipfs address) received from satori server:
        look at each pin, if not up to date, download it to temporary disk,
        merge on disk, tell models to pull data again.
        '''
        pass

    def incrementallyDownloadDatasets(self):
        ''' download history incrementally by using Satori Rendezvous network'''
        pass

    def pause(self, timeout: int = 60):
        ''' pause the engine. '''
        pass

    def unpause(self):
        ''' pause the engine. '''
        pass
