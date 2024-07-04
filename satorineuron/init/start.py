from typing import Union
import os
import time
import json
import threading
from reactivex.subject import BehaviorSubject
from queue import Queue
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
from satorineuron.common.structs import ConnectionTo
from satorineuron.relay import RawStreamRelayEngine, ValidateRelayStream
from satorineuron.structs.start import StartupDagStruct
from satorineuron.structs.pubsub import SignedStreamId
from satorineuron.synergy.engine import SynergyManager


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

    def __init__(
        self,
        *args,
        env: str = 'dev',
        urlServer: str = None,
        urlPubsub: str = None,
        urlSynergy: str = None,
        isDebug: bool = False
    ):
        super(StartupDag, self).__init__(*args)
        self.env = env
        self.lastWalletCall = 0
        self.lastVaultCall = 0
        self.electrumCooldown = 30
        self.asyncThread: AsyncThread = AsyncThread()
        self.isDebug: bool = isDebug
        # self.workingUpdates: BehaviorSubject = BehaviorSubject(None)
        # self.chatUpdates: BehaviorSubject = BehaviorSubject(None)
        self.workingUpdates: Queue = Queue()
        self.chatUpdates: Queue = Queue()
        # dictionary of connection statuses {ConnectionTo: bool}
        self.connectionsStatusQueue: Queue = Queue()
        self.latestConnectionStatus: dict = {}
        self.urlServer: str = urlServer
        self.urlPubsub: str = urlPubsub
        self.urlSynergy: str = urlSynergy
        self.paused: bool = False
        self.pauseThread: Union[threading.Thread, None] = None
        self._ravencoinWallet: RavencoinWallet
        self._evrmoreWallet: EvrmoreWallet
        self._ravencoinVault: Union[RavencoinWallet, None] = None
        self._evrmoreVault: Union[EvrmoreWallet, None] = None
        self.details: dict
        self.key: str
        self.idKey: str
        self.subscriptionKeys: str
        self.publicationKeys: str
        # self.ipfs: Ipfs = Ipfs()
        self.caches: dict[StreamId, disk.Cache] = {}
        self.relayValidation: ValidateRelayStream
        self.server: SatoriServerClient
        self.pubsub: SatoriPubSubConn = None
        self.synergy: Union[SynergyManager, None] = None
        self.relay: RawStreamRelayEngine = None
        self.engine: satoriengine.Engine
        self.publications: list[Stream] = []
        self.subscriptions: list[Stream] = []
        self.udpQueue: Queue = Queue()
        self.restartThread = threading.Thread(
            target=self.restartEverything, daemon=True)
        self.restartThread.start()
        # self.delayedStart()
        alreadySetup: bool = os.path.exists(config.walletPath('wallet.yaml'))
        if alreadySetup:
            threading.Thread(target=self.delayedEngine).start()
        while True:
            if self.asyncThread.loop is not None:
                self.restartThread = self.asyncThread.repeatRun(
                    task=self.start,
                    interval=60*60*24 if alreadySetup else 60*60*12)
                break
            time.sleep(1)

    def delayedEngine(self):
        time.sleep(60*60*6)
        self.buildEngine()

    def cacheOf(self, streamId: StreamId) -> Union[disk.Cache, None]:
        ''' returns the reference to the cache of a stream '''
        return self.caches.get(streamId)

    @property
    def network(self) -> str:
        return 'main' if self.env == 'prod' else 'test'

    @property
    def vault(self) -> Union[EvrmoreWallet, RavencoinWallet]:
        return self._evrmoreVault if self.env == 'prod' else self._ravencoinVault

    @property
    def wallet(self) -> Union[EvrmoreWallet, RavencoinWallet]:
        return self._evrmoreWallet if self.env == 'prod' else self._ravencoinWallet

    @property
    def ravencoinWallet(self) -> RavencoinWallet:
        if self._ravencoinWallet is None:
            self._ravencoinWallet = RavencoinWallet(
                config.walletPath('wallet.yaml'),
                reserve=0.01,
                isTestnet=self.networkIsTest('ravencoin'))
        return self._ravencoinWallet

    @property
    def evrmoreWallet(self) -> EvrmoreWallet:
        if self._evrmoreWallet is None:
            self._evrmoreWallet = EvrmoreWallet(
                config.walletPath('wallet.yaml'),
                reserve=0.01,
                isTestnet=self.networkIsTest('evrmore'))
        return self._evrmoreWallet

    def ravencoinVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[RavencoinWallet, None]:
        if self._ravencoinVault is None or (self._ravencoinVault.password is None and password is not None):
            try:
                vaultPath = config.walletPath('vault.yaml')
                if os.path.exists(vaultPath) or create:
                    self._ravencoinVault = RavencoinWallet(
                        vaultPath,
                        reserve=0.01,
                        isTestnet=self.networkIsTest('ravencoin'),
                        password=password,
                        use=self._ravencoinVault)
            except Exception as e:
                logging.error('failed to open vault', color='red')
                raise e
            if password is None:
                logging.info('loaded raw vault', color='green')
            else:
                logging.info('accessed vault', color='green')
            return self._ravencoinVault
        return self._ravencoinVault

    def evrmoreVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[RavencoinWallet, None]:
        if self._evrmoreVault is None or (self._evrmoreVault.password is None and password is not None):
            try:
                vaultPath = config.walletPath('vault.yaml')
                if os.path.exists(vaultPath) or create:
                    self._evrmoreVault = EvrmoreWallet(
                        vaultPath,
                        reserve=0.01,
                        isTestnet=self.networkIsTest('evrmore'),
                        password=password,
                        use=self._evrmoreVault)
            except Exception as e:
                logging.error('failed to open vault', color='red')
                raise e
            if password is None:
                logging.info('loaded vault', color='green')
            else:
                logging.info('accessed vault', color='green')
            return self._evrmoreVault
        return self._evrmoreVault

    def networkIsTest(self, network: str = None) -> bool:
        return network.lower().strip() in ('testnet', 'test', 'ravencoin', 'rvn')

    def getWallet(self, network: str = None) -> Union[EvrmoreWallet, RavencoinWallet]:
        network = network or self.network
        if self.networkIsTest(network):
            return self.ravencoinWallet
        return self.evrmoreWallet

    def getVault(
        self,
        network: str = None,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[EvrmoreWallet, RavencoinWallet]:
        network = network or self.network
        if self.networkIsTest(network):
            return self.ravencoinVault(password=password, create=create)
        return self.evrmoreVault(password=password, create=create)

    def openWallet(self, network: Union[str, None] = None) -> Union[EvrmoreWallet, RavencoinWallet]:
        wallet = self.getWallet(network)
        if self.lastWalletCall + self.electrumCooldown < time.time():
            self.lastWalletCall = time.time()
            wallet = wallet()
            if wallet.electrumx.conn is not None:
                self.updateConnectionStatus(
                    connTo=ConnectionTo.electrumx,
                    status=True)
            else:
                self.updateConnectionStatus(
                    connTo=ConnectionTo.electrumx,
                    status=False)
            logging.info('opened wallet', color='green')
        else:
            logging.info('respecting wallet cooldown', color='green')
        return wallet

    def closeVault(self) -> Union[RavencoinWallet, EvrmoreWallet, None]:
        ''' close the vault, reopen it without decrypting it. '''
        try:
            self._ravencoinVault.close()
        except Exception as _:
            pass
        try:
            self._evrmoreVault.close()
        except Exception as _:
            pass
        return self.openVault()

    def openVault(
        self,
        network: Union[str, None] = None,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[RavencoinWallet, EvrmoreWallet, None]:
        '''
        without a password it will open the vault (if it exists) but not decrypt
        it. this allows us to get it's balance, but not spend from it.
        '''
        vault = self.getVault(network, password, create)
        if vault is not None and self.lastVaultCall + self.electrumCooldown < time.time():
            self.lastVaultCall = time.time()
            vault = vault()
            if vault.electrumx.conn is not None:
                self.updateConnectionStatus(
                    connTo=ConnectionTo.electrumx,
                    status=True)
            else:
                self.updateConnectionStatus(
                    connTo=ConnectionTo.electrumx,
                    status=False)
            logging.info('opened vault', color='green')
        else:
            logging.info('respecting vault cooldown', color='green')
        return vault

    def start(self):
        ''' start the satori engine. '''
        # while True:
        self.createRelayValidation()
        self.openWallet()
        self.openVault()
        self.checkin()
        # self.autosecure()
        self.verifyCaches()
        self.startSynergyEngine()
        self.pubsubConnect()
        if self.isDebug:
            return
        self.startRelay()
        self.buildEngine()
        time.sleep(60*4)

    def updateConnectionStatus(self, connTo: ConnectionTo, status: bool):
        # logging.info('connTo:', connTo, status, color='yellow')
        self.latestConnectionStatus = {
            **self.latestConnectionStatus,
            **{connTo.name: status}}
        self.connectionsStatusQueue.put(self.latestConnectionStatus)

    def createRelayValidation(self):
        self.relayValidation = ValidateRelayStream()
        logging.info('started relay validation engine', color='green')

    def checkin(self):
        self.server = SatoriServerClient(self.wallet, url=self.urlServer)
        try:
            referrer = open(
                config.root('config', 'referral.txt'),
                mode='r').read().strip()
        except Exception as _:
            referrer = None
        try:
            self.details = CheckinDetails(
                self.server.checkin(referrer=referrer))
            self.updateConnectionStatus(
                connTo=ConnectionTo.central,
                status=True)
            # logging.debug(self.details, color='magenta')
            self.key = self.details.key
            self.idKey = self.details.idKey
            self.subscriptionKeys = self.details.subscriptionKeys
            self.publicationKeys = self.details.publicationKeys
            self.subscriptions = [
                Stream.fromMap(x)
                for x in json.loads(self.details.subscriptions)]
            # logging.debug(self.subscriptions, color='yellow')
            self.publications = [
                Stream.fromMap(x)
                for x in json.loads(self.details.publications)]
            # logging.debug(self.publications, color='magenta')
            self.caches = {
                x.streamId: disk.Cache(id=x.streamId)
                for x in set(self.subscriptions + self.publications)}
            # for k, v in self.caches.items():
            #    logging.debug(k, v, color='magenta')

            # logging.debug(self.caches, color='yellow')
            # self.signedStreamIds = [
            #    SignedStreamId(
            #        source=s.id.source,
            #        author=s.id.author,
            #        stream=s.id.stream,
            #        target=s.id.target,
            #        publish=False,
            #        subscribe=True,
            #        signature=sig,  # doesn't the server need my pubkey?
            #        signed=self.wallet.sign(sig)) for s, sig in zip(
            #            self.subscriptions,
            #            self.subscriptionKeys)
            # ] + [
            #    SignedStreamId(
            #        source=p.id.source,
            #        author=p.id.author,
            #        stream=p.id.stream,
            #        target=p.id.target,
            #        publish=True,
            #        subscribe=True,
            #        signature=sig,  # doesn't the server need my pubkey?
            #        signed=self.wallet.sign(sig)) for p, sig in zip(
            #            self.publications,
            #            self.publicationKeys)]
            logging.info('checked in with Satori', color='green')
        except Exception as _:
            self.updateConnectionStatus(
                connTo=ConnectionTo.central,
                status=False)

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

    def pubsubConnect(self):
        ''' establish a pubsub connection. '''
        if self.pubsub is not None:
            self.pubsub.disconnect()
            self.updateConnectionStatus(
                connTo=ConnectionTo.pubsub,
                status=False)
            self.pubsub = None
        if self.key:
            signature = self.wallet.sign(self.key)
            self.pubsub = satorineuron.engine.establishConnection(
                url=self.urlPubsub,
                pubkey=self.wallet.publicKey,
                key=signature.decode() + '|' + self.key,
                onConnect=lambda: self.updateConnectionStatus(
                    connTo=ConnectionTo.pubsub,
                    status=True),
                onDisconnect=lambda: self.updateConnectionStatus(
                    connTo=ConnectionTo.pubsub,
                    status=False))
            logging.info('connected to Satori pubsub network', color='green')
        else:
            time.sleep(30)
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

    def startSynergyEngine(self):
        ''' establish a synergy connection '''
        if self.wallet:
            self.synergy = SynergyManager(
                url=self.urlSynergy,
                wallet=self.wallet,
                onConnect=self.syncDatasets)
            logging.info(
                'connected to Satori p2p network', color='green')
        else:
            raise Exception('wallet not open yet.')

    def syncDataset(self, streamId: StreamId):
        ''' establish a synergy connection '''
        if self.synergy and self.synergy.isConnected:
            for stream in self.subscriptions:
                if streamId == stream.streamId:
                    logging.info('resyncing stream:', stream, print=True)
                    self.synergy.connectToPeer(stream.streamId)
        # else:
        #    raise Exception('synergy not created or not connected.')

    def syncDatasets(self):
        ''' establish a synergy connection '''
        if self.synergy and self.synergy.isConnected:
            self.updateConnectionStatus(
                connTo=ConnectionTo.synergy,
                status=True)
            for stream in self.subscriptions:
                self.synergy.connectToPeer(stream.streamId)
        else:
            self.updateConnectionStatus(
                connTo=ConnectionTo.synergy,
                status=False)
        # else:
        #    raise Exception('synergy not created or not connected.')

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

    # def autosecure(self):
    #     ''' automatically send funds to the vault on startup '''

    #     def executeAutosecure(wallet: Union[RavencoinWallet, EvrmoreWallet], network: str):
    #         entry = wallet.getAutosecureEntry()
    #         if entry is None:
    #             return
    #         amount = wallet.balanceAmount - entry.get('retain', 0)
    #         if amount > wallet.reserveAmount:
    #             result = wallet.typicalNeuronTransaction(
    #                 amount=amount,
    #                 address=entry.get('address'),
    #                 sweep=False,
    #                 pullFeeFromAmount=True)
    #             if result.msg == 'creating partial, need feeSatsReserved.':
    #                 responseJson = self.server.requestSimplePartial(
    #                     network=network)
    #                 # account for fee
    #                 if amount > 1:
    #                     amount -= 1
    #                 result = wallet.typicalNeuronTransaction(
    #                     sweep=False,
    #                     amount=amount,
    #                     address=entry.get('address'),
    #                     completerAddress=responseJson.get('completerAddress'),
    #                     feeSatsReserved=responseJson.get('feeSatsReserved'),
    #                     changeAddress=responseJson.get('changeAddress'),
    #                 )
    #             if result is None:
    #                 logging.error('Unable to execute autosecure transaction')
    #             elif result.success:
    #                 if (  # checking any on of these should suffice in theory...
    #                     result.tx is not None and
    #                     result.reportedFeeSats is not None and
    #                     result.reportedFeeSats > 0 and
    #                     result.msg == 'send transaction requires fee.'
    #                 ):
    #                     r = self.server.broadcastSimplePartial(
    #                         tx=result.tx,
    #                         reportedFeeSats=result.reportedFeeSats,
    #                         feeSatsReserved=responseJson.get(
    #                             'feeSatsReserved'),
    #                         network=(
    #                             'ravencoin' if self.networkIsTest(network)
    #                             else 'evrmore'))
    #                     if r.text != '':
    #                         logging.info(r.text)
    #                         time.sleep(10)
    #                         wallet.get(allWalletInfo=False)
    #                         return
    #                     logging.error(
    #                         'Unable to execute autosecure transaction')
    #                     return
    #                 time.sleep(10)
    #                 wallet.get(allWalletInfo=False)
    #                 return
    #             logging.error('Unable to execute autosecure transaction')

    #     def autosecureLoop():
    #         logging.info('running autosecure loop', color='green')
    #         for wallet, network in zip(
    #             [self._ravencoinWallet, self._evrmoreWallet],
    #             ['test', 'main']
    #         ):
    #             if wallet is not None and wallet.shouldAutosecure():
    #                 executeAutosecure(wallet, network)

    #     autosecureLoop()

    def repullFor(self, streamId: StreamId):
        if self.engine is not None:
            for model in self.engine.models:
                if model.variable == streamId:
                    model.inputsUpdated.on_next(True)
                else:
                    for target in model.targets:
                        if target == streamId:
                            model.inputsUpdated.on_next(True)

    def delayedStart(self):
        alreadySetup: bool = os.path.exists(config.walletPath('wallet.yaml'))
        if alreadySetup:
            threading.Thread(target=self.delayedEngine).start()
        # while True:
        #    if self.asyncThread.loop is not None:
        #        self.restartThread = self.asyncThread.repeatRun(
        #            task=self.start,
        #            interval=60*60*24 if alreadySetup else 60*60*12)
        #        break
        #    time.sleep(1)

    def restartEverything(self):
        import random
        time.sleep(random.randint(60*60*21, 60*60*24))
        import requests
        requests.get('http://127.0.0.1:24601/restart')
