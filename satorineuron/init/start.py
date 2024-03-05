# todo create config if no config present, use config if config present
from typing import Union
import os
import json
import threading
from reactivex.subject import BehaviorSubject
import satorineuron
import satoriengine
from satorilib.concepts.structs import StreamId, Stream
from satorilib.api import disk
from satorilib.api.wallet import RavencoinWallet, EvrmoreWallet
# from satorilib.api.ipfs import Ipfs
from satorilib.server import SatoriServerClient
from satorilib.server.api import CheckinDetails
from satorilib.pubsub import SatoriPubSubConn
from satorilib.asynchronous import AsyncThread
from satorineuron import logging
from satorineuron import config
from satorineuron.relay import RawStreamRelayEngine, ValidateRelayStream
# from satorilib.api.udp.rendezvous import UDPRendezvousConnection  # todo: remove from lib
from satorineuron.rendezvous import rendezvous
from satorineuron.rendezvous.structs.domain import SignedStreamId
from satorineuron.structs.start import StartupDagStruct


def getStart():
    ''' returns StartupDag singleton '''
    return StartupDag()
# engine_start = StartupDag()


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class StartupDag(StartupDagStruct, metaclass=SingletonMeta):
    ''' a DAG of startup tasks. '''

    def __init__(self, *args, urlServer: str = None, urlPubsub: str = None, isDebug: bool = False):
        super(StartupDag, self).__init__(*args)
        self.isDebug: bool = isDebug
        self.workingUpdates: BehaviorSubject = BehaviorSubject(None)
        self.urlServer: str = urlServer
        self.urlPubsub: str = urlPubsub
        self.paused: bool = False
        self.pauseThread: Union[threading.Thread, None] = None
        self.ravencoinWallet: RavencoinWallet
        self.evrmoreWallet: EvrmoreWallet
        self.ravencoinVault: Union[RavencoinWallet, None] = None
        self.evrmoreVault: Union[EvrmoreWallet, None] = None
        self.details: dict
        self.key: str
        self.idKey: str
        self.subscriptionKeys: str
        self.publicationKeys: str
        # self.ipfs: Ipfs = Ipfs()
        self.signedStreamIds: list[SignedStreamId]
        self.caches: dict[StreamId, disk.Cache] = {}
        self.relayValidation: ValidateRelayStream
        self.server: SatoriServerClient
        self.pubsub: SatoriPubSubConn = None
        self.peer: rendezvous.RendezvousEngine
        self.relay: RawStreamRelayEngine = None
        self.engine: satoriengine.Engine
        self.publications: list[Stream] = []
        self.subscriptions: list[Stream] = []
        self.asyncThread: AsyncThread = AsyncThread()

    def cacheOf(self, streamId: StreamId) -> Union[disk.Cache, None]:
        ''' returns the reference to the cache of a stream '''
        return self.caches.get(streamId)

    @property
    def vault(self) -> RavencoinWallet:
        return self.ravencoinVault

    @property
    def wallet(self) -> RavencoinWallet:
        return self.ravencoinWallet

    def networkIsTest(self, network: str = None) -> bool:
        return network.lower().strip() in ('testnet', 'test', 'ravencoin', 'rvn')

    def getWallet(self, test: bool = False, network: str = None) -> Union[EvrmoreWallet, RavencoinWallet]:
        if test or self.networkIsTest(network):
            return self.ravencoinWallet
        return self.evrmoreWallet

    def start(self):
        ''' start the satori engine. '''
        self.createRelayValidation()
        self.openWallet()
        self.openVault()
        self.autosecure()
        self.checkin()
        self.verifyCaches()
        self.pubsubConnect()
        if self.isDebug:
            return
        self.startRelay()
        self.buildEngine()
        self.rendezvousConnect()
        self.incrementallyDownloadDatasets()
        # self.downloadDatasets()

    def createRelayValidation(self):
        self.relayValidation = ValidateRelayStream()
        logging.info('started relay validation engine', color='green')

    def openWallet(self):
        self.ravencoinWallet = RavencoinWallet(
            config.walletPath('wallet.yaml'),
            reserve=0.01,
            isTestnet=self.networkIsTest('ravencoin'))()
        self.evrmoreWallet = EvrmoreWallet(
            config.walletPath('wallet.yaml'),
            reserve=0.01,
            isTestnet=self.networkIsTest('evrmore'))()
        logging.info('opened wallet', color='green')

    def closeVault(self):
        ''' close the vault, reopen it without decrypting it. '''
        self.ravencoinVault = None
        self.evrmoreVault = None
        self.openVault()

    def openVault(self, password: str = None, create: bool = False) -> tuple[RavencoinWallet, EvrmoreWallet]:
        '''
        without a password it will open the vault (if it exists) but not decrypt
        it. this allows us to get it's balance, but not spend from it.
        '''
        try:
            vaultPath = config.walletPath('vault.yaml')
            if os.path.exists(vaultPath):
                self.ravencoinVault = RavencoinWallet(
                    vaultPath,
                    reserve=0.01,
                    isTestnet=self.networkIsTest('ravencoin'),
                    password=password,
                )()
                # self.evrmoreVault = EvrmoreWallet(
                #    vaultPath,
                #    reserve=0.01,
                #    isTestnet=self.networkIsTest('evrmore'),
                #    password=password,
                # )()
            else:  # create it if we're allowed to
                if create:
                    self.ravencoinVault = RavencoinWallet(
                        vaultPath,
                        reserve=0.01,
                        isTestnet=self.networkIsTest('ravencoin'),
                        password=password,
                    )()
                logging.info('vault not created yet')
        except Exception as e:
            logging.error('failed to open vault', color='red')
            raise e
        logging.info('opened vault', color='green')
        return self.ravencoinVault, self.evrmoreVault

    def checkin(self):
        self.server = SatoriServerClient(self.wallet, url=self.urlServer)
        self.details = CheckinDetails(self.server.checkin())
        # logging.debug(self.details, color='magenta')
        self.key = self.details.key
        self.idKey = self.details.idKey
        self.subscriptionKeys = self.details.subscriptionKeys
        self.publicationKeys = self.details.publicationKeys
        self.subscriptions = [
            Stream.fromMap(x)
            for x in json.loads(self.details.subscriptions)]
        self.publications = [
            Stream.fromMap(x)
            for x in json.loads(self.details.publications)]
        self.caches = {
            x.streamId: disk.Cache(id=x.streamId)
            for x in set(self.subscriptions + self.publications)}
        # logging.debug(self.caches, color='yellow')
        self.signedStreamIds = [
            SignedStreamId(
                source=s.id.source,
                author=s.id.author,
                stream=s.id.stream,
                target=s.id.target,
                publish=False,
                subscribe=True,
                signature=sig,  # doesn't the server need my pubkey?
                signed=self.wallet.sign(sig)) for s, sig in zip(
                    self.subscriptions,
                    self.subscriptionKeys)
        ] + [
            SignedStreamId(
                source=p.id.source,
                author=p.id.author,
                stream=p.id.stream,
                target=p.id.target,
                publish=True,
                subscribe=True,
                signature=sig,  # doesn't the server need my pubkey?
                signed=self.wallet.sign(sig)) for p, sig in zip(
                    self.publications,
                    self.publicationKeys)]
        logging.info('checked in with Satori', color='green')

    def verifyCaches(self) -> bool:
        ''' rehashes my published hashes '''

        def validateCache(cache: disk.Cache):
            success, _ = cache.validateAllHashes()
            if not success:
                cache.saveHashes()

        for stream in set(self.publications):
            cache = self.cacheOf(stream.id)
            self.asyncThread.runAsync(cache, task=validateCache)
        return True

    def buildEngine(self):
        ''' start the engine, it will run w/ what it has til ipfs is synced '''
        def predictionStreams(streams: list[Stream]):
            ''' filter down to prediciton publications '''
            return [s for s in streams if s.predicting is not None]

        self.engine: satoriengine.Engine = satorineuron.engine.getEngine(
            subscriptions=self.subscriptions,
            publications=predictionStreams(self.publications))
        self.engine.run()
        logging.info('started AI Engine', color='green')

    def pubsubConnect(self):
        ''' establish a pubsub connection. '''
        if self.pubsub is not None:
            self.pubsub.disconnect()
            self.pubsub = None
        if self.key:
            signature = self.wallet.sign(self.key)
            self.pubsub = satorineuron.engine.establishConnection(
                url=self.urlPubsub,
                pubkey=self.wallet.publicKey,
                key=signature.decode() + '|' + self.key)
            logging.info('connected to Satori pubsub network', color='green')
        else:
            raise Exception('no key provided by satori server')

    def rendezvousConnect(self):
        ''' establish a rendezvous connection. '''
        # if self.idKkey: # rendezvous has changed, instead of sending just our
        # ID key, we need to send our signed stream ids in a subscription msg.
        if self.key:
            self.peer = rendezvous.RendezvousEngine(
                peer=rendezvous.generatePeer(
                    signature=self.wallet.sign(self.key),
                    signed=self.key,
                    signedStreamIds=self.signedStreamIds))
            logging.info('connected to Satori p2p network', color='green')
        else:
            raise Exception('no key provided by satori server')

    def startRelay(self):
        def append(streams: list[Stream]):
            relays = satorineuron.config.get('relay')
            rawStreams = []
            for x in streams:
                topic = x.streamId.topic(asJson=True)
                if topic in relays.keys():
                    x.uri = relays.get(topic).get('uri')
                    x.headers = relays.get(topic).get('headers')
                    x.payload = relays.get(topic).get('payload')
                    x.hook = relays.get(topic).get('hook')
                    x.history = relays.get(topic).get('history')
                    rawStreams.append(x)
            return rawStreams

        if self.relay is not None:
            self.relay.kill()
        self.relay = RawStreamRelayEngine(streams=append(self.publications))
        self.relay.run()
        logging.info('started relay engine', color='green')

    def downloadDatasets(self):
        '''
        download pins (by ipfs address) received from satori server:
        look at each pin, if not up to date, download it to temporary disk,
        merge on disk, tell models to pull data again.
        '''
        def threadedDownload(
            ipfsAddress: str,
            ipfsStream: StreamId,
            ipfsPeer: str,
            diskApi: disk.Disk,
        ):
            # TODO:
            # if this fails ask the server for all the pins of this stream.
            # the other pins will be reported by the subscribers. download
            # them at random. or latest updated or oldest stream? idk.

            # go get the ipfs history and merge it in to the dataset.
            self.ipfs.connectIfMissing(peer=ipfsPeer)
            self.ipfs.get(
                hash=ipfsAddress,
                abspath=diskApi.path(aggregate=None, temp=True))
            diskApi.compress(includeTemp=True)
            # tell models that use this dataset to go get all their data.
            for model in self.engine.models:
                if model.variable == ipfsStream:
                    model.inputsUpdated.on_next(True)
                else:
                    for target in model.targets:
                        if target == ipfsStream:
                            model.inputsUpdated.on_next(True)

        # we should make the download run in parellel so using async functions
        # here. but in the meantime, we'll do them sequentially.
        threads = {}
        pins = self.details.pins
        if isinstance(pins, str):
            pins = json.loads(pins)
        for pin in [p for p in pins if p.get('pin_author') == p.get('stream_author')]:
            ipfsAddress = pin.get('ipfs')
            ipfsPeer = pin.get('peer')
            ipfsStream = StreamId(
                source=pin.get('stream_source'),
                author=pin.get('stream_author'),
                stream=pin.get('stream_stream'),
                target=pin.get('stream_target'))
            diskApi = disk.Disk(id=ipfsStream)
            if (
                ipfsAddress is not None and
                ipfsAddress != self.ipfs.hashOfDirectory(
                    abspath=diskApi.path(aggregate=None, temp=False))
            ):
                threads[ipfsAddress] = threading.Thread(
                    target=threadedDownload,
                    args=[ipfsAddress, ipfsStream, ipfsPeer, diskApi],
                    daemon=True)
                threads[ipfsAddress].start()
        logging.info('downloaded datasets via ipfs', color='green')

    def incrementallyDownloadDatasets(self):
        ''' download history incrementally by using Satori Rendezvous network'''
        self.peer.run()
        logging.info('downloading datasets via p2p network', color='green')

    def pause(self, timeout: int = 60):
        ''' pause the engine. '''
        self.paused = True
        # self.engine.pause()
        self.pauseThread = self.asyncThread.delayedRun(
            task=self.unpause,
            delay=timeout)
        logging.info('AI engine paused', color='green')

    def unpause(self):
        ''' pause the engine. '''
        # self.engine.unpause()
        self.paused = False
        if self.pauseThread is not None:
            self.asyncThread.cancelTask(self.pauseThread)
        self.pauseThread = None
        logging.info('AI engine unpaused', color='green')

    def autosecure(self):

        def executeAutosecure(wallet: Union[RavencoinWallet, EvrmoreWallet], network: str):
            import time
            entry = wallet.getAutosecureEntry()
            if entry is None:
                return
            amount = wallet.balanceAmount - entry.get('retain', 0)
            if amount > 0:
                result = wallet.typicalNeuronTransaction(
                    amount=amount,
                    address=entry.get('address'),
                    sweep=False,
                    pullFeeFromAmount=True)
                if result.msg == 'creating partial, need feeSatsReserved.':
                    responseJson = self.server.requestSimplePartial(
                        network=network)
                    logging.debug(responseJson, color='yellow')
                    # account for fee
                    if amount > 1:
                        amount -= 1
                    result = wallet.typicalNeuronTransaction(
                        sweep=False,
                        amount=amount,
                        address=entry.get('address'),
                        completerAddress=responseJson.get('completerAddress'),
                        feeSatsReserved=responseJson.get('feeSatsReserved'),
                        changeAddress=responseJson.get('changeAddress'),
                    )
                if result is None:
                    logging.error('Unable to execute autosecure transaction')
                elif result.success:
                    if (  # checking any on of these should suffice in theory...
                        result.tx is not None and
                        result.reportedFeeSats is not None and
                        result.reportedFeeSats > 0 and
                        result.msg == 'send transaction requires fee.'
                    ):
                        r = self.server.broadcastSimplePartial(
                            tx=result.tx,
                            reportedFeeSats=result.reportedFeeSats,
                            feeSatsReserved=responseJson.get(
                                'feeSatsReserved'),
                            network=(
                                'ravencoin' if self.networkIsTest(network)
                                else 'evrmore'))
                        if r.text != '':
                            logging.info(r.text)
                            time.sleep(10)
                            wallet.get(allWalletInfo=False)
                            return
                        logging.error(
                            'Unable to execute autosecure transaction')
                        return
                    time.sleep(10)
                    wallet.get(allWalletInfo=False)
                    return
                logging.error('Unable to execute autosecure transaction')

        def autosecureLoop():
            logging.info('running autosecure loop', color='green')
            for wallet, network in zip(
                [self.ravencoinWallet, self.evrmoreWallet],
                ['test', 'main']
            ):
                if wallet is not None and wallet.shouldAutosecure():
                    executeAutosecure(wallet, network)

        self.autosecureThread = self.asyncThread.repeatRun(
            task=autosecureLoop,
            interval=60*60*6,
            delay=10)
