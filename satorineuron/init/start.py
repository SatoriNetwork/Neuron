from typing import Union
import os
import time
import json
import random
import threading
from queue import Queue
import pandas as pd
from satorilib.concepts.structs import (
    StreamId,
    Stream,
    StreamPairs,
    StreamOverview)
from satorilib import disk
from satorilib.wallet import EvrmoreWallet
from satorilib.server import SatoriServerClient
from satorilib.server.api import CheckinDetails
from satorilib.pubsub import SatoriPubSubConn
from satorilib.asynchronous import AsyncThread
import satoriengine
from satoriengine.veda.data.structs import StreamForecast
import satorineuron
from satorineuron import VERSION
from satorineuron import logging
from satorineuron import config
from satorineuron.init import engine
from satorineuron.init.tag import LatestTag, Version
from satorineuron.init.wallet import WalletVaultManager
from satorineuron.common.structs import ConnectionTo
from satorineuron.relay import RawStreamRelayEngine, ValidateRelayStream
from satorineuron.structs.start import RunMode, StartupDagStruct
from satorineuron.synergy.engine import SynergyManager
from satorilib.datamanager import DataClient
from satorilib.utils import generateUUID

def getStart():
    """returns StartupDag singleton"""
    return StartupDag()


# engine_start = StartupDag()


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class StartupDag(StartupDagStruct, metaclass=SingletonMeta):
    """a DAG of startup tasks."""

    def __init__(
        self,
        *args,
        env: str = "dev",
        runMode: str = None,
        urlServer: str = None,
        urlMundo: str = None,
        urlPubsubs: list[str] = None,
        urlSynergy: str = None,
        isDebug: bool = False,
    ):
        super(StartupDag, self).__init__(*args)
        self.version = Version(VERSION)
        # TODO: test and turn on with new installer
        # self.watchForVersionUpdates()
        self.env = env
        self.runMode = RunMode.choose(runMode)
        logging.info(f'mode: {self.runMode.name}', print=True)
        self.userInteraction = time.time()
        self.walletVaultManager: WalletVaultManager
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
        self.details: CheckinDetails = None
        self.key: str
        self.oracleKey: str
        self.idKey: str
        self.subscriptionKeys: str
        self.publicationKeys: str
        # self.ipfs: Ipfs = Ipfs()
        self.caches: dict[StreamId, disk.Cache] = {}
        self.relayValidation: ValidateRelayStream
        self.dataServerIp: str =  ''
        self.dataClient: Union[DataClient, None] = None
        self.allOracleStreams = None
        self.sub: SatoriPubSubConn = None
        self.pubs: list[SatoriPubSubConn] = []
        self.synergy: Union[SynergyManager, None] = None
        self.relay: RawStreamRelayEngine = None
        self.engine: satoriengine.Engine
        self.publications: list[Stream] = []
        self.subscriptions: list[Stream] = []
        self.streamDisplay: list = []
        self.udpQueue: Queue = Queue()  # TODO: remove
        self.stakeStatus: bool = False
        self.miningMode: bool = False
        self.stopAllSubscriptions = threading.Event()
        self.lastBlockTime = time.time()
        self.lastBridgeTime = 0
        self.poolIsAccepting: bool = False
        self.setEngineVersion()
        self.setupWalletManager()
        if not config.get().get("disable restart", False):
            self.restartThread = threading.Thread(
                target=self.restartEverythingPeriodic,
                daemon=True)
            self.restartThread.start()
        self.restartQueue: Queue = Queue()
        self.restartQueueThread = threading.Thread(
            target=self.restartWithQueue,
            args=(self.restartQueue,),
            daemon=True)
        self.restartQueueThread.start()
        self.checkinCheckThread = threading.Thread(
            target=self.checkinCheck,
            daemon=True)
        self.checkinCheckThread.start()
        # self.delayedStart()
        alreadySetup: bool = os.path.exists(config.walletPath("wallet.yaml"))
        if not alreadySetup:
            threading.Thread(target=self.delayedEngine).start()
        self.ranOnce = False
        if self.runMode == RunMode.normal:
            startFunction = self.start
        elif self.runMode == RunMode.worker:
            startFunction = self.startWorker
        elif self.runMode == RunMode.wallet:
            startFunction = self.startWalletOnly
        while True:
            if self.asyncThread.loop is not None:
                self.checkinThread = self.asyncThread.repeatRun(
                    task=startFunction,
                    interval=60 * 60 * 24 if alreadySetup else 60 * 60 * 12,
                )
                break
            time.sleep(60 * 15)

    @property
    def walletOnlyMode(self) -> bool:
        return self.runMode == RunMode.wallet

    @property
    def rewardAddress(self) -> str:
        if isinstance(self.details, CheckinDetails):
            reward = self.details.wallet.get("rewardaddress", "")
            if (
                reward not in [
                    self.details.wallet.get("address", ""),
                    self.details.wallet.get("vaultaddress", "")]
            ):
                return reward or ""
        return ""

    @property
    def network(self) -> str:
        return 'main' if self.env in ['prod', 'local'] else 'test'

    @property
    def vault(self) -> EvrmoreWallet:
        return self.walletVaultManager.vault

    @property
    def wallet(self) -> EvrmoreWallet:
        return self.walletVaultManager.wallet

    @property
    def holdingBalance(self) -> float:
        self._holdingBalance = round(
            self.wallet.balance.amount
            + (self.vault.balance.amount if self.vault is not None else 0),
            8)
        return self._holdingBalance

    def setupWalletManager(self):
        self.walletVaultManager = WalletVaultManager(
            updateConnectionStatus=self.updateConnectionStatus,
            persistent=self.runMode == RunMode.wallet)
        self.walletVaultManager.setup()

    def shutdownWallets(self):
        self.walletVaultManager.disconnect()
        self.walletVaultManager.electrumx = None
        self.walletVaultManager._wallet = None
        self.walletVaultManager._vault = None

    def closeVault(self):
        self.walletVaultManager.closeVault()

    def openVault(self, password: Union[str, None] = None, create: bool = False):
        return self.walletVaultManager.openVault(password=password, create=create)

    def getWallet(self, **kwargs):
        return self.walletVaultManager.getWallet()

    def getVault(self, password: Union[str, None] = None, create: bool = False):
        return self.walletVaultManager.getVault(password=password, create=create)

    def electrumxCheck(self):
        self.walletVaultManager.electrumxCheck()

    def watchForVersionUpdates(self):
        """
        if we notice the code version has updated, download code restart
        in order to restart we have to kill the main thread manually.
        """

        def getPidByName(name: str) -> Union[int, None]:
            """
            Returns the PID of a process given a name or partial command name match.
            If multiple matches are found, returns the first match.
            Returns None if no process is found with the given name.
            """
            import psutil

            for proc in psutil.process_iter(["pid", "cmdline"]):
                try:
                    # Check if the process command line matches the target name
                    if name in " ".join(proc.info["cmdline"]):
                        return proc.info["pid"]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue  # Process terminated or access denied, skip
            return None  # No process found with the given name

        def terminatePid(pid: int):
            import signal
            os.kill(pid, signal.SIGTERM)  # Send SIGTERM to the process

        def watchForever():
            latestTag = LatestTag(self.version, serverURL=self.urlServer)
            while True:
                time.sleep(60 * 60 * 6)
                if latestTag.mustUpdate():
                    terminatePid(getPidByName("satori.py"))

        self.watchVersionThread = threading.Thread(
            target=watchForever,
            daemon=True)
        self.watchVersionThread.start()

    def userInteracted(self):
        self.userInteraction = time.time()
        # tell engines or managers the user interacted, incase they care:
        self.walletVaultManager.userInteracted()

    def delayedEngine(self):
        time.sleep(60 * 60 * 6)
        self.buildEngine()

    def checkinCheck(self):
        while True:
            time.sleep(60 * 60 * 6)
            # loop through streams, if I haven't had an observation on a stream
            # in more than 24 hours, delete it. and restart
            # for stream in self.subscriptions:
            #    ts = timestampToSeconds(
            #        self.cacheOf(stream.streamId).getLatestObservationTime()
            #    )
            #    if ts > 0 and ts + 60*60*24 < time.time():
            #        self.server.removeStream(stream.streamId.topic())
            #        self.triggerRestart()
            if self.server.checkinCheck():
                self.triggerRestart()  # should just be start()

    def cacheOf(self, streamId: StreamId) -> Union[disk.Cache, None]:
        """returns the reference to the cache of a stream"""
        return self.caches.get(streamId)

    def networkIsTest(self, network: str = None) -> bool:
        return network.lower().strip() in ("testnet", "test", "ravencoin", "rvn")

    async def start(self):
        """start the satori engine."""
        # while True:
        if self.ranOnce:
            time.sleep(60 * 60)
        self.ranOnce = True
        if self.walletOnlyMode:
            self.walletVaultManager.setupWalletAndVault()
            self.createServerConn()
            logging.info("in WALLETONLYMODE")
            return
        self.walletVaultManager.setupWalletAndVault()
        self.setMiningMode()
        self.createRelayValidation()
        self.createServerConn()
        self.checkin()
        await self.connectToDataServer()
        await self.sharePubSubInfo()
        self.setRewardAddress()
        self.verifyCaches()
        # self.startSynergyEngine()
        self.subConnect()
        self.pubsConnect()
        if self.isDebug:
            return
        self.startRelay()
        await self.buildEngine()
        
        time.sleep(60 * 60 * 24)

    def engine_necessary(self):
        """Below are what is necessary for the Engine to start building"""
        if self.ranOnce:
            time.sleep(60 * 60)
        self.ranOnce = True
        if self.walletOnlyMode:
            self.walletVaultManager.setupWalletAndVault()
            self.createServerConn()
            return
        # self.setMiningMode()
        # self.setEngineVersion()
        # self.createRelayValidation()
        self.walletVaultManager.setupWalletAndVault()
        # self.getVault()
        self.createServerConn()
        self.checkin()
        # self.setRewardAddress()
        # self.verifyCaches()
        # self.startSynergyEngine()
        self.subConnect()
        # self.pubsConnect()
        if self.isDebug:
            return
        # self.startRelay()
        self.buildEngine()
        time.sleep(60 * 60 * 24)

    def startWalletOnly(self):
        """start the satori engine."""
        logging.info("running in walletOnly mode", color="blue")
        # while True:
        if self.ranOnce:
            time.sleep(60 * 60)
        self.ranOnce = True
        self.walletVaultManager.setupWalletAndVault()
        self.createServerConn()

    def startWorker(self):
        """start the satori engine."""
        logging.info("running in worker mode", color="blue")
        # while True:
        if self.ranOnce:
            time.sleep(60 * 60)
        self.ranOnce = True
        self.walletVaultManager.setupWalletAndVault()
        self.setMiningMode()
        self.setEngineVersion()
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
        time.sleep(60 * 60 * 24)

    def updateConnectionStatus(self, connTo: ConnectionTo, status: bool):
        # logging.info('connTo:', connTo, status, color='yellow')
        self.latestConnectionStatus = {
            **self.latestConnectionStatus,
            **{connTo.name: status}}
        self.connectionsStatusQueue.put(self.latestConnectionStatus)

    def createRelayValidation(self):
        self.relayValidation = ValidateRelayStream()
        logging.info("started relay validation engine", color="green")

    def createServerConn(self):
        logging.debug(self.urlServer, color="teal")
        self.server = SatoriServerClient(
            self.wallet, url=self.urlServer, sendingUrl=self.urlMundo
        )

    def checkin(self):
        try:
            referrer = (
                open(config.root("config", "referral.txt"), mode="r")
                .read()
                .strip())
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
                    connTo=ConnectionTo.central, status=True)
                # logging.debug(self.details, color='magenta')
                self.key = self.details.key
                self.poolIsAccepting = bool(
                    self.details.wallet.get("accepting", False))
                self.oracleKey = self.details.oracleKey
                self.idKey = self.details.idKey
                self.subscriptionKeys = self.details.subscriptionKeys
                self.publicationKeys = self.details.publicationKeys
                self.subscriptions = [
                    Stream.fromMap(x)
                    for x in json.loads(self.details.subscriptions)]
                if (
                    attempt < 5 and (
                        self.details is None or len(self.subscriptions) == 0)
                ):
                    time.sleep(30)
                    continue
                logging.info("subscriptions:", len(
                    self.subscriptions), print=True)
                # logging.info('subscriptions:', self.subscriptions, print=True)
                self.publications = [
                    Stream.fromMap(x)
                    for x in json.loads(self.details.publications)]
                logging.info(
                    "publications:",
                    len(self.publications),
                    print=True)
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
                logging.info("checked in with Satori", color="green")
                break
            except Exception as e:
                self.updateConnectionStatus(
                    connTo=ConnectionTo.central, status=False)
                logging.warning(f"connecting to central err: {e}")
            x = x * 1.5 if x < 60 * 60 * 6 else 60 * 60 * 6
            logging.warning(f"trying again in {x}")
            time.sleep(x)

    def setRewardAddress(self) -> bool:
        configRewardAddress: str = str(config.get().get("reward address", ""))
        if (
            self.env in ['prod', 'local'] and
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
        """rehashes my published hashes"""

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
        """filter down to prediciton publications"""
        # todo: doesn't work
        return [s for s in streams if s.predicting is not None]

    @staticmethod
    def oracleStreams(streams: list[Stream]):
        """filter down to prediciton publications"""
        return [s for s in streams if s.predicting is None]

    async def buildEngine(self):
        """start the engine, it will run w/ what it has til ipfs is synced"""

        def streamDisplayer(subsription: Stream):
            return StreamOverview(
                streamId=subsription.streamId,
                value="",
                prediction="",
                values=[],
                predictions=[])

        def handleNewPrediction(streamForecast: StreamForecast):
            for stream_display in self.streamDisplay:
                if stream_display.streamId == streamForecast.streamId:
                    stream_display.value = streamForecast.currentValue["value"].iloc[-1]
                    stream_display.prediction = streamForecast.forecast["pred"].iloc[0]
                    stream_display.values = [
                        value
                        for value in streamForecast.currentValue.value]
                    stream_display.predictions = [
                        value
                        for value in streamForecast.predictionHistory.value]
            logging.info(f'publishing {streamForecast.firstPrediction()} prediction for {streamForecast.predictionStreamId}', color='blue')
            # self.server.publish( # TODO : fix this for the new datamanager
            #     topic=streamForecast.predictionStreamId.topic(),
            #     data=streamForecast.forecast["pred"].iloc[0],
            #     observationTime=streamForecast.observationTime,
            #     observationHash=streamForecast.observationHash,
            #     isPrediction=True,
            #     useAuthorizedCall=self.version >= Version("0.2.6"))

        # TODO: we will have to change this some day to a mapping between the
        #       publication (key) and all the supporting subscriptions (value)
        #       because we will have a target feature stream and feature streams
        #       {publication: [primarySubscription1, subscription2, ...]}
        streamPairs = StreamPairs(
            self.subscriptions,
            StartupDag.predictionStreams(self.publications))
        self.subscriptions, self.publications = streamPairs.get_matched_pairs()
        # print([sub.streamId for sub in self.subscriptions])

        self.streamDisplay = [
            streamDisplayer(subscription)
            for subscription in self.subscriptions]

        self.engine: satoriengine.Engine = engine.getEngine(
            run=self.engineVersion == 'v1',
            subscriptions=self.subscriptions,
            publications=self.publications)
        self.engine.run()
        # else:
        #    logging.warning('Running in Local Mode.', color='green')
        if self.engineVersion == 'v2':
            self.aiengine: satoriengine.veda.engine.Engine = (
                await satoriengine.veda.engine.Engine.create()
            )
            self.aiengine.predictionProduced.subscribe(
                lambda x: handleNewPrediction(x) if x is not None else None)

    def subConnect(self):
        """establish a random pubsub connection used only for subscribing"""
        if self.sub is not None:
            self.sub.disconnect()
            self.updateConnectionStatus(
                connTo=ConnectionTo.pubsub, status=False)
            self.sub = None
        if self.key:
            signature = self.wallet.sign(self.key)
            self.sub = engine.establishConnection(
                url=random.choice(self.urlPubsubs),
                # url='ws://pubsub3.satorinet.io:24603',
                pubkey=self.wallet.publicKey,
                key=signature.decode() + "|" + self.key,
                emergencyRestart=self.emergencyRestart,
                onConnect=lambda: self.updateConnectionStatus(
                    connTo=ConnectionTo.pubsub,
                    status=True),
                onDisconnect=lambda: self.updateConnectionStatus(
                    connTo=ConnectionTo.pubsub,
                    status=False))
        else:
            time.sleep(30)
            raise Exception("no key provided by satori server")

    def pubsConnect(self):
        """
        oracle nodes publish to every pubsub machine. therefore, they have
        an additional set of connections that they mush push to.
        """
        self.pubs = []
        # oracles = oracleStreams(self.publications)
        if not self.oracleKey:
            return
        for pubsubMachine in self.urlPubsubs:
            signature = self.wallet.sign(self.oracleKey)
            self.pubs.append(
                engine.establishConnection(
                    subscription=False,
                    url=pubsubMachine,
                    pubkey=self.wallet.publicKey + ":publishing",
                    emergencyRestart=self.emergencyRestart,
                    key=signature.decode() + "|" + self.oracleKey))
    
    
    async def connectToDataServer(self):
        try:
            self.dataServerIp = config.get().get('server ip', '0.0.0.0')
            self.dataClient = DataClient(self.dataServerIp)
            await self.dataClient.sendRequest(
                        self.dataServerIp, 
                        method='initiate-server-connection')
            logging.info("Successfully connected to Server Ip at :", self.dataServerIp, color="green")
        except Exception as e:
            logging.error("Error connecting to server ip in config : ", e)
            try:
                self.dataServerIp = self.start.server.getPublicIp().text.split()[-1] # TODO : is this correct?
                self.dataClient = DataClient(self.dataServerIp)
                await self.dataClient.sendRequest(
                        self.dataServerIp, 
                        method='initiate-server-connection')
                logging.info("Successfully connected to Server Ip at :", self.dataServerIp, color="green")
            except Exception as e:
                logging.error("Failed to find a valid Server Ip : ", e)
                # TODO : maybe retry in an hour or when we are provided with a valid server Ip

    async def sharePubSubInfo(self):

        def matchPubSub() -> dict:
            ''' match related pub/sub stream and return dictionary with pub-sub mapping '''
            streamPairs = StreamPairs(
                self.subscriptions,
                StartupDag.predictionStreams(self.publications))
            self.subscriptions, self.publications = streamPairs.get_matched_pairs()
            subInfo = {
                sub.streamId.uuid: {'subscribers':['6.9.6.9', '69.96'], 'publishers':['420.123', '123.23']}
                for sub in self.subscriptions
            }
            pubInfo = {
                pub.streamId.uuid: {'subscribers':['6.9.6.9', '69.96'], 'publishers':['420.123', '123.23']}
                for pub in self.publications
            }
            return {
                sub_uuid: {
                    'publicationUuid': pub_uuid,
                    'dataStreamSubscribers': subInfo[sub_uuid]['subscribers'],
                    'dataStreamPublishers': subInfo[sub_uuid]['publishers'],
                    'predictiveStreamSubscribers': pubInfo[pub_uuid]['subscribers'],
                    'predictiveStreamPublishers': pubInfo[pub_uuid]['publishers']
                }
                for sub_uuid, pub_uuid in zip(subInfo.keys(), pubInfo.keys())
            }


        async def _sendPubSubMapping( mappingDict: dict):
            """ send pub-sub mapping with peer informations to the DataServer """
            try:
                await self.dataClient.sendRequest(
                    self.dataServerIp,
                    uuid=mappingDict,
                    method='send-pubsub-map'
                )
            except Exception as e:
                logging.error(f"Failed to send pub-sub mapping {e}")

        pubSubMapping = matchPubSub()
        await _sendPubSubMapping(pubSubMapping)


    def startRelay(self):
        def append(streams: list[Stream]):
            relays = satorineuron.config.get("relay")
            rawStreams = []
            for x in streams:
                topic = x.streamId.topic(asJson=True)
                if topic in relays.keys():
                    x.uri = relays.get(topic).get("uri")
                    x.headers = relays.get(topic).get("headers")
                    x.payload = relays.get(topic).get("payload")
                    x.hook = relays.get(topic).get("hook")
                    x.history = relays.get(topic).get("history")
                    rawStreams.append(x)
            return rawStreams

        if self.relay is not None:
            self.relay.kill()
        self.relay = RawStreamRelayEngine(streams=append(self.publications))
        self.relay.run()
        logging.info("started relay engine", color="green")

    def startSynergyEngine(self):
        """establish a synergy connection"""
        """DISABLED FOR NOW:
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
        """
        if self.wallet:
            self.synergy = SynergyManager(
                url=self.urlSynergy,
                wallet=self.wallet,
                onConnect=self.syncDatasets)
            logging.info("connected to Satori p2p network", color="green")
        else:
            raise Exception("wallet not open yet.")

    def syncDataset(self, streamId: StreamId):
        """establish a synergy connection"""
        if self.synergy and self.synergy.isConnected:
            for stream in self.subscriptions:
                if streamId == stream.streamId:
                    logging.info("resyncing stream:", stream, print=True)
                    self.synergy.connectToPeer(stream.streamId)
        # else:
        #    raise Exception('synergy not created or not connected.')

    def syncDatasets(self):
        """establish a synergy connection"""
        if self.synergy and self.synergy.isConnected:
            self.updateConnectionStatus(
                connTo=ConnectionTo.synergy, status=True)
            for stream in self.subscriptions:
                self.synergy.connectToPeer(stream.streamId)
        else:
            self.updateConnectionStatus(
                connTo=ConnectionTo.synergy, status=False)
        # else:
        #    raise Exception('synergy not created or not connected.')

    def pause(self, timeout: int = 60):
        """pause the engine."""
        self.paused = True
        # self.engine.pause()
        self.pauseThread = self.asyncThread.delayedRun(
            task=self.unpause, delay=timeout)
        logging.info("AI engine paused", color="green")

    def unpause(self):
        """pause the engine."""
        # self.engine.unpause()
        self.paused = False
        if self.pauseThread is not None:
            self.asyncThread.cancelTask(self.pauseThread)
        self.pauseThread = None
        logging.info("AI engine unpaused", color="green")

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
        alreadySetup: bool = os.path.exists(config.walletPath("wallet.yaml"))
        if alreadySetup:
            threading.Thread(target=self.delayedEngine).start()
        # while True:
        #    if self.asyncThread.loop is not None:
        #        self.restartThread = self.asyncThread.repeatRun(
        #            task=self.start,
        #            interval=60*60*24 if alreadySetup else 60*60*12)
        #        break
        #    time.sleep(1)

    def triggerRestart(self, return_code=1):
        from satorisynapse import Envelope, Signal
        self.udpQueue.put(
            Envelope(ip="", vesicle=Signal(restart=True)))  # TODO: remove
        import time
        time.sleep(5)
        # 0 = shutdown, 1 = restart container, 2 = restart app
        os._exit(return_code)

    def emergencyRestart(self):
        import time
        logging.warning("restarting in 10 minutes", print=True)
        time.sleep(60 * 10)
        self.triggerRestart()

    def restartEverythingPeriodic(self):
        import random
        restartTime = time.time() + config.get().get(
            "restartTime", random.randint(60 * 60 * 21, 60 * 60 * 24)
        )
        # # removing tag check because I think github might block vps or
        # # something when multiple neurons are hitting it at once. very
        # # strange, but it was unreachable for someone and would just hang.
        # latestTag = LatestTag()
        while True:
            if time.time() > restartTime:
                self.triggerRestart()
            time.sleep(random.randint(60 * 60, 60 * 60 * 4))
            # time.sleep(random.randint(10, 20))
            # latestTag.get()
            # if latestTag.isNew:
            #    self.triggerRestart()

    def restartWithQueue(self, queue):
        return_code = int(queue.get())  # Wait for signal
        self.triggerRestart(return_code)

    def publish(
        self,
        topic: str,
        data: str,
        observationTime: str,
        observationHash: str,
        toCentral: bool = True,
        isPrediction: bool = False,
    ) -> True:
        """publishes to all the pubsub servers"""
        # does this take proxy into account? I don't think so.
        # if self.holdingBalance < constants.stakeRequired:
        #    return False
        if not isPrediction:
            for pub in self.pubs:
                pub.publish(
                    topic=topic,
                    data=data,
                    observationTime=observationTime,
                    observationHash=observationHash)
        if toCentral:
            self.server.publish(
                topic=topic,
                data=data,
                observationTime=observationTime,
                observationHash=observationHash,
                isPrediction=isPrediction,
                useAuthorizedCall=self.version >= Version("0.2.6"))

    def performStakeCheck(self):
        self.stakeStatus = self.server.stakeCheck()
        return self.stakeStatus

    def setMiningMode(self, miningMode: Union[bool, None] = None):
        miningMode = (
            miningMode
            if isinstance(miningMode, bool)
            else config.get().get('mining mode', True))
        self.miningMode = miningMode
        config.add(data={'mining mode': self.miningMode})
        if hasattr(self, 'server') and self.server is not None:
            self.server.setMiningMode(miningMode)
        return self.miningMode

    def setEngineVersion(self, version: Union[str, None] = None) -> str:
        default = 'v2'
        version = (
            version
            if version in ['v1', 'v2']
            else config.get().get('engine version', default))
        self.engineVersion = version if version in ['v1', 'v2'] else default
        config.add(data={'engine version': self.engineVersion})
        return self.engineVersion

    def poolAccepting(self, status: bool):
        success, result = self.server.poolAccepting(status)
        if success:
            self.poolIsAccepting = status
        return success, result

    def getAllOracleStreams(self, searchText: Union[str, None] = None, fetch: bool = False):
        if fetch or self.allOracleStreams is None:
            self.allOracleStreams = self.server.getSearchStreams(
                searchText=searchText)
        return self.allOracleStreams

    def ableToBridge(self):
        if self.lastBridgeTime < time.time() + 60*60*1:
            return True, ''
        return False, 'Please wait at least an hour before Bridging Satori'
