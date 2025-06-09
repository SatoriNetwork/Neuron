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
        wallet_path: Optional[str] = "wallet.yaml",
        vault_path: Optional[str] = "vault.yaml",
        vault_password: Optional[str] = None,
        cache_path: Optional[str] = None,
        peers_cache: Optional[str] = None,
        update_connection_status: Optional[Callable] = None
    ) -> 'WalletManager':
        """
        Create a new WalletManager instance with wallet and vault.
        
        Args:
            wallet_path: Path to the wallet YAML file
            vault_path: Path to the vault YAML file
            vault_password: Password for the vault
            cache_path: Path to cache directory
            peers_cache: Path to peers cache file
        """
        wallet_path = wallet_path or config.walletPath('wallet.yaml')
        vault_path = vault_path or config.walletPath('vault.yaml')
        vault_password = vault_password or str(config.get().get('vault password'))
        
        # Only create vault if we have both a password and the file doesn't exist yet
        create_vault = vault_password is not None and not os.path.exists(vault_path)
        
        WalletManager.performMigrationBackup("wallet")
        WalletManager.performMigrationBackup("vault")
        manager = WalletManager()
        manager.setup(wallet_path, vault_path, vault_password, create_vault, cache_path, peers_cache, update_connection_status)
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
        self._update_connection_status: Optional[Callable] = None

    @property
    def wallet(self) -> Optional[EvrmoreWallet]:
        """Get the wallet instance without ensuring connection."""
        return self._wallet

    @property
    def vault(self) -> Optional[EvrmoreWallet]:
        """Get the vault instance without ensuring connection."""
        return self._vault

    def setup(
        self,
        wallet_path: str,
        vault_path: str,
        vault_password: str,
        create_vault: bool,
        cache_path: Optional[str] = None,
        peers_cache: Optional[str] = None,
        update_connection_status: Optional[Callable] = None,
    ):
        self._initialize_wallet(wallet_path, cache_path, peers_cache)
        self._initialize_vault(vault_path, cache_path, peers_cache, vault_password, create_vault)
        self._update_connection_status = update_connection_status

    def _initialize_wallet(
        self,
        wallet_path: str,
        cache_path: Optional[str] = None,
        peers_cache: Optional[str] = None,
    ) -> EvrmoreWallet:
        """Initialize the wallet, which doesn't require a password."""
        if self._wallet is not None:
            return self._wallet
        self._wallet = EvrmoreWallet.create(
            walletPath=wallet_path,
            cachePath=cache_path,
            identity=EvrmoreIdentity(wallet_path),
            persistent=False,  # We want lazy connection
            cachedPeersFile=peers_cache
        )
        logging.info('initialized wallet', color='green')
        return self._wallet

    def _initialize_vault(
        self,
        vault_path: str,
        cache_path: Optional[str] = None,
        peers_cache: Optional[str] = None,
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
            if not os.path.exists(vault_path) and not create:
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
                walletPath=vault_path,
                identity=EvrmoreIdentity(vault_path, password=password),
                cachePath=cache_path,
                persistent=False,  # We want lazy connection
                cachedPeersFile=peers_cache
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
            if not self.is_connected():
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
            
            if self.is_connected():
                # Update wallet and vault with current electrumx instance
                if self._wallet:
                    self._wallet.electrumx = self._electrumx
                if self._vault:
                    self._vault.electrumx = self._electrumx
                self._update_connection_status(
                    connTo=ConnectionTo.electrumx,
                    status=True)
                return True
            self._update_connection_status(
                connTo=ConnectionTo.electrumx,
                status=False)
            return False
        except Exception as e:
            logging.error(f"Failed to establish Electrumx connection: {e}")
            return False

    def is_connected(self) -> bool:
        """Check if there is a valid and active Electrumx connection."""
        return (
            self._electrumx is not None 
            and self._electrumx.connected() 
        )

    def open_vault(
        self,
        password: Union[str, None] = None,
        create: bool = False,
    ) -> Union[EvrmoreWallet, None]:
        if isinstance(self._vault, EvrmoreWallet):
            if self._vault.isDecrypted:
                return self._vault
            self._vault.open(password)
            return self._vault
        return self._initialize_vault(password=password, create=create)

    def close_vault(self) -> Union[EvrmoreWallet, None]:
        ''' close the vault, reopen it without decrypting it. '''
        if isinstance(self._vault, EvrmoreWallet):
            self._vault.close()
        return self._vault
