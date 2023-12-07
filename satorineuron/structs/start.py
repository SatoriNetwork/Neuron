from typing import Union
import threading
from satorilib.concepts.structs import Stream
from satorilib.api.wallet import Wallet
# from satorilib.api.ipfs import Ipfs
from satorilib.server import SatoriServerClient
from satorilib.pubsub import SatoriPubSubConn
from satorilib.asynchronous import AsyncThread


class StartupDagStruct(object):
    ''' a DAG of startup tasks. '''

    def __init__(self, urlServer: str = None, urlPubsub: str = None, *args):
        super(StartupDagStruct, self).__init__(*args)
        self.urlServer: str = None
        self.urlPubsub: str = None
        self.paused: bool = None
        self.pauseThread: Union[threading.Thread, None] = None
        self.wallet: Wallet = None
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
        # self.retro: Retro = None
        self.relay: 'RawStreamRelayEngine' = None
        self.engine: 'satoriengine.Engine' = None
        self.publications: list[Stream] = None
        self.subscriptions: list[Stream] = None
        self.asyncThread: AsyncThread = None

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

    def retroConnect(
        self,
        subscriptions: Union[list, None] = None,
        extraSubscriptions: Union[list, None] = None,
    ):
        '''
        establish a retro connection. we can subscribe to anything in retro 
        so allow override or additional subscriptions here.
        '''
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
