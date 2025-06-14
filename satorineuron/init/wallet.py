from typing import Union, Optional, Callable
import os
import shutil
from satorineuron import logging
from satorilib.wallet.evrmore.wallet import EvrmoreWallet
from satorilib.wallet.evrmore.identity import EvrmoreIdentity
from satorilib.electrumx.electrumx import Electrumx
from satorineuron import config
from satorineuron.common.structs import ConnectionTo


class WalletManager:

    @staticmethod
    def create(
        walletPath: Optional[str] = None,
        vaultPath: Optional[str] = None,
        vaultPassword: Optional[str] = None,
        cachePath: Optional[str] = None,
        peersCache: Optional[str] = None,
        updateConnectionStatus: Optional[Callable] = None
    ) -> 'WalletManager':
        """
        Create a new WalletManager instance with wallet and vault.
        
        Args:
            walletPath: Path to the wallet YAML file
            vaultPath: Path to the vault YAML file
            vaultPassword: Password for the vault
            cachePath: Path to cache directory
            peersCache: Path to peers cache file
        """
        walletPath = walletPath or config.walletPath('wallet.yaml')
        vaultPath = vaultPath or config.walletPath('vault.yaml')
        vaultPassword = vaultPassword or str(config.get().get('vault password'))
        
        # Only create vault if we have both a password and the file doesn't exist yet
        createVault = vaultPassword is not None and not os.path.exists(vaultPath)
        
        WalletManager.performMigrationBackup("wallet")
        WalletManager.performMigrationBackup("vault")
        manager = WalletManager()
        manager.setup(walletPath, vaultPath, vaultPassword, createVault, cachePath, peersCache, updateConnectionStatus)
        return manager

    @staticmethod
    def performMigrationBackup(name: str = "wallet"):
        if (
            os.path.exists(config.walletPath(f"{name}.yaml")) and
            not os.path.exists(config.walletPath(f"{name}.yaml.bak"))
        ):
            shutil.copy2(
                config.walletPath(f"{name}.yaml"),
                config.walletPath(f"{name}.yaml.bak"))

    def __init__(self):
        self._wallet: Optional[EvrmoreWallet] = None
        self._vault: Optional[EvrmoreWallet] = None
        self._electrumx: Optional[Electrumx] = None
        self._updateConnectionStatus: Optional[Callable] = None

    def setup(
        self,
        walletPath: str,
        vaultPath: str,
        vaultPassword: str,
        createVault: bool,
        cachePath: Optional[str] = None,
        peersCache: Optional[str] = None,
        updateConnectionStatus: Optional[Callable] = None,
    ):
        self._initializeWallet(walletPath, cachePath, peersCache)
        self._initializeVault(vaultPath, cachePath, peersCache, vaultPassword, createVault)
        self._updateConnectionStatus = updateConnectionStatus

    def _initializeWallet(
        self,
        walletPath: str,
        cachePath: Optional[str] = None,
        peersCache: Optional[str] = None,
    ) -> EvrmoreWallet:
        """Initialize the wallet, which doesn't require a password."""
        if self._wallet is not None:
            return self._wallet
        self._wallet = EvrmoreWallet.create(
            walletPath=walletPath,
            cachePath=cachePath,
            identity=EvrmoreIdentity(walletPath),
            persistent=False,  # We want lazy connection
            cachedPeersFile=peersCache
        )
        logging.info('initialized wallet', color='green')
        return self._wallet

    def _initializeVault(
        self,
        vaultPath: str,
        cachePath: Optional[str] = None,
        peersCache: Optional[str] = None,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[EvrmoreWallet, None]:
        """
        Initialize the vault based on different scenarios:
        1. No vault file exists and no password: Return None (wait for password)
        2. No vault file exists and have password: Create new vault
        3. Vault file exists: Try to load it (will be encrypted if password not provided)
        """
        try:
            # Case 1: No vault file and no password - wait for password
            if not os.path.exists(vaultPath) and not create:
                return None

            # Case 2: Existing vault instance - handle password updates
            if isinstance(self._vault, EvrmoreWallet):
                if (
                    self._vault.password is None
                    and isinstance(password, str)
                    and len(password) > 0
                ):
                    # Decrypt existing vault with new password
                    self._vault.open(password)
                    return self._vault
                elif password is None or self._vault.password == password:
                    # Return existing vault if no password change needed
                    return self._vault

            # Case 3: Create new vault or load existing vault
            self._vault = EvrmoreWallet.create(
                walletPath=vaultPath,
                identity=EvrmoreIdentity(vaultPath, password=password),
                cachePath=cachePath,
                persistent=False,  # We want lazy connection
                cachedPeersFile=peersCache
            )
            logging.info('initialized vault', color='green')
            return self._vault
            
        except Exception as e:
            logging.error(f'failed to open Vault: {str(e)}', color='red')
            raise e

    def connect(self) -> bool:
        """
        Ensures there is a valid Electrumx connection, creating or reconnecting as needed.
        Returns True if connection is successful, False otherwise.
        """
        try:
            if not self.isConnected():
                # Try to reconnect if needed
                try:
                    self._electrumx.reconnect()
                except Exception as e:
                    logging.debug(f"Failed to reconnect to Electrumx: {e}")
                    self._electrumx = None  # Force new connection creation
            
            # Create new connection if needed
            if not self._electrumx:
                self._electrumx = Electrumx.create(
                hostPorts=config.get().get('electrumx servers'),
                persistent=False)
            
            if self.isConnected():
                # Update wallet and vault with current electrumx instance
                if self._wallet:
                    self._wallet.electrumx = self._electrumx
                if self._vault:
                    self._vault.electrumx = self._electrumx
                self._updateConnectionStatus(
                    connTo=ConnectionTo.electrumx,
                    status=True)
                return True
            self._updateConnectionStatus(
                connTo=ConnectionTo.electrumx,
                status=False)
            return False
        except Exception as e:
            logging.error(f"Failed to establish Electrumx connection: {e}")
            return False

    def isConnected(self) -> bool:
        """Check if there is a valid and active Electrumx connection."""
        return (
            self._electrumx is not None 
            and self._electrumx.connected()
        )

    @property
    def wallet(self) -> Optional[EvrmoreWallet]:
        """Get the wallet instance without ensuring connection."""
        return self._wallet

    @property
    def vault(self) -> Optional[EvrmoreWallet]:
        """Get the vault instance without ensuring connection."""
        return self._vault

    def openVault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[EvrmoreWallet, None]:
        if isinstance(self._vault, EvrmoreWallet):
            if self._vault.isDecrypted:
                return self._vault
            self._vault.open(password)
            return self._vault
        return self._initializeVault(password=password, create=create)

    def closeVault(self) -> Union[EvrmoreWallet, None]:
        """Close the vault, reopen it without decrypting it."""
        if isinstance(self._vault, EvrmoreWallet):
            self._vault.close()
        return self._vault
