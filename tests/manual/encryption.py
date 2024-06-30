from satorilib.api.wallet import RavencoinWallet, EvrmoreWallet
from satorineuron import config
from satorilib import logging
from satorineuron.init import engine
# from satorilib.api.wallet import RavencoinWallet
from satorilib.api.disk import Cache  # Disk
Cache.setConfig(config)
vaultPath = config.walletPath('vault.yaml')
vaultPath
password = ''
r = RavencoinWallet(vaultPath, reserve=0.01, isTestnet=True, password=password)
r()
e = EvrmoreWallet(vaultPath, reserve=0.01, isTestnet=False, password=password)
e()
