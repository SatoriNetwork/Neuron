from typing import Union
import os
import time
import json
import random
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
from satorineuron.init.restart import restartLocalSatori
from satorineuron.init.tag import LatestTag
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
        urlMundo: str = None,
        urlPubsubs: list[str] = None,
        urlSynergy: str = None,
        isDebug: bool = False
    ):
        super(StartupDag, self).__init__(*args)
        self.env = env
        self.lastWalletCall = 0
        self.lastVaultCall = 0
        self.electrumCooldown = 10
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
        self.urlMundo: str = urlMundo
        self.urlPubsubs: list[str] = urlPubsubs
        self.urlSynergy: str = urlSynergy
        self.paused: bool = False
        self.pauseThread: Union[threading.Thread, None] = None
        self._ravencoinWallet: RavencoinWallet
        self._evrmoreWallet: EvrmoreWallet
        self._ravencoinVault: Union[RavencoinWallet, None] = None
        self._evrmoreVault: Union[EvrmoreWallet, None] = None
        self.details: CheckinDetails = None
        self.key: str
        self.oracleKey: str
        self.idKey: str
        self.subscriptionKeys: str
        self.publicationKeys: str
        # self.ipfs: Ipfs = Ipfs()
        self.caches: dict[StreamId, disk.Cache] = {}
        self.relayValidation: ValidateRelayStream
        self.server: SatoriServerClient
        self.sub: SatoriPubSubConn = None
        self.pubs: list[SatoriPubSubConn] = []
        self.synergy: Union[SynergyManager, None] = None
        self.relay: RawStreamRelayEngine = None
        self.engine: satoriengine.Engine
        self.publications: list[Stream] = []
        self.subscriptions: list[Stream] = []
        self.udpQueue: Queue = Queue()
        self.stakeStatus: bool = False
        self.miningMode: bool = False
        self.mineToVault: bool = False
        if not config.get().get('disable_restart', False):
            self.restartThread = threading.Thread(
                target=self.restartEverythingPeriodic, daemon=True)
        self.restartThread.start()
        self.checkinCheckThread = threading.Thread(
            target=self.checkinCheck, daemon=True)
        self.checkinCheckThread.start()
        # self.delayedStart()
        alreadySetup: bool = os.path.exists(config.walletPath('wallet.yaml'))
        if not alreadySetup:
            threading.Thread(target=self.delayedEngine).start()
        self.ranOnce = False
        while True:
            if self.asyncThread.loop is not None:
                self.checkinThread = self.asyncThread.repeatRun(
                    task=self.start,
                    interval=60*60*24 if alreadySetup else 60*60*12)
                break
            time.sleep(60*15)

    def delayedEngine(self):
        time.sleep(60*60*6)
        self.buildEngine()

    def checkinCheck(self):
        while True:
            time.sleep(60*60*6)
            if self.server.checkinCheck():
                self.triggerRestart()  # should just be start()

    def cacheOf(self, streamId: StreamId) -> Union[disk.Cache, None]:
        ''' returns the reference to the cache of a stream '''
        return self.caches.get(streamId)

    @property
    def rewardAddress(self) -> str:
        if isinstance(self.details, CheckinDetails):
            reward = self.details.wallet.get('rewardaddress', '')
            if reward not in [
                    self.details.wallet.get('address', ''),
                    self.details.wallet.get('vaultaddress', '')]:
                return reward or ''
        return ''

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
                reserve=0.25,
                isTestnet=self.networkIsTest('ravencoin'))
        return self._ravencoinWallet

    @property
    def evrmoreWallet(self) -> EvrmoreWallet:
        if self._evrmoreWallet is None:
            self._evrmoreWallet = EvrmoreWallet(
                config.walletPath('wallet.yaml'),
                reserve=0.25,
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
                        reserve=0.25,
                        isTestnet=self.networkIsTest('ravencoin'),
                        password=password)
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
        if self._evrmoreVault is None:
            try:
                vaultPath = config.walletPath('vault.yaml')
                if os.path.exists(vaultPath) or create:
                    self._evrmoreVault = EvrmoreWallet(
                        vaultPath,
                        reserve=0.25,
                        isTestnet=self.networkIsTest('evrmore'),
                        password=password)
            except Exception as e:
                logging.error('failed to open vault', color='red')
                raise e
            if password is None:
                logging.info('loaded vault', color='green')
            else:
                logging.info('accessed vault', color='green')
            return self._evrmoreVault
        elif self._evrmoreVault.password is None and password is not None:
            self._evrmoreVault.open(password)
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
        self.closeVault()
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
        if self.ranOnce:
            time.sleep(60*60)
        self.ranOnce = True
        self.setMiningMode()
        self.createRelayValidation()
        self.getWallet()
        self.getVault()
        self.checkin()
        self.verifyCaches()
        # self.startSynergyEngine()
        self.subConnect()
        self.pubsConnect()
        if self.isDebug:
            return
        self.startRelay()
        self.buildEngine()
        time.sleep(60*60*24)

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
        logging.debug(self.urlServer, color='teal')
        self.server = SatoriServerClient(
            self.wallet, url=self.urlServer, sendingUrl=self.urlMundo)
        try:
            referrer = open(
                config.root('config', 'referral.txt'),
                mode='r').read().strip()
        except Exception as _:
            referrer = None
        x = 30
        attempt = 0
        while True:
            attempt += 1
            try:
                self.details = CheckinDetails(
                    self.server.checkin(referrer=referrer))
                self.updateConnectionStatus(
                    connTo=ConnectionTo.central,
                    status=True)
                # logging.debug(self.details, color='magenta')
                self.key = self.details.key
                self.oracleKey = self.details.oracleKey
                self.idKey = self.details.idKey
                self.subscriptionKeys = self.details.subscriptionKeys
                self.publicationKeys = self.details.publicationKeys
                self.subscriptions = [
                    Stream.fromMap(x)
                    for x in json.loads(self.details.subscriptions)]
                if attempt < 5 and (self.details is None or len(self.subscriptions) == 0):
                    time.sleep(30)
                    continue
                logging.info('subscriptions:', len(
                    self.subscriptions), print=True)
                # logging.info('subscriptions:', self.subscriptions, print=True)
                self.publications = [
                    Stream.fromMap(x)
                    for x in json.loads(self.details.publications)]
                logging.info('publications:', len(
                    self.publications), print=True)
                # logging.info('publications:', self.publications, print=True)
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
                break
            except Exception as e:
                self.updateConnectionStatus(
                    connTo=ConnectionTo.central,
                    status=False)
                logging.warning(f'connecting to central err: {e}')
            x = x * 1.5 if x < 60*60*6 else 60*60*6
            logging.warning(f'trying again in {x}')
            time.sleep(x)

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

    @staticmethod
    def predictionStreams(streams: list[Stream]):
        ''' filter down to prediciton publications '''
        # todo: doesn't work
        return [s for s in streams if s.predicting is not None]

    @staticmethod
    def oracleStreams(streams: list[Stream]):
        ''' filter down to prediciton publications '''
        return [s for s in streams if s.predicting is None]

    def buildEngine(self):
        ''' start the engine, it will run w/ what it has til ipfs is synced '''
        # if self.miningMode:
        # logging.warning('Running in Minng Mode.', color='green')
        self.engine: satoriengine.Engine = satorineuron.engine.getEngine(
            subscriptions=self.subscriptions,
            publications=StartupDag.predictionStreams(self.publications))
        self.engine.run()
        # else:
        #    logging.warning('Running in Local Mode.', color='green')

    def subConnect(self):
        ''' establish a random pubsub connection used only for subscribing '''
        if self.sub is not None:
            self.sub.disconnect()
            self.updateConnectionStatus(
                connTo=ConnectionTo.pubsub,
                status=False)
            self.sub = None
        if self.key:
            signature = self.wallet.sign(self.key)
            self.sub = satorineuron.engine.establishConnection(
                url=random.choice(self.urlPubsubs),
                # url='ws://pubsub3.satorinet.io:24603',
                pubkey=self.wallet.publicKey,
                key=signature.decode() + '|' + self.key,
                emergencyRestart=self.emergencyRestart,
                onConnect=lambda: self.updateConnectionStatus(
                    connTo=ConnectionTo.pubsub,
                    status=True),
                onDisconnect=lambda: self.updateConnectionStatus(
                    connTo=ConnectionTo.pubsub,
                    status=False))
        else:
            time.sleep(30)
            raise Exception('no key provided by satori server')

    def pubsConnect(self):
        '''
        oracle nodes publish to every pubsub machine. therefore, they have
        an additional set of connections that they mush push to.
        '''
        self.pubs = []
        # oracles = oracleStreams(self.publications)
        if not self.oracleKey:
            return
        for pubsubMachine in self.urlPubsubs:
            signature = self.wallet.sign(self.oracleKey)
            self.pubs.append(
                satorineuron.engine.establishConnection(
                    subscription=False,
                    url=pubsubMachine,
                    pubkey=self.wallet.publicKey + ':publishing',
                    emergencyRestart=self.emergencyRestart,
                    key=signature.decode() + '|' + self.oracleKey))

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
        '''establish a synergy connection'''
        '''DISABLED FOR NOW:
        Snippet of a tcpdump
        23:11:41.073074 IP lpcpu04.58111 > dns.google.domain: 2468+ A? synergy.satorinet.io. (38)
        23:11:41.073191 IP lpcpu04.42736 > dns.google.domain: 10665+ A? synergy.satorinet.io. (38)
        23:11:41.073796 IP lpcpu04.10088 > dns.google.domain: 42995+ A? synergy.satorinet.io. (38)
        23:11:41.073819 IP lpcpu04.42121 > dns.google.domain: 31559+ A? synergy.satorinet.io. (38)
        23:11:41.073991 IP lpcpu04.44500 > dns.google.domain: 33234+ A? synergy.satorinet.io. (38)
        23:11:41.074484 IP lpcpu04.40834 > dns.google.domain: 29728+ A? synergy.satorinet.io. (38)
        23:11:41.074561 IP lpcpu04.62919 > dns.google.domain: 40503+ A? synergy.satorinet.io. (38)
        23:11:41.074685 IP lpcpu04.38206 > dns.google.domain: 20506+ A? synergy.satorinet.io. (38)
        23:11:41.075028 IP lpcpu04.58587 > dns.google.domain: 34024+ A? synergy.satorinet.io. (38)
        23:11:41.075408 IP lpcpu04.45231 > dns.google.domain: 13854+ A? synergy.satorinet.io. (38)
        23:11:41.075438 IP lpcpu04.49361 > dns.google.domain: 19875+ A? synergy.satorinet.io. (38)
        23:11:41.075581 IP lpcpu04.57224 > dns.google.domain: 47540+ A? synergy.satorinet.io. (38)
        same second, hundred of querys
        '''
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

    def triggerRestart(self):
        from satorisynapse import Envelope, Signal
        self.udpQueue.put(Envelope(ip='', vesicle=Signal(restart=True)))
        import time
        time.sleep(5)
        os._exit(0)
        # import requests
        # requests.get('http://127.0.0.1:24601/restart')

    def emergencyRestart(self):
        import time
        logging.warning('restarting in 10 minutes', print=True)
        time.sleep(60*10)
        self.triggerRestart()

    def restartEverythingPeriodic(self):
        import random
        restartTime = time.time() + config.get().get(
            'restartTime',
            random.randint(60*60*21, 60*60*24))
        latestTag = LatestTag()
        while True:
            if time.time() > restartTime:
                self.triggerRestart()
            # time.sleep(random.randint(60*60, 60*60*4))
            time.sleep(random.randint(10, 20))
            latestTag.get()
            if latestTag.isNew:
                self.triggerRestart()

    def publish(self, topic: str, data: str, observationTime: str, observationHash: str):
        ''' publishes to all the pubsub servers '''
        for pub in self.pubs:
            pub.publish(
                topic=topic,
                data=data,
                observationTime=observationTime,
                observationHash=observationHash)

    def performStakeCheck(self):
        self.stakeStatus = self.server.stakeCheck()
        return self.stakeStatus

    def setMiningMode(self, miningMode: Union[bool, None] = None):
        miningMode = miningMode if isinstance(
            miningMode, bool) else config.get().get('mining mode', True)
        self.miningMode = miningMode
        config.add(data={'mining mode': self.miningMode})
        return self.miningMode

    def enableMineToVault(self, network: str = 'main'):
        vault = self.getVault(network=network)
        mineToAddress = vault.address
        success, result = self.server.enableMineToVault(
            walletSignature=self.getWallet(
                network=network).sign(mineToAddress),
            vaultSignature=vault.sign(mineToAddress),
            vaultPubkey=vault.publicKey,
            address=mineToAddress)
        if success:
            self.mineToVault = True
        return success, result

    def disableMineToVault(self, network: str = 'main'):
        vault = self.getVault(network=network)
        wallet = self.getWallet(network=network)
        # logging.debug('wallet:', wallet, color="magenta")
        mineToAddress = wallet.address
        success, result = self.server.disableMineToVault(
            walletSignature=wallet.sign(mineToAddress),
            vaultSignature=vault.sign(mineToAddress),
            vaultPubkey=vault.publicKey,
            address=mineToAddress)
        if success:
            self.mineToVault = False
        return success, result
