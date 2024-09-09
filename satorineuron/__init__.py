# from satorineuron import spoof
from satorineuron import config
from satorilib import logging
from satorineuron.init import engine
# from satorilib.api.wallet import RavencoinWallet
from satorilib.api.disk import Cache  # Disk
Cache.setConfig(config)
logging.setup(level={
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}[config.get().get('logging level', 'warning').lower()])

VERSION = '0.2.03'
MOTTO = 'Let your workings remain a mystery, just show people the results.'
