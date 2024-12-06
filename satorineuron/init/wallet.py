from typing import Union
import os
import time
import shutil
from queue import Queue
from satorilib.electrumx import Electrumx
from satorilib.wallet import EvrmoreWallet
from satorineuron import logging
from satorineuron import config
from satorineuron.common.structs import ConnectionTo


class WalletVaultManager():
    ''' Wallets Manager '''

    @staticmethod
    def performMigrationBackup(name: str = "wallet"):
        if (
            os.path.exists(config.walletPath(f"{name}.yaml")) and
            not os.path.exists(config.walletPath(
                f"{name}-migration-backup.yaml"))
        ):
            shutil.copy(
                config.walletPath(f"{name}.yaml"),
                config.walletPath(f"{name}-migration-backup.yaml"))

    def __init__(
        self,
        updateConnectionStatus: callable,
        persistent: bool = False
    ):
        self.persistent = persistent
        self.updateConnectionStatus = updateConnectionStatus
        self.electrumx: Electrumx = None
        self._wallet: Union[EvrmoreWallet, None] = None
        self._vault: Union[EvrmoreWallet, None] = None
        self.connectionsStatusQueue: Queue = Queue()
        self.userInteraction = time.time()

    @property
    def vault(self) -> EvrmoreWallet:
        return self._vault

    @property
    def wallet(self) -> EvrmoreWallet:
        return self._wallet

    def setup(self):
        WalletVaultManager.performMigrationBackup("wallet")
        WalletVaultManager.performMigrationBackup("vault")
        self.createElectrumxConnection()

    def disconnect(self):
        if isinstance(self.electrumx, Electrumx):
            self.electrumx.disconnect()
            self.electrumx = None

    def reconnect(self):
        self.setupWalletAndVault(force=True)

    def userInteracted(self):
        self.userInteraction = time.time()
        if not self.electrumxCheck():
            self.reconnect()

    def electrumxCheck(self) -> bool:
        ''' returns connection status to electrumx '''
        if isinstance(self.electrumx, Electrumx) and self.electrumx.connected():
            self.updateConnectionStatus(
                connTo=ConnectionTo.electrumx,
                status=True)
            return True
        self.updateConnectionStatus(
            connTo=ConnectionTo.electrumx,
            status=False)
        return False

    def createElectrumxConnection(self, hostPort: str = None):
        try:
            self.electrumx = EvrmoreWallet.createElectrumxConnection(
                hostPort=hostPort,
                persistent=self.persistent)
            logging.info('initialized electrumx', color='green')
        except Exception as e:
            logging.warning((
                'unable to connect to electrumx, '
                'continuing without wallet abilities... error:\n'),
                e)

    def setupSubscriptions(self):
        if self.electrumxCheck():
            # self.electrumx.api.subscribeToHeaders() # for testing
            if isinstance(self._wallet, EvrmoreWallet):
                self._wallet.subscribeToScripthashActivity()
                #self._wallet.subscribe()
                #self._wallet.callTransactionHistory()
            if isinstance(self._vault, EvrmoreWallet):
                self._vault.subscribeToScripthashActivity()
                #self._vault.subscribe()
                #self._vault.callTransactionHistory()

    def _initializeWallet(self, force: bool = False) -> EvrmoreWallet:
        if not force and self._wallet is not None:
            return self._wallet
        self._wallet = EvrmoreWallet(
            walletPath=config.walletPath('wallet.yaml'),
            reserve=0.25,
            isTestnet=False,
            electrumx=self.electrumx,
            type='wallet')
        self._wallet()
        logging.info('initialized wallet', color='green')
        return self._wallet

    def _initializeVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
        force: bool = False,
    ) -> Union[EvrmoreWallet, None]:
        vaultPath = config.walletPath('vault.yaml')
        if not os.path.exists(vaultPath) and not create:
            return None
        try:
            if not force and isinstance(self._vault, EvrmoreWallet):
                if (
                    self._vault.password is None
                    and isinstance(password, str)
                    and len(password) > 0
                ):
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
                type='vault')
            self._vault()
            logging.info('initialized vault', color='green')
            return self._vault
        except Exception as e:
            logging.error(
                f'failed to open Vault: {str(e)}', color='red')
            raise e

    def setupWalletAndVault(self, force: bool = False):
        if not self.electrumxCheck():
            self.createElectrumxConnection()
        self._initializeWallet(force=force)
        self._initializeVault(
            password=None,
            create=False,
            force=force)
        return self.setupSubscriptions()

    def getWallet(self, *args, **kwargs) -> EvrmoreWallet:
        if isinstance(self._wallet, EvrmoreWallet):
            return self._wallet
        return self._initializeWallet()

    def getVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> EvrmoreWallet:
        if isinstance(self._vault, EvrmoreWallet):
            return self._vault
        return self._initializeVault(password=password, create=create)

    def openVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> EvrmoreWallet:
        if isinstance(self._vault, EvrmoreWallet):
            if self._vault.isDecrypted:
                return self._vault
            self._vault.open(password)
            return self._vault
        return self._initializeVault(password=password, create=create)

    def closeVault(self) -> Union[EvrmoreWallet, None]:
        ''' close the vault, reopen it without decrypting it. '''
        if isinstance(self._vault, EvrmoreWallet):
            self._vault.close()
        return self._vault