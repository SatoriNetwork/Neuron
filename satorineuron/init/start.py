from typing import Union
from threading import Thread, Event
import os
import time
import json
import random
import threading

from reactivex.subject import BehaviorSubject
from queue import Queue
import satorineuron
import satoriengine
from satoriwallet.api.blockchain import Electrumx
from satorilib.concepts.structs import StreamId, Stream
from satorilib.api import disk
from satorilib.api.wallet import RavencoinWallet, EvrmoreWallet
# from satorilib.api.ipfs import Ipfs
from satorilib.server import SatoriServerClient
from satorilib.server.api import CheckinDetails
from satorilib.pubsub import SatoriPubSubConn
from satorilib.asynchronous import AsyncThread
from satorineuron import VERSION
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
        walletOnlyMode: bool = False,
        urlServer: str = None,
        urlMundo: str = None,
        urlPubsubs: list[str] = None,
        urlSynergy: str = None,
        isDebug: bool = False
    ):
        super(StartupDag, self).__init__(*args)
        self.version = [int(x) for x in VERSION.split('.')]
        self.env = env
        self.walletOnlyMode = walletOnlyMode
        self.userInteraction = time.time()
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
        self.electrumx: Electrumx = None
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
        self.stopAllSubscriptions = threading.Event()
        self.walletTimeoutSeconds = 60*20
        self.walletTimeoutThread = threading.Thread(
            target=self.walletTimeoutWatcher, daemon=True)
        self.walletTimeoutThread.start()
        self.lastBlockTime = time.time()
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

    def disconnectWallets(self):
        if self.electrumx is not None:
            self.stopAllSubscriptions.set()
            self.electrumx = None
            self.wallet.electrumx = None
            self.vault.electrumx = None
            self.walletTimeoutSeconds = 60*60

    def reconnectWallets(self):
        self.stopAllSubscriptions.clear()
        self.setupElectrumxConnection()
        self.initializeWalletAndVault(force=True)

    def walletTimeoutWatcher(self):
        while True:
            time.sleep(self.walletTimeoutSeconds)
            if self.userInteraction < time.time() - self.walletTimeoutSeconds:
                self.disconnectWallets()

    def userInteracted(self):
        self.userInteraction = time.time()
        if not self.electrumxCheck():
            self.reconnectWallets()
            self.walletTimeoutSeconds = 60*1

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

    # @property
    # def ravencoinWallet(self) -> RavencoinWallet:
    #     if self._ravencoinWallet is None:
    #         self._ravencoinWallet = RavencoinWallet(
    #             config.walletPath('wallet.yaml'),
    #             reserve=0.25,
    #             isTestnet=self.networkIsTest('ravencoin'))
    #     return self._ravencoinWallet

    # @property
    # def evrmoreWallet(self) -> EvrmoreWallet:
    #     if self._evrmoreWallet is None:
    #         self._evrmoreWallet = EvrmoreWallet(
    #             config.walletPath('wallet.yaml'),
    #             reserve=0.25,
    #             isTestnet=self.networkIsTest('evrmore'))
    #     return self._evrmoreWallet

    def initializeWalletAndVault(self, network: str = None, force: bool = False):
        # Initialize wallets
        network = network or self.network
        if self.networkIsTest(network):
            self._initialize_wallet('ravencoin', force=force)
            self._initialize_vault("ravencoin", None, False, force=force)
        walletInstance = self._initialize_wallet(
            'evrmore', self.electrumx, force=force)
        vaultInstance = self._initialize_vault(
            "evrmore", None, False, self.electrumx, force=force)
        # Setup subscriptions fpr header and scripthash
        walletInstance.setupSubscriptions()
        vaultInstance.setupSubscriptions()
        # Start a thread to listen for updates
        self.processThread = Thread(
            target=self._processNotifications)
        self.processThread.start()
        # Get Transaction history in separate threads
        walletInstance.callTransactionHistory()
        vaultInstance.callTransactionHistory()

    # _processNotifications method to listening for updates
    def _processNotifications(self):
        """
        Processes incoming notifications for the subscribed scripthash and headers.
        """
        logging.debug("_processNotifications started")
        try:
            for notification in self.electrumx.receive_notifications():
                logging.debug(f"Received notification {notification}")
                if self.stopAllSubscriptions.is_set():
                    logging.debug("Stop event set, breaking loop")
                    break
                if 'method' in notification:
                    if notification['method'] == 'blockchain.scripthash.subscribe':
                        if 'params' in notification and len(notification['params']) == 2:
                            scripthash, status = notification['params']
                            if self._evrmoreWallet.scripthash == scripthash:
                                logging.debug(
                                    f"Received update for wallet scripthash {scripthash}: {status}")
                                if callable(self._evrmoreWallet.get):
                                    self._evrmoreWallet.get()
                                if callable(self._evrmoreWallet.callTransactionHistory):
                                    self._evrmoreWallet.callTransactionHistory()
                            if self._evrmoreVault.scripthash == scripthash:
                                logging.debug(
                                    f"Received update for vault scripthash {scripthash}: {status}")
                                if callable(self._evrmoreVault.get):
                                    self._evrmoreVault.get()
                                if callable(self._evrmoreVault.callTransactionHistory):
                                    self._evrmoreVault.callTransactionHistory()
                    elif notification['method'] == 'blockchain.headers.subscribe':
                        if 'params' in notification and len(notification['params']) > 0:
                            header = notification['params'][0]
                            logging.debug(
                                f"Received new block header: height {header.get('height')}, hash {header.get('hex')[:64]}")
                            self.lastBlockTime = time.time()
                            # if callable(self.onBlockNotification):
                            #     self.onBlockNotification(notification)
                    else:
                        logging.error(
                            f"Received unknown method: {notification['method']}")
        except Exception as e:
            logging.error(f"Error in _processNotifications: {str(e)}")
        logging.debug("_processNotifications ended")

    # new method
    def _initialize_wallet(self, network: str, connection: Electrumx = None, force: bool = False) -> Union[EvrmoreWallet, RavencoinWallet, None]:
        wallet_class = EvrmoreWallet if network == 'evrmore' else RavencoinWallet
        wallet_attr = '_evrmoreWallet' if network == 'evrmore' else '_ravencoinWallet'
        # try:
        if not force:
            existing_wallet = getattr(self, wallet_attr)
            if existing_wallet is not None:
                return existing_wallet
        wallet = wallet_class(
            walletPath=config.walletPath('wallet.yaml'),
            reserve=0.25,
            isTestnet=self.networkIsTest(network),
            connection=connection,
            type="wallet")
        setattr(self, wallet_attr, wallet)
        wallet()
        logging.info(f'initialized {network.title()} wallet', color='green')
        return wallet
        # except Exception as e:
        #    logging.error(
        #        f'failed to initialize {network} wallet: {str(e)}', color='red')
        #    return None

    # new method
    def _initialize_vault(self, network: str, password: Union[str, None] = None, create: bool = False, connection: Electrumx = None, force: bool = False) -> Union[EvrmoreWallet, RavencoinWallet, None]:
        vault_path = config.walletPath('vault.yaml')
        wallet_class = EvrmoreWallet if network == 'evrmore' else RavencoinWallet
        vault_attr = '_evrmoreVault' if network == 'evrmore' else '_ravencoinVault'
        if not os.path.exists(vault_path) and not create:
            return None
        try:
            if not force:
                existing_vault = getattr(self, vault_attr)
                if existing_vault is not None:
                    if existing_vault.password is None and password is not None:
                        existing_vault.open(password)
                        logging.info(
                            f'opened existing {network} vault with password', color='green')
                        return existing_vault
                    elif password is None or existing_vault.password == password:
                        return existing_vault
            vault = wallet_class(
                walletPath=vault_path,
                reserve=0.25,
                isTestnet=self.networkIsTest(network),
                password=password,
                connection=connection,
                type="vault")
            setattr(self, vault_attr, vault)
            vault()
            logging.info(f'initialized {network.title()} vault', color='green')
            return vault
        except Exception as e:
            logging.error(
                f'failed to open {network} vault: {str(e)}', color='red')
            raise e

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
            return self._ravencoinWallet
        return self._evrmoreWallet

    def getVault(
        self,
        network: str = None,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[EvrmoreWallet, RavencoinWallet]:
        network = network or self.network
        if self.networkIsTest(network):
            return self._initialize_vault("ravencoin", password, create)
        return self._initialize_vault("evrmore", password, create)

    def electrumxCheck(self) -> bool:
        ''' returns connection status to electrumx '''
        if self.electrumx is None or not self.electrumx.connected():
            self.updateConnectionStatus(
                connTo=ConnectionTo.electrumx,
                status=False)
            return False
        else:
            self.updateConnectionStatus(
                connTo=ConnectionTo.electrumx,
                status=True)
            return True

    def closeVault(self) -> Union[RavencoinWallet, EvrmoreWallet, None]:
        ''' close the vault, reopen it without decrypting it. '''
        for vault_attr in ['_ravencoinVault', '_evrmoreVault']:
            vault = getattr(self, vault_attr)
            if vault is not None:
                try:
                    vault.close()
                except Exception as e:
                    logging.error(
                        f'Error closing vault: {str(e)}', color='red')

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
        network = network or self.network
        return self.getVault(network, password, create)

    def start(self):
        ''' start the satori engine. '''
        # while True:
        if self.ranOnce:
            time.sleep(60*60)
        self.ranOnce = True
        self.setupElectrumxConnection()
        if self.walletOnlyMode:
            self.initializeWalletAndVault()
            self.createServerConn()
            return
        self.initializeWalletAndVault()
        self.setMiningMode()
        self.createRelayValidation()
        self.createServerConn()
        self.checkin()
        self.setRewardAddress()
        self.verifyCaches()
        # self.startSynergyEngine()
        self.subConnect()
        self.pubsConnect()
        if self.isDebug:
            return
        self.startRelay()
        self.buildEngine()
        time.sleep(60*60*24)

    def setupElectrumxConnection(self):
        self.createElectrumxConnection()
        # if you want it to continue to connect all the time, enable this
        # self.monitorLastBlockTimeThread = threading.Thread(
        #    target=self.monitorLastBlockTime, daemon=True)
        # self.monitorLastBlockTimeThread.start()

    # updated one
    def monitorLastBlockTime(self):
        logging.info("monitorLastBlockTime called", color="yellow")
        while True:
            time.sleep(60)  # Check every minute
            logging.info(
                f"Last block Time {time.time()} and {self.lastBlockTime} and {time.time() - self.lastBlockTime}", color="green")
            if time.time() - self.lastBlockTime > 300:  # 10 minutes in seconds
                logging.info(
                    "lastBlockTime not updated in 10 minutes, reconnecting to server.", color="yellow")
                try:
                    # end the last process thread
                    logging.info("Connection started", color="green")
                    # Reconnect to the server
                    self.createElectrumxConnection()
                    self._evrmoreWallet.connection = self.electrumx
                    self._evrmoreWallet.electrumx.conn = self.electrumx
                    self._evrmoreWallet.electrumx.lastHandshake = time.time()
                    self._evrmoreVault.connection = self.electrumx
                    self._evrmoreVault.electrumx.conn = self.electrumx
                    self._evrmoreVault.electrumx.lastHandshake = time.time()
                    logging.info(
                        "Connection done, starting processing again", color="green")
                    self.lastBlockTime = time.time()
                    self._evrmoreWallet.setupSubscriptions()
                    self._evrmoreVault.setupSubscriptions()
                    logging.info(
                        "Starting the thread for the process notification")
                    self.processThread = Thread(
                        target=self._processNotifications)
                    self.processThread.start()
                except Exception as e:
                    logging.error(f"Error while reconnecting {e}")

    def createElectrumxConnection(self):
        servers: list[str] = [
            '146.190.149.237:50002',
            '146.190.38.120:50002',
            'electrum1-mainnet.evrmorecoin.org:50002',
            'electrum2-mainnet.evrmorecoin.org:50002']
        serversSubscription: list[str] = [
            '146.190.149.237:50001',
            '146.190.38.120:50001',
            'electrum1-mainnet.evrmorecoin.org:50001',
            'electrum2-mainnet.evrmorecoin.org:50001']
        hostPort = random.choice(servers)
        hostPortSubscription = random.choice(serversSubscription)
        self.electrumx = Electrumx(
            host=hostPort.split(':')[0],
            port=int(hostPort.split(':')[1]),
            hostSubscription=hostPortSubscription.split(':')[0],
            portSubscription=int(hostPortSubscription.split(':')[1]))

    def updateConnectionStatus(self, connTo: ConnectionTo, status: bool):
        # logging.info('connTo:', connTo, status, color='yellow')
        self.latestConnectionStatus = {
            **self.latestConnectionStatus,
            **{connTo.name: status}}
        self.connectionsStatusQueue.put(self.latestConnectionStatus)

    def createRelayValidation(self):
        self.relayValidation = ValidateRelayStream()
        logging.info('started relay validation engine', color='green')

    def createServerConn(self):
        logging.debug(self.urlServer, color='teal')
        self.server = SatoriServerClient(
            self.wallet, url=self.urlServer, sendingUrl=self.urlMundo)

    def checkin(self):
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

    def setRewardAddress(self) -> bool:
        configRewardAddress: str = str(config.get().get('reward address', ''))
        if (
            self.env == 'prod' and
            len(configRewardAddress) == 34 and
            configRewardAddress.startswith('E') and
            self.rewardAddress != configRewardAddress
        ):
            self.server.setRewardAddress(
                signature=self.wallet.sign(configRewardAddress),
                pubkey=self.wallet.publicKey,
                address=configRewardAddress)
            return True
        return False

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
        # # removing tag check because I think github might block vps or
        # # something when multiple neurons are hitting it at once. very
        # # strange, but it was unreachable for someone and would just hang.
        # latestTag = LatestTag()
        while True:
            if time.time() > restartTime:
                self.triggerRestart()
            time.sleep(random.randint(60*60, 60*60*4))
            # time.sleep(random.randint(10, 20))
            # latestTag.get()
            # if latestTag.isNew:
            #    self.triggerRestart()

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
