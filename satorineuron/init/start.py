from typing import Union, Callable
import os
import time
import json
import random
import threading
from queue import Queue
from eth_account import Account
import asyncio
import pandas as pd
from satorilib.concepts.structs import (
    StreamId,
    Stream,
    StreamPairs,
    StreamOverview)
from satorilib import disk
from satorilib.concepts import constants
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
from satorineuron.init.wallet import WalletManager
from satorineuron.common.structs import ConnectionTo
from satorineuron.relay import RawStreamRelayEngine, ValidateRelayStream
from satorineuron.structs.start import RunMode, UiEndpoint, StartupDagStruct
from satorilib.datamanager import DataClient, DataServerApi, DataClientApi, Message, Subscription
from satorilib.utils.ip import getPublicIpv4UsingCurl
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

    _holdingBalanceBase_cache = None
    _holdingBalanceBase_timestamp = 0

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
            isDebug=isDebug)
        await startupDag.startFunction()
        return startupDag

    def __init__(
        self,
        *args,
        env: str = 'dev',
        runMode: str = None,
        sendToUI: Callable = None,
        urlServer: str = None,
        urlMundo: str = None,
        urlPubsubs: list[str] = None,
        isDebug: bool = False,
    ):
        super(StartupDag, self).__init__(*args)
        self.needsRestart: Union[str, None] = None
        self.version = Version(VERSION)
        # TODO: test and turn on with new installer
        # self.watchForVersionUpdates()
        self.env = env
        self.runMode = RunMode.choose(runMode or config.get().get('mode', None))
        self.sendToUI = sendToUI or (lambda x: None)
        logging.debug(f'mode: {self.runMode.name}', print=True)
        self.userInteraction = time.time()
        self.walletManager: WalletManager
        self.asyncThread: AsyncThread = AsyncThread()
        self.isDebug: bool = isDebug
        # self.chatUpdates: BehaviorSubject = BehaviorSubject(None)
        self.chatUpdates: Queue = Queue()
        # dictionary of connection statuses {ConnectionTo: bool}
        self.latestConnectionStatus: dict = {}
        self.urlServer: str = urlServer
        self.urlMundo: str = urlMundo
        self.urlPubsubs: list[str] = urlPubsubs
        self.paused: bool = False
        self.pauseThread: Union[threading.Thread, None] = None
        self.details: CheckinDetails = CheckinDetails(raw={})
        self.balances: dict = {}
        self.key: str
        self.oracleKey: str
        self.idKey: str
        self.subscriptionKeys: str
        self.publicationKeys: str
        # self.ipfs: Ipfs = Ipfs()
        self.relayValidation: ValidateRelayStream
        self.dataServerIp: str =  ''
        self.dataServerPort: Union[int, None] =  None
        self.dataClient: Union[DataClient, None] = None
        self.allOracleStreams = None
        self.sub: SatoriPubSubConn = None
        self.pubs: list[SatoriPubSubConn] = []
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
        self.transferProtocol: Union[str, None] = None
        self.invitedBy: str = None
        self.setInvitedBy()
        self.latestObservationTime: float = 0
        self.configRewardAddress: str = None
        self.setRewardAddress()
        self.setEngineVersion()
        self.setupWalletManager()
        self.ip = getPublicIpv4UsingCurl()
        self.restartQueue: Queue = Queue()
        # self.checkinCheckThread = threading.Thread( # TODO: clean up after making sure the newer async works well
        #     target=self.checkinCheck,
        #     daemon=True)
        # self.checkinCheckThread.start()
        asyncio.create_task(self.checkinCheck())
        # self.delayedStart()
        alreadySetup: bool = os.path.exists(config.walletPath("wallet.yaml"))
        if not alreadySetup:
            threading.Thread(target=self.delayedEngine).start()
        self.ranOnce = False
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
            return self.details.get('rewardaddress')
        return self.configRewardAddress
        #if isinstance(self.details, CheckinDetails):
        #    return self.details.rewardAddress
        #return self.configRewardAddress

    @property
    def network(self) -> str:
        return 'main' if self.env in ['prod', 'local', 'testprod'] else 'test'

    @property
    def vault(self) -> EvrmoreWallet:
        return self.walletManager.vault

    @property
    def wallet(self) -> EvrmoreWallet:
        return self.walletManager.wallet

    @property
    def holdingBalance(self) -> float:
        if self.wallet.balance.amount > 0:
            self._holdingBalance = round(
                self.wallet.balance.amount
                + (self.vault.balance.amount if self.vault is not None else 0),
                8)
        else:
            self._holdingBalance = self.getBalance()
        return self._holdingBalance

    def refreshBalance(self, threaded: bool = True, forWallet: bool = True, forVault: bool = True):
        self.walletManager.connect()
        if forWallet and isinstance(self.wallet, EvrmoreWallet):
            if threaded:
                threading.Thread(target=self.wallet.get).start()
            else:
                self.wallet.get()
        if forVault and isinstance(self.vault, EvrmoreWallet):
            if threaded:
                threading.Thread(target=self.vault.get).start()
            else:
                self.vault.get()
        return self.holdingBalance

    def refreshUnspents(self, threaded: bool = True, forWallet: bool = True, forVault: bool = True):
        self.walletManager.connect()
        if forWallet and isinstance(self.wallet, EvrmoreWallet):
            if threaded:
                threading.Thread(target=self.wallet.getReadyToSend).start()
            else:
                self.wallet.getReadyToSend()
        if forVault and isinstance(self.vault, EvrmoreWallet):
            if threaded:
                threading.Thread(target=self.vault.getReadyToSend).start()
            else:
                self.vault.getReadyToSend()
        return self._holdingBalance

 #  api basescan version
 #  @property
 #   def holdingBalanceBase(self) -> float:
 #       """
 #       Get Satori from Base 5 min interval
 #       """
 #       import requests
 #       current_time = time.time()
 #       cache_timeout = 60 * 5
 #       if self._holdingBalanceBase_cache is not None and (current_time - self._holdingBalanceBase_timestamp) < cache_timeout:
 #           return self._holdingBalanceBase_cache
 #       eth_address = self.vault.ethAddress
 #       #base_api_url = "https://api.basescan.org/api"
 #       params = {
 #           "module": "account",
 #           "action": "tokenbalance",
 #           "contractaddress": "0xc1c37473079884CbFCf4905a97de361FEd414B2B",
 #           "address": eth_address,
 #           "tag": "latest",
 #           "apikey": "xxx"
 #       }
 #       try:
 #           response = requests.get(base_api_url, params=params)
 #           response.raise_for_status()
 #           data = response.json()
 #           if data.get("status") == "1":
 #               token_balance = int(data.get("result", 0)) / (10 ** 18)
 #               self._holdingBalanceBase_cache = token_balance
 #               self._holdingBalanceBase_timestamp = current_time
 #               print(f"Connecting to Base node OK")
 #               return token_balance
 #           else:
 #               print(f"Error API: {data.get('message', 'Unknown Error')}")
 #               return 0
 #       except requests.RequestException as e:
 #           print(f"Error connecting to API: {e}")
 #           return 0

    @property
    def holdingBalanceBase(self) -> float:
        """
        Get Satori from Base with 5-minute interval cache
        """
        # TEMPORARY DISABLE
        return 0
        
        import requests
        import time

        current_time = time.time()
        cache_timeout = 60 * 5
        if self._holdingBalanceBase_cache is not None and (current_time - self._holdingBalanceBase_timestamp) < cache_timeout:
            return self._holdingBalanceBase_cache
        eth_address = self.vault.ethAddress
        base_api_url = "https://base-mainnet.g.alchemy.com/v2/wdwSzh0cONBj81_XmHWvODOBq-wuQiAi"
        payload = {
            "jsonrpc": "2.0",
            "method": "alchemy_getTokenBalances",
            "params": [
                eth_address,
                ["0xc1c37473079884CbFCf4905a97de361FEd414B2B"]
            ],
            "id": 1
        }
        headers = {"Content-Type": "application/json"}
        try:
            response = requests.post(base_api_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            if "result" in data and "tokenBalances" in data["result"]:
                balance_hex = data["result"]["tokenBalances"][0]["tokenBalance"]
                token_balance = int(balance_hex, 16) / (10 ** 18)
                self._holdingBalanceBase_cache = token_balance
                self._holdingBalanceBase_timestamp = current_time
                print(f"Connecting to Base node OK")
                return token_balance
            else:
                print(f"API Error: Unexpected response format")
                return 0
        except requests.RequestException as e:
            print(f"Error connecting to API: {e}")
            return 0

    @property
    def ethaddressforward(self) -> str:
        eth_address = self.vault.ethAddress
        if eth_address:
            return eth_address
        else:
        #    print("Ethereum address not found")
            return ""
    @property
    def evrvaultaddressforward(self) -> str:
        evrvaultaddress = self.details.wallet.get('vaultaddress', '')
        if evrvaultaddress:
            return evrvaultaddress
        else:
        #    print("EVR Vault address not found")
            return ""


    def setupWalletManager(self):
        self.walletManager = WalletManager.create(
            update_connection_status=self.updateConnectionStatus)

    def shutdownWallets(self):
        self.walletManager._electrumx = None
        self.walletManager._wallet = None
        self.walletManager._vault = None

    def closeVault(self):
        self.walletManager.closeVault()

    def openVault(self, password: Union[str, None] = None, create: bool = False):
        return self.walletManager.openVault(password=password, create=create)

    def getWallet(self, **kwargs):
        return self.walletManager.wallet

    def getVault(self, password: Union[str, None] = None, create: bool = False) -> Union[EvrmoreWallet, None]:
        return self.walletManager.openVault(password=password, create=create)

    def electrumxCheck(self):
        if self.walletManager.isConnected():
            self.updateConnectionStatus(
                connTo=ConnectionTo.electrumx, 
                status=True)
            return True
        else:
            self.updateConnectionStatus(
                connTo=ConnectionTo.electrumx, 
                status=False)
            return False

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

    def delayedEngine(self):
        time.sleep(60 * 60 * 6)
        self.buildEngine()

    # TODO: clean up after making sure the newer async works well
    # def checkinCheck(self):
    #     while True:
    #         time.sleep(60 * 60 * 6)
    #         # loop through streams, if I haven't had an observation on a stream
    #         # in more than 24 hours, delete it. and restart
    #         # for stream in self.subscriptions:
    #         #    ts = timestampToSeconds(
    #         #        self.cacheOf(stream.streamId).getLatestObservationTime()
    #         #    )
    #         #    if ts > 0 and ts + 60*60*24 < time.time():
    #         #        self.server.removeStream(stream.streamId.jsonId)
    #         #        self.triggerRestart()
    #         if self.latestObservationTime + 60*60*6 < time.time():
    #             self.triggerRestart()
    #         if self.server.checkinCheck():
    #             self.triggerRestart()

    async def checkinCheck(self):
        while True:
            await asyncio.sleep(60 * 60 * 6) 
            current_time = time.time()
            if self.latestObservationTime and (current_time - self.latestObservationTime > 60*60*6):
                logging.warning("No observations in 6 hours, restarting")
                self.triggerRestart()
            if hasattr(self.server, 'checkinCheck') and self.server.checkinCheck():
                logging.warning("Server check failed, restarting") 
                self.triggerRestart()

    def networkIsTest(self, network: str = None) -> bool:
        return network.lower().strip() in ("testnet", "test", "ravencoin", "rvn")

    async def dataServerFinalize(self):
        await self.sharePubSubInfo()
        await self.populateData()
        await self.subscribeToRawData()
        await self.subscribeToEngineUpdates()

    async def start(self):
        """start the satori engine."""
        await self.connectToDataServer()
        asyncio.create_task(self.stayConnectedForever())
        # while True:
        if self.ranOnce:
            time.sleep(60 * 60)
        self.ranOnce = True
        if self.walletOnlyMode:
            self.createServerConn()
            self.checkin()
            self.getBalances()
            logging.info("in WALLETONLYMODE")
            return
        self.setMiningMode()
        self.createRelayValidation()
        self.createServerConn()
        self.checkin()
        self.getBalances()
        self.pubsConnect()
        await self.dataServerFinalize() 
        if self.isDebug:
            return
        self.startRelay()

    def startWalletOnly(self):
        """start the satori engine."""
        logging.info("running in walletOnly mode", color="blue")
        self.createServerConn()
        return

    async def startWorker(self):
        """start the satori engine."""
        logging.info("running in worker mode", color="blue")
        await self.connectToDataServer()
        asyncio.create_task(self.stayConnectedForever())
        self.setMiningMode()
        self.createRelayValidation()
        self.createServerConn()
        self.checkin()
        self.getBalances()
        self.pubsConnect()
        await self.dataServerFinalize() 
        if self.isDebug:
            return
        self.startRelay()
        await asyncio.Event().wait() # probably place this at the end of satori.py?

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
                vault = self.getVault()
                self.details = CheckinDetails(
                    self.server.checkin(
                        referrer=referrer,
                        ip=self.ip,
                        vaultInfo={
                            'vaultaddress': vault.address, 
                            'vaultpubkey': vault.publicKey,
                        } if isinstance(vault, EvrmoreWallet) else None))
                
                if self.details.get('sponsor') != self.invitedBy:
                    if self.invitedBy is None:
                        self.setInvitedBy(self.details.get('sponsor'))
                    if isinstance(self.invitedBy, str) and len(self.invitedBy) == 34 and self.invitedBy.startswith('E'):
                        self.server.invitedBy(self.invitedBy)

                if config.get().get('prediction stream', 'notExisting') == 'notExisting':
                    config.add(data={'prediction stream': None})

                self.server.setDataManagerPort(self.dataServerPort)

                if self.details.get('rewardaddress') != self.configRewardAddress:
                    if self.configRewardAddress is None:
                        self.setRewardAddress(address=self.details.get('rewardaddress'))
                    else:
                        self.setRewardAddress(globally=True)

                self.updateConnectionStatus(
                    connTo=ConnectionTo.central, 
                    status=True)
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
                logging.debug("subscriptions:", len(
                    self.subscriptions), print=True)
                self.publications = [
                    Stream.fromMap(x)
                    for x in json.loads(self.details.publications)]
                logging.debug(
                    "publications:",
                    len(self.publications),
                    print=True)
                logging.info("checked in with Satori", color="green")
                break
            except Exception as e:
                self.updateConnectionStatus(
                    connTo=ConnectionTo.central,
                    status=False)
                logging.warning(f"connecting to central err: {e}")
            x = x * 1.5 if x < 60 * 60 * 6 else 60 * 60 * 6
            logging.warning(f"trying again in {x}")
            time.sleep(x)

    def getBalances(self):
        '''
        we get this from the server, not electrumx
        example:
        {
            'currency': 100,
            'chain_balance': 0,
            'liquidity_balance': None,
        }
        '''
        success, self.balances = self.server.getBalances()
        if not success:
            logging.warning("Failed to get balances from server")
        return success, self.balances
    
    def getBalance(self, currency: str = 'currency') -> float:
        return self.balances.get(currency, 0)

    def setRewardAddress(
        self,
        address: Union[str, None] = None,
        globally: bool = False
    ) -> bool:
        if EvrmoreWallet.addressIsValid(address):
            self.configRewardAddress = address
            config.add(data={'reward address': address})
            if isinstance(self.details, CheckinDetails):
                self.details.setRewardAddress(address)
            if not globally:
                return True
        else:
            self.configRewardAddress: str = str(config.get().get('reward address', ''))
        if (
            globally and
            self.env in ['prod', 'local', 'testprod'] and
            EvrmoreWallet.addressIsValid(self.configRewardAddress)
        ):
            self.server.setRewardAddress(
                signature=self.wallet.sign(self.configRewardAddress),
                pubkey=self.wallet.publicKey,
                address=self.configRewardAddress)
            return True
        return False

    async def populateData(self):
        """ save real and prediction data in neuron """
        for k in self.pubSubMapping.keys():
            if k != 'transferProtocol' and k != 'transferProtocolPayload' and k != 'transferProtocolKey':
                realDataDf = None
                predictionDataDf = None
                try:
                    realData = await self.dataClient.getLocalStreamData(k)
                    if realData.status == DataServerApi.statusSuccess.value and isinstance(realData.data, pd.DataFrame):
                        realDataDf = realData.data.tail(100)
                    else:
                        raise Exception(realData.senderMsg)
                except Exception as e:
                    # logging.error(e)
                    pass
                try:
                    predictionData = await self.dataClient.getLocalStreamData(self.pubSubMapping[k]['publicationUuid'])
                    if predictionData.status == DataServerApi.statusSuccess.value and isinstance(predictionData.data, pd.DataFrame):
                        predictionDataDf = predictionData.data.tail(100)
                    else:
                        raise Exception(predictionData.senderMsg)
                except Exception as e:
                    # logging.error(e)
                    pass

                self.data[k] = {
                    'realData': realDataDf.tail(100) if realDataDf is not None else pd.DataFrame([]),
                    'predictionData': predictionDataDf.tail(100) if predictionDataDf is not None else pd.DataFrame([])
                }
                if ((realDataDf is not None and not realDataDf.empty) or 
                (predictionDataDf is not None and not predictionDataDf.empty)):
                    self.updateStreamDisplay(self.findMatchingPubSubStream(k).streamId)

    @staticmethod
    def predictionStreams(streams: list[Stream]):
        """filter down to prediciton publications"""
        # todo: doesn't work
        return [s for s in streams if s.predicting is not None]

    @staticmethod
    def oracleStreams(streams: list[Stream]):
        """filter down to prediciton publications"""
        return [s for s in streams if s.predicting is None]

    def streamDisplayer(self, subsription: Stream):
        return StreamOverview(
            streamId=subsription.streamId,
            value="",
            prediction="",
            values=[],
            predictions=[])
    
    def removePair(self, pub: StreamId, sub: StreamId):
        self.publications = [p for p in self.publications if p.streamId != pub]
        self.subscriptions = [s for s in self.subscriptions if s.streamId != sub]

    def addToEngine(self, stream: Stream, publication: Stream):
        if self.aiengine is not None:
            self.aiengine.addStream(stream, publication)

    def getMatchingStream(self, streamId: StreamId) -> Union[StreamId, None]:
        for stream in self.publications:
            if stream.streamId == streamId:
                return stream.predicting  # predicting is already a StreamId
            if stream.predicting == streamId:  # comparing StreamId objects directly
                return stream.streamId
        return None
    
    def removePair(self, pub: StreamId, sub: StreamId):
        self.publications = [p for p in self.publications if p.streamId != pub]
        self.subscriptions = [s for s in self.subscriptions if s.streamId != sub]

    def addToEngine(self, stream: Stream, publication: Stream):
        if self.aiengine is not None:
            self.aiengine.addStream(stream, publication)

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
            self.dataClient = DataClient(self.dataServerIp, self.dataServerPort, identity=self.identity)
            return await authenticate()

        waitingPeriod = 10
        while not self.isConnectedToServer:
            try:
                self.dataServerIp = config.get().get('server ip', '0.0.0.0')
                self.dataServerPort = int(config.get().get('server port', 24600))
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

    async def stayConnectedForever(self):
        ''' alternative to await asyncio.Event().wait() '''
        while True:
            await asyncio.sleep(30)
            if not self.isConnectedToServer:
                await self.connectToDataServer()
                await self.dataServerFinalize()

    def determineTransferProtocol(self, ipAddr: str, port: int = 24600) -> str:
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
            'p2p-pubsub' if self.server.loopbackCheck(ipAddr, port) else 'p2p-proactive-pubsub')
    
    def determineInternalNatIp(self) -> str:
        """Determine the internal NAT IP address using multiple methods."""
        
        import socket
        import subprocess
        import re
        import ipaddress

        # Method 1: Using socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ipaddress.ip_address(ip).is_private:
                return ip
        except Exception as e:
            logging.debug(f"Socket method failed: {e}")
        
        # Method 2: Parse output of ip address command
        try:
            result = subprocess.run(["ip", "addr", "show"], capture_output=True, text=True)
            output = result.stdout
            interfaces = {}
            current_iface = None
            
            for line in output.splitlines():
                iface_match = re.match(r'^\d+:\s+(\w+):', line)
                if iface_match:
                    current_iface = iface_match.group(1)
                    if current_iface == 'lo' or current_iface.startswith(('docker', 'br-', 'veth')):
                        current_iface = None
                elif current_iface and 'inet ' in line:
                    ip_match = re.search(r'inet\s+(\d+\.\d+\.\d+\.\d+)', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        if not ip.startswith('127.') and ipaddress.ip_address(ip).is_private:
                            interfaces[current_iface] = ip
            
            # First try specific interface prefixes
            priority_prefixes = ['eth', 'ens', 'eno', 'enp', 'wlan']
            for prefix in priority_prefixes:
                for iface, ip in interfaces.items():
                    if iface.startswith(prefix):
                        return ip
            
            # Then try any available private IP
            if interfaces:
                return next(iter(interfaces.values()))
                    
        except Exception as e:
            logging.error(f"IP command method failed: {e}")
        
        # Method 3: Fallback to hostname command
        try:
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
            ips = result.stdout.strip().split()
            for ip in ips:
                if ipaddress.ip_address(ip).is_private:
                    return ip
        except Exception as e:
            logging.error(f"Hostname method failed: {e}")
        
        return "0.0.0.0"


    async def sharePubSubInfo(self):
        ''' set Pub-Sub mapping in the authorized server '''
        def matchPubSub():
            ''' matchs related pub/sub stream '''
            streamPairs = StreamPairs(
                self.subscriptions,
                StartupDag.predictionStreams(self.publications))
            subscriptions, publications = streamPairs.get_matched_pairs()
            self.streamDisplay = [
                self.streamDisplayer(subscription)
                for subscription in subscriptions]
            predictionStreamsToPredict = config.get().get('prediction stream', None)
            if predictionStreamsToPredict is not None:
                streamsLen = int(predictionStreamsToPredict)
                logging.info(f"Length of Streams reduced from {len(subscriptions)} to {streamsLen}")
            else:
                streamsLen = len(subscriptions)
            subList = [sub.streamId.uuid for sub in subscriptions[:streamsLen]]
            pubList = [pub.streamId.uuid for pub in publications[:streamsLen]]
            pubListAll = [pub.streamId.uuid for pub in self.publications]
            _, fellowSubscribers = self.server.getStreamsSubscribers(subList)
            success, mySubscribers = self.server.getStreamsSubscribers(pubListAll)
            _, remotePublishers = self.server.getStreamsPublishers(subList)
            _, meAsPublisher = self.server.getStreamsPublishers(pubList)
            _, hostInfo = self.server.getStreamsPublishers(pubListAll)

            # removing duplicates ( same ip and port )
            for data in [fellowSubscribers, mySubscribers, remotePublishers, meAsPublisher]:
                for key in data:
                    seen = set()
                    data[key] = [x for x in data[key] if not (x in seen or seen.add(x))]

            logging.debug("My Subscribers", mySubscribers, print=True)
            logging.debug("hostInfo", hostInfo, print=True)
            logging.debug("remotePublishers", remotePublishers, print=True)

            hostIpAndPort = next((value for value in hostInfo.values() if value), [])

            # Handle empty `hostInfo` or hostIpAndPort is not known case
            if not hostInfo or not hostIpAndPort:
                logging.warning("Host Info is empty. Using default Pro-active protocol.")
                self.transferProtocol = 'p2p-proactive-pubsub' # a good usecase for 'pubsub'?
            else:
                logging.debug('Host Ip And Port', hostIpAndPort, print=True)
                hostIp = hostIpAndPort[0].split(':')[0]
                for k, v in remotePublishers.items():
                    publisherIp = v[0].split(':')[0]
                    if publisherIp == hostIp:
                        uuidOfMatchedIp = k
                        portOfMatchedIp = v[0].split(':')[1]
                        internalNatIp = self.determineInternalNatIp()
                        publisherToBeAppended = internalNatIp + ':' + portOfMatchedIp
                        for k, v in fellowSubscribers.items():
                            # Appending the internal NAT ip if remotePublisher has same ip as of the host
                            if k == uuidOfMatchedIp:
                                logging.debug("Appended remotePublisher Ip with Port:", publisherToBeAppended, print=True)
                                v.append(publisherToBeAppended)
                self.transferProtocol = self.determineTransferProtocol(
                    hostIp, self.dataServerPort)
                logging.debug('transferProtocol', self.transferProtocol, print=True)
                    
            subInfo = {
                uuid: {
                    'subscribers': fellowSubscribers.get(uuid, []),
                    'publishers': remotePublishers.get(uuid, [])}
                for uuid in subList
            }
            pubInfo = {
                uuid: {
                    'subscribers': mySubscribers.get(uuid, []),
                    'publishers': meAsPublisher.get(uuid, [])}
                for uuid in pubList
            }

            self.pubSubMapping = {
                sub_uuid: {
                    'publicationUuid': pub_uuid,
                    'supportiveUuid': [],
                    'dataStreamSubscribers': subInfo[sub_uuid]['subscribers'],
                    'dataStreamPublishers': subInfo[sub_uuid]['publishers'],
                    'predictiveStreamSubscribers': pubInfo[pub_uuid]['subscribers'],
                    'predictiveStreamPublishers': pubInfo[pub_uuid]['publishers']
                }
                for sub_uuid, pub_uuid in zip(subInfo.keys(), pubInfo.keys())
            }
            self.pubSubMapping['transferProtocol'] = self.transferProtocol

            if self.transferProtocol == 'p2p-proactive-pubsub': # p2p-proactive-pubsub
                self.pubSubMapping['transferProtocolPayload'] = mySubscribers if success else {}
                self.pubSubMapping['transferProtocolKey'] = self.key
            elif self.transferProtocol == 'p2p-pubsub':
                self.pubSubMapping['transferProtocolKey'] = self.key
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

        for k in self.pubSubMapping.keys():
            if k!= 'transferProtocol' and k!= 'transferProtocolPayload' and k != 'transferProtocolKey':
                response = await self.dataClient.subscribe(
                    uuid=k,
                    callback=self.handleRawData)
                if response.status == DataServerApi.statusSuccess.value:
                    logging.debug('Subscribed to Raw Data', response.senderMsg)
                else:
                    logging.warning('Failed to Subscribe: ', response.senderMsg )

    async def subscribeToEngineUpdates(self):
        ''' local neuron client subscribes to engine predication data '''

        for k, v in self.pubSubMapping.items():
            if k!= 'transferProtocol' and k!= 'transferProtocolPayload' and k != 'transferProtocolKey':
                response = await self.dataClient.subscribe(
                    uuid=v['publicationUuid'],
                    callback=self.handlePredictionData)
                if response.status == DataServerApi.statusSuccess.value:
                    logging.debug('Subscribed to Prediction Data', response.senderMsg)
                else:
                    logging.warning('Failed to Subscribe: ', response.senderMsg )

    async def handleRawData(self, subscription: Subscription, message: Message):

        if message.status != DataClientApi.streamInactive.value:
            logging.info('Raw Data Subscribtion Message',message.to_dict(True), color='green')
            updated_data  = pd.concat([
                self.data[message.uuid]['realData'],
                message.data
            ])
            self.data[message.uuid]['realData'] = updated_data.tail(100)
            self.latestObservationTime = time.time()
        else:
            logging.warning('Raw Data Subscribtion Message',message.to_dict(True))

    async def handlePredictionData(self, subscription: Subscription, message: Message):

        def findMatchingSubUuid(pubUuid) -> str:
            for key in self.pubSubMapping.keys():
                if pubUuid == self.pubSubMapping.get(key, {}).get('publicationUuid'):
                    return key

        if message.status != DataClientApi.streamInactive.value:
            logging.info('Prediction Data Subscribtion Message',message.to_dict(True), color='green')
            matchedSubUuid = findMatchingSubUuid(message.uuid)
            matchedPubStream = self.findMatchingPubSubStream(message.uuid, False)
            matchedSubStream = self.findMatchingPubSubStream(matchedSubUuid)

            if not message.replace: # message.replace is False if its prediction on cadence
                self.server.publish(
                    topic=matchedPubStream.streamId.jsonId,
                    data=str(message.data['value'].iloc[0]),
                    observationTime=str(message.data.index[0]),
                    observationHash=str(message.data['hash'].iloc[0]),
                    isPrediction=True,
                    useAuthorizedCall=self.version >= Version("0.2.6"))
            
            updatedPredictionData  = pd.concat([
                self.data[matchedSubUuid]['predictionData'],
                message.data
            ])
            self.data[matchedSubUuid]['predictionData'] = updatedPredictionData.tail(100)
            self.updateStreamDisplay(matchedSubStream.streamId)
        else:
            logging.warning('Prediction Data Subscribtion Message',message.to_dict(True))

    def startRelay(self):
        def append(streams: list[Stream]):
            relays = satorineuron.config.get("relay")
            rawStreams = []
            for x in streams:
                topic = x.streamId.jsonId
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

    def findMatchingPubSubStream(self, uuid: str, sub: bool = True) -> Stream:
            if sub:
                for sub in self.subscriptions:
                    if sub.streamId.uuid == uuid:
                        return sub
            else:
                for pub in self.publications:
                    if pub.streamId.uuid == uuid:
                        return pub

    def updateStreamDisplay(self, streamId: StreamId) -> None:
        """
        Update stream display with new value and prediction 
        """
        for stream_display in self.streamDisplay:
            if stream_display.streamId == streamId:
                uuid = streamId.uuid
                if uuid in self.data:
                    realData = self.data[uuid]['realData']
                    predData = self.data[uuid]['predictionData']
                    alignedRealData, alignedPredData = self.alignPredDataWithRealData(realData, predData)
                    if alignedRealData.empty or alignedPredData.empty:
                        continue
                    stream_display.value = str(alignedRealData['value'].iloc[-1])
                    stream_display.values = [str(val) for val in alignedRealData['value']]
                    stream_display.prediction = str(predData['value'].iloc[-1])
                    stream_display.predictions = [str(val) for val in alignedPredData['value']]
                    self.addModelUpdate(stream_display)
                    break

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

    def setInvitedBy(self, address: Union[str, None] = None) -> str:
        address = address or config.get().get('invited by', address)
        if address:
            self.invitedBy = address
            config.add(data={'invited by': self.invitedBy})
        return self.invitedBy

    def poolAccepting(self, status: bool):
        success, result = self.server.poolAccepting(status)
        if success:
            self.poolIsAccepting = status
        return success, result

    # def getAllOracleStreams(self, searchText: Union[str, None] = None, fetch: bool = False):
    #     if fetch or self.allOracleStreams is None:
    #         self.allOracleStreams = self.server.getSearchStreams(
    #             searchText=searchText)
    #     return self.allOracleStreams


    def getPaginatedOracleStreams(self, page: int = 1, per_page: int = 100, searchText: Union[str, None] = None, 
                            sort_by: str = 'popularity', order: str = 'desc', force_refresh: bool = False) -> tuple[list, dict]:
        """ Get paginated oracle streams (recommended approach) """
        try:
            page = max(1, page)
            per_page = min(max(1, per_page), 200)
            
            offset = (page - 1) * per_page
            
            streams, total_count = self.server.getSearchStreamsPaginated(
                searchText=searchText,
                page=page,
                per_page=per_page,
                sort_by=sort_by,
                order=order
            )
            
            total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
            has_prev = page > 1
            has_next = page < total_pages
            
            pagination_info = {
                'current_page': page,
                'total_pages': total_pages,
                'total_count': total_count,
                'has_prev': has_prev,
                'has_next': has_next,
                'per_page': per_page
            }
            return streams, pagination_info
            
        except Exception as e:
            logging.error(f"Error in getPaginatedOracleStreams: {str(e)}")
            return [], {
                'current_page': page,
                'total_pages': 0,
                'total_count': 0,
                'has_prev': False,
                'has_next': False,
                'per_page': per_page
            }

    def ableToBridge(self):
        if self.lastBridgeTime < time.time() + 60*60*1:
            return True, ''
        return False, 'Please wait at least an hour before Bridging Satori'

    @property
    def stakeRequired(self) -> float:
        return self.details.stakeRequired or constants.stakeRequired

    @property
    def admin(self) -> float:
        ''' check if the wallet is an admin, shows admin abilities '''
        if self.wallet is None:
            return False
        return self.wallet.address in ['EKHXCC6vGU3VfrGsRFnfBGLkvm6EENsXaB']
    
    def alignPredDataWithRealData(self, realDataDf, predictionDataDf) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Align prediction data with the NEXT real data point. Used for aligning the raw data with pred data in the UI
        """
        if realDataDf.empty or predictionDataDf.empty:
            return realDataDf, predictionDataDf
        
        # Ensure datetime index and sort
        realDataDf.index = pd.to_datetime(realDataDf.index)
        predictionDataDf.index = pd.to_datetime(predictionDataDf.index)
        realDataDf = realDataDf.sort_index()
        predictionDataDf = predictionDataDf.sort_index()
        
        # Calculate cadence from real data (median time difference between consecutive points)
        if len(realDataDf) < 2:
            cadence_minutes = 10  # Default fallback
        else:
            time_diffs = realDataDf.index.to_series().diff().dropna()
            cadence_seconds = time_diffs.median().total_seconds()
            cadence_minutes = max(1, cadence_seconds / 60)  # At least 1 minute
        
        # We need at least 2 real data points for this alignment strategy
        if len(realDataDf) < 2:
            return pd.DataFrame(), pd.DataFrame()
        
        aligned_real = []
        aligned_predictions = []
        
        # Start from the second real data point (index 1) since we need the previous point
        for i in range(1, len(realDataDf)):
            current_real_timestamp = realDataDf.index[i]
            previous_real_timestamp = realDataDf.index[i-1]
            current_real_row = realDataDf.iloc[i]
            
            # Define prediction window: from previous real data timestamp to just before current
            window_start = previous_real_timestamp
            window_end = current_real_timestamp - pd.Timedelta(seconds=1)
            
            # Find predictions within this window
            prediction_mask = (
                (predictionDataDf.index >= window_start) & 
                (predictionDataDf.index <= window_end)
            )
            
            window_predictions = predictionDataDf[prediction_mask]
            
            if not window_predictions.empty:
                # Take the latest prediction in the window (closest to current real data)
                latest_prediction = window_predictions.iloc[-1]
                
                aligned_real.append(current_real_row)
                aligned_predictions.append(latest_prediction)
        
        # Convert to DataFrames with sequential indices
        if aligned_real:
            aligned_real_df = pd.DataFrame(aligned_real)
            aligned_predictions_df = pd.DataFrame(aligned_predictions)
            
            # Reset indices to be sequential
            aligned_real_df.reset_index(drop=True, inplace=True)
            aligned_predictions_df.reset_index(drop=True, inplace=True)
            
            return aligned_real_df, aligned_predictions_df
        else:
            return pd.DataFrame(), pd.DataFrame()
