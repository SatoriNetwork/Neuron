from typing import Union
import os
import time
import shutil
import threading
from queue import Queue
from satorilib.electrumx import Electrumx
from satorilib.api.wallet import EvrmoreWallet
from satorineuron import logging
from satorineuron import config
from satorineuron.common.structs import ConnectionTo
from satorineuron.structs.start import RunMode


class WalletVaultManager():
    """ Wallets Manager """

    @staticmethod
    def performMigrationBackup(name: str = "wallet"):
        if (
            os.path.exists(config.walletPath(f"{name}.yaml")) and
            not os.path.exists(config.walletPath(f"{name}-migration-backup.yaml"))
        ):
            shutil.copy(
                config.walletPath(f"{name}.yaml"),
                config.walletPath(f"{name}-migration-backup.yaml"),
            )

    def __init__(self, runMode: RunMode, updateConnectionStatus: callable):
        self.runMode = RunMode.choose(runMode)
        self.electrumx: Electrumx = None
        self._wallet: Union[EvrmoreWallet, None] = None
        self._vault: Union[EvrmoreWallet, None] = None
        self.connectionsStatusQueue: Queue = Queue()
        self.stopAllSubscriptions = threading.Event()
        self.updateConnectionStatus = updateConnectionStatus
        self.userInteraction = time.time()

    def setup(self):
        WalletVaultManager.performMigrationBackup("wallet")
        WalletVaultManager.performMigrationBackup("vault")
        self.createElectrumxConnection()
        if self.runMode != RunMode.worker:
            self.walletTimeoutSeconds = 60 * 20
            self.walletTimeoutThread = threading.Thread(
                target=self.walletTimeoutWatcher,
                daemon=True)
            self.walletTimeoutThread.start()

    @property
    def vault(self) -> EvrmoreWallet:
        return self._vault

    @property
    def wallet(self) -> EvrmoreWallet:
        return self._wallet

    def disconnectWallets(self):
        if self.electrumx is not None:
            self.stopAllSubscriptions.set()
            self.electrumx = None
            self.wallet.electrumx = None
            if self.vault is not None:
                self.vault.electrumx = None
            self.walletTimeoutSeconds = 60 * 60

    def reconnectWallets(self):
        self.stopAllSubscriptions.clear()
        self.createElectrumxConnection()
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
            self.walletTimeoutSeconds = 60 * 20

    def initializeWalletAndVault(self, force: bool = False):
        if not self.electrumxCheck():
            self.createElectrumxConnection()
        self._initializeWallet(force=force)
        self._initializeVault(
            password=None,
            create=False,
            force=force)
        return self.setupSubscriptions()

    def setupSubscriptions(self):
        # Setup subscriptions fpr header and scripthash
        if self.electrumx is not None and self.electrumx.connected():
            self._wallet.setupSubscriptions()
            self._wallet.subscribe()
            if self._vault is not None:
                self._vault.setupSubscriptions()
                self._vault.subscribe()

            # test - both show as being subscribed to...
            # time.sleep(5)
            # self._wallet.stopSubscription()
            # time.sleep(5)
            # self._vault.stopSubscription()
            # time.sleep(10)
            # self.stopAllSubscriptions.set()
            # exit()

            # Get Transaction history in separate threads
            self._wallet.callTransactionHistory()
            if self._vault is not None:
                self._vault.callTransactionHistory()

    # new method
    def _initializeWallet(self, force: bool = False) -> EvrmoreWallet:
        if not force and self._wallet is not None:
            return self._wallet
        self._wallet = EvrmoreWallet(
            walletPath=config.walletPath("wallet.yaml"),
            reserve=0.25,
            isTestnet=False,
            electrumx=self.electrumx,
            type="wallet")
        self._wallet()
        logging.info("initialized Wallet", color="green")
        return self._wallet

    def _initializeVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
        force: bool = False,
    ) -> Union[EvrmoreWallet, None]:
        vaultPath = config.walletPath("vault.yaml")
        if not os.path.exists(vaultPath) and not create:
            return None
        try:
            if not force and self._vault is not None:
                if self._vault.password is None and password is not None:
                    self._vault.open(password)
                    return self._vault
                elif password is None or self._vault.password == password:
                    return self._vault
            self._vault = EvrmoreWallet(
                walletPath=vaultPath,
                reserve=0.25,
                isTestnet=False,
                password=password,
                electrumx=self.electrumx,
                type="vault")
            self._vault()
            logging.info("initialized Vault", color="green")
            return self._vault
        except Exception as e:
            logging.error(
                f"failed to open Vault: {str(e)}", color="red")
            raise e

    def getWallet(self, *args, **kwargs) -> EvrmoreWallet:
        if self._wallet is not None:
            return self._wallet
        return self._initializeWallet()

    def getVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> EvrmoreWallet:
        if self._vault is not None:
            return self._vault
        return self._initializeVault(password=password, create=create)

    def electrumxCheck(self) -> bool:
        """returns connection status to electrumx"""
        if self.electrumx is None or not self.electrumx.connected():
            self.updateConnectionStatus(
                connTo=ConnectionTo.electrumx, status=False)
            return False
        else:
            self.updateConnectionStatus(
                connTo=ConnectionTo.electrumx, status=True)
            return True

    def closeVault(self) -> Union[EvrmoreWallet, None]:
        """close the vault, reopen it without decrypting it."""
        if self._vault is not None:
            try:
                self._vault.close()
            except Exception as e:
                logging.error(f"Error closing vault: {str(e)}", color="red")

    def openWallet(self, *args, **kwargs) -> Union[EvrmoreWallet, None]:
        return self.getWallet()

    def openVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[EvrmoreWallet, None]:
        """
        without a password it will open the vault (if it exists) but not decrypt
        it. this allows us to get it's balance, but not spend from it.
        """
        if self._vault is None:
            return self._initializeVault(password=password, create=create)
        self.closeVault()
        return self.getVault(password=password, create=create)

    def createElectrumxConnection(self, hostPort: str = None):
        try:
            self.electrumx = EvrmoreWallet.createElectrumxConnection(hostPort)
        except Exception as e:
            logging.warning(
                "unable to connect to electrum opperating without wallet abilities:", e
            )
