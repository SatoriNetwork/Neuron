from typing import Union, Callable
import os
import time
import json
import random
import threading
from queue import Queue
import asyncio
import pandas as pd
from satorilib.concepts.structs import (
    StreamId,
    Stream,
    StreamPairs,
    StreamOverview)
from satorilib import disk
from satorilib.wallet import EvrmoreWallet
from satorilib.wallet.evrmore.identity import EvrmoreIdentity
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
from satorineuron.structs.start import RunMode, UiEndpoint, StartupDagStruct
from satorineuron.synergy.engine import SynergyManager
from satorilib.datamanager import DataClient, DataServerApi, Message, Subscription
from io import StringIO

def getStart():
    """returns StartupDag singleton"""
    return StartupDag()


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class StartupDag(StartupDagStruct, metaclass=SingletonMeta):
    """a DAG of startup tasks."""

    @classmethod
    async def create(
        cls,
        *args,
        env: str = 'dev',
        runMode: str = None,
        sendToUI: Callable = None,
        urlServer: str = None,
        urlMundo: str = None,
        urlPubsubs: list[str] = None,
        urlSynergy: str = None,
        isDebug: bool = False,
    ) -> 'StartupDag':
        '''Factory method to create and initialize StartupDag asynchronously'''
        startupDag = cls(
            *args,
            env=env,
            runMode=runMode,
            sendToUI=sendToUI,
            urlServer=urlServer,
            urlMundo=urlMundo,
            urlPubsubs=urlPubsubs,
            urlSynergy=urlSynergy,
            isDebug=isDebug)
        await startupDag.startFunction()

    def __init__(
        self,
        *args,
        env: str = 'dev',
        runMode: str = None,
        sendToUI: Callable = None,
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
        sendToUI = sendToUI or (lambda x: None)
        logging.info(f'mode: {self.runMode.name}', print=True)
        self.userInteraction = time.time()
        self.walletVaultManager: WalletVaultManager
        self.asyncThread: AsyncThread = AsyncThread()
        self.isDebug: bool = isDebug
        # self.chatUpdates: BehaviorSubject = BehaviorSubject(None)
        self.chatUpdates: Queue = Queue()
        # dictionary of connection statuses {ConnectionTo: bool}
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
        self.pubSubMapping: dict = {}
        self.identity: EvrmoreIdentity = EvrmoreIdentity(config.walletPath('wallet.yaml'))
        self.data: dict[str, dict[pd.DataFrame, pd.DataFrame]] = {}
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
        self.startFunction = self.start
        if self.runMode == RunMode.normal:
            self.startFunction = self.start
        elif self.runMode == RunMode.worker:
            self.startFunction = self.startWorker
        elif self.runMode == RunMode.wallet:
            self.startFunction = self.startWalletOnly
        # TODO: this logic must be removed - auto restart functionality should
        #       happen ouside neuron
        if not config.get().get("disable restart", False):
            self.restartThread = threading.Thread(
                target=self.restartEverythingPeriodic,
                daemon=True)
            self.restartThread.start()
        #while True:
        #    if self.asyncThread.loop is not None:
        #        self.checkinThread = self.asyncThread.repeatRun(
        #            task=startFunction,
        #            interval=60 * 60 * 24 if alreadySetup else 60 * 60 * 12,
        #        )
        #        break
        #    time.sleep(60 * 15)

        # TODO: after pubsubmap is provided to the data server,
        #       get the data for each datastream, grab all (optimize later)
        #       subscribe to everything, add the data to our in memory datasets
        #       (that updates the ui)

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

    async def dataServerFinalize(self):
        transferProtocol = self.determineTransferProtocol()
        # TODO: do something with this transfer protocol:
        #       should we support just p2p-limited or (p2p-limited and pubsub)?
        await self.sharePubSubInfo()
        await self.populateData()
        await self.subscribeToRawData()
        await self.subscribeToEngineUpdates()

    async def start(self):
        """start the satori engine."""
        await self.connectToDataServer()
        asyncio.create_task(self.stayConnectedForever())
        self.walletVaultManager.setupWalletAndVault()
        self.setMiningMode()
        self.createRelayValidation()
        self.createServerConn()
        self.checkin()
        self.setRewardAddress()
        self.subConnect()
        self.pubsConnect()
        await self.dataServerFinalize() # TODO : This should come way b4, rn we need the pub/sub info to be filled
        if self.isDebug:
            return
        self.startRelay()
        await asyncio.Event().wait() # probably place this at the end of satori.py?

    async def engine_necessary(self):
        """Below are what is necessary for the Engine to start building"""
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
        # self.populateData()
        # self.startSynergyEngine()
        self.subConnect()
        # self.pubsConnect()
        if self.isDebug:
            return
        # self.startRelay()
        self.buildEngine()
        time.sleep(60 * 60 * 24)

    async def startWalletOnly(self):
        """start the satori engine."""
        logging.info("running in walletOnly mode", color="blue")
        self.walletVaultManager.setupWalletAndVault()
        self.createServerConn()
        return

    async def startWorker(self):
        """start the satori engine."""
        logging.info("running in worker mode", color="blue")
        self.walletVaultManager.setupWalletAndVault()
        self.setMiningMode()
        self.setEngineVersion()
        self.createRelayValidation()
        self.createServerConn()
        self.checkin()
        self.setRewardAddress()
        self.populateData()
        # self.startSynergyEngine()
        self.subConnect()
        self.pubsConnect()
        if self.isDebug:
            return
        self.startRelay()
        #self.buildEngine()
        time.sleep(60 * 60 * 24)

    def updateConnectionStatus(self, connTo: ConnectionTo, status: bool):
        # logging.info('connTo:', connTo, status, color='yellow')
        self.latestConnectionStatus = {
            **self.latestConnectionStatus,
            **{connTo.name: status}}
        self.sendToUI(UiEndpoint.connectionStatus, self.latestConnectionStatus)

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

    async def populateData(self):
        """ save real and prediction data in neuron """
        for k in self.pubSubMapping.keys():
            if k != 'transferProtocol' and k != 'transferProtocolPayload':
                realDataDf = None
                predictionDataDf = None
                try:
                    realData = await self.dataClient.getLocalStreamData(k)
                    if realData.status == DataServerApi.statusSuccess.value and isinstance(realData.data, pd.DataFrame):
                        realDataDf = realData.data
                    else:
                        raise Exception(realData.senderMsg)
                except Exception as e:
                    # logging.error(e)
                    pass
                try:
                    predictionData = await self.dataClient.getLocalStreamData(self.pubSubMapping[k]['publicationUuid'])
                    if predictionData.status == DataServerApi.statusSuccess.value and isinstance(predictionData.data, pd.DataFrame):
                        predictionDataDf = predictionData.data
                    else:
                        raise Exception(predictionData.senderMsg)
                except Exception as e:
                    # logging.error(e)
                    pass
                self.data[k] = {
                    'realData': realDataDf if realDataDf is not None else pd.DataFrame([]),
                    'predictionData': predictionDataDf if predictionDataDf is not None else pd.DataFrame([])
                }

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
                    self.addModelUpdate(stream_display)
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


    @property
    def isConnectedToServer(self):
        if hasattr(self, 'dataClient') and self.dataClient is not None:
            return self.dataClient.isConnected()
        return False

    async def connectToDataServer(self):
        ''' connect to server, retry if failed '''

        async def authenticate() -> bool:
            response = await self.dataClient.authenticate(islocal='neuron')
            if response.status == DataServerApi.statusSuccess.value:
                logging.info("Local Neuron successfully connected to Server Ip at :", self.dataServerIp, color="green")
                return True
            return False

        async def initiateServerConnection() -> bool:
            ''' local neuron client authorization '''
            self.dataClient = DataClient(self.dataServerIp, identity=self.identity)
            return await authenticate()

        waitingPeriod = 10
        while not self.isConnectedToServer:
            try:
                self.dataServerIp = config.get().get('server ip', '0.0.0.0')
                if await initiateServerConnection():
                    return True
            except Exception as e:
                # logging.error("Error connecting to server ip in config : ", e)
                try:
                    self.dataServerIp = self.server.getPublicIp().text.split()[-1]
                    if await initiateServerConnection():
                        return True
                except Exception as e:
                    logging.warning(f'Failed to find a valid Server Ip, retrying in {waitingPeriod}')
                    await asyncio.sleep(waitingPeriod)
        #return False?

    async def stayConnectedForever(self):
        ''' alternative to await asyncio.Event().wait() '''
        while True:
            await asyncio.sleep(30)
            if not self.isConnectedToServer:
                await self.connectToDataServer()
                await self.dataServerFinalize()
                #await self.start()
                # should we manage all our other connections here too?
                # pubsub
                # electrumx

    def determineTransferProtocol(self) -> str:
        '''
        determine the transfer protocol to be used for data transfer
        default: p2p
        p2p - use the data server and data clients
        p2p-proactive
            - use the data server and data clients.
            - connect to my subscribers, send them the data streams they want.
                - sync historic datasets?
        pubsub
            - use the pubsub connection to subscribe to data streams.
            - does not include pub
        '''
        return config.get().get(
            'transfer protocol',
            'p2p' if self.server.loopbackCheck() else 'p2p-proactive') # TODO: we have to pass in our IP address


    async def sharePubSubInfo(self):
        ''' set Pub-Sub mapping in the authorized server '''

        def matchPubSub():
            ''' matchs related pub/sub stream '''
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

            # Below for testing Purposes
            ## this must at least run on the local server
            # add in a new subInfo and pubInfo for our mock data stream using ip address and port of the mock remote neuron server

            # subInfo = {}
            # pubInfo = {}

            # subInfo['009bb819-b737-55f5-b4d7-d851316eceae'] = {
            #     'subscribers':[],
            #     'publishers':['188.166.4.120'],
            # }

            # pubInfo['03efefc1-944c-5b02-8861-936bade65c00'] = {
            #     'subscribers':[],
            #     'publishers':[],
            # }

            # End of testing


            self.pubSubMapping = {
                sub_uuid: {
                    'publicationUuid': pub_uuid,
                    'supportiveUuid':[],
                    'dataStreamSubscribers': subInfo[sub_uuid]['subscribers'],
                    'dataStreamPublishers': subInfo[sub_uuid]['publishers'],
                    'predictiveStreamSubscribers': pubInfo[pub_uuid]['subscribers'],
                    'predictiveStreamPublishers': pubInfo[pub_uuid]['publishers']
                }
                for sub_uuid, pub_uuid in zip(subInfo.keys(), pubInfo.keys())
            }
            transferProtocol = self.determineTransferProtocol() 
            self.pubSubMapping['transferProtocol'] = transferProtocol
            if transferProtocol == 'pubsub':
                self.pubSubMapping['transferProtocolPayload'] = self.key
            elif transferProtocol == 'p2p-proactive':
                success, mySubscribers = self.server.getSubscribers()
                if success:
                    self.pubSubMapping['transferProtocolPayload'] = [ subDict.get('ip') for subDict in mySubscribers ] 
                else:
                    logging.warning("Subscriber information not available")
                    self.pubSubMapping['transferProtocolPayload'] = []
            else:
                self.pubSubMapping['transferProtocolPayload'] = None

        async def _sendPubSubMapping():
            """ send pub-sub mapping with peer informations to the DataServer """
            try:
                response = await self.dataClient.setPubsubMap(self.pubSubMapping)
                if response.status == DataServerApi.statusSuccess.value:
                    logging.debug(response.senderMsg, print=True)
                else:
                    raise Exception(response.senderMsg)
            except Exception as e:
                logging.error(f"Failed to set pub-sub mapping, {e}")

        matchPubSub()
        await _sendPubSubMapping()

    async def subscribeToRawData(self):
        ''' local neuron client subscribes to engine predication data '''

        for k in self.pubSubMapping.items():
            if k!= 'transferProtocol' and k!= 'transferProtocolPayload':
                response = await self.dataClient.subscribe(
                    peerHost=self.dataServerIp,
                    uuid=k,
                    callback=self.handleRawData)
                if response.status == DataServerApi.statusSuccess.value:
                    logging.debug('Subscribed to Raw Data', response.senderMsg, color='green')
                else:
                    logging.warning('Failed to Subscribe: ', response.senderMsg )
                    # await asyncio.sleep(10)
                    # await self.subscribeToRawData()

    async def subscribeToEngineUpdates(self):
        ''' local neuron client subscribes to engine predication data '''

        for k, v in self.pubSubMapping.items():
            if k!= 'transferProtocol' and k!= 'transferProtocolPayload':
                response = await self.dataClient.subscribe(
                    peerHost=self.dataServerIp,
                    uuid=v['publicationUuid'],
                    callback=self.handlePredictionData)
                if response.status == DataServerApi.statusSuccess.value:
                    logging.debug('Subscribed to Prediction Data', response.senderMsg, color='green')
                else:
                    logging.warning('Failed to Subscribe: ', response.senderMsg )
                    # await asyncio.sleep(10)
                    # await self.subscribeToEngineUpdates()

    async def handleRawData(self, subscription: Subscription, message: Message):

        def findMatchingStreamUuid(subUuid) -> str:
            for key in self.pubSubMapping.keys():
                if subUuid == self.pubSubMapping.get(key):
                    return key

        logging.info('Raw Data Subscribtion Message',message.to_dict(True), color='green')
        matchedStreamUuid = findMatchingStreamUuid(message.uuid)
        self.data[matchedStreamUuid]['realData'] = pd.concat([
            self.data[matchedStreamUuid]['realData'],
            message.data
        ])

    async def handlePredictionData(self, subscription: Subscription, message: Message):

        def findMatchingStreamUuid(pubUuid) -> str:
            for key in self.pubSubMapping.keys():
                if pubUuid == self.pubSubMapping.get(key, {}).get('publicationUuid'):
                    return key

        logging.info('Prediction Data Subscribtion Message',message.to_dict(True), color='green')
        matchedStreamUuid = findMatchingStreamUuid(message.uuid)
        self.data[matchedStreamUuid]['predictionData'] = pd.concat([
            self.data[matchedStreamUuid]['predictionData'],
            message.data
        ])

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

    def addWorkingUpdate(self, data: str):
        ''' tell ui we are working on something '''
        self.sendToUI(UiEndpoint.workingUpdate, data)

    def addModelUpdate(self, data: StreamOverview):
        ''' tell ui about model changes '''
        self.sendToUI(UiEndpoint.modelUpdate, data)

    def populateStreamDisplay(self):

        def streamDisplayer(subsription: Stream):
            return StreamOverview(
                streamId=subsription.streamId,
                value="",
                prediction="",
                values=[],
                predictions=[])

        self.streamDisplay = [
            streamDisplayer(subscription)
            for subscription in self.subscriptions]
        self.streamDisplay = [
            streamDisplayer(publication)
            for publication in self.publications]


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
