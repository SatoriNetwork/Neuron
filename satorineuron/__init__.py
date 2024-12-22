# from satorineuron import spoof
from satorineuron import config
from satorilib import logging
from satorineuron.init import engine
# from satorilib.wallet import RavencoinWallet
from satorilib.disk import Cache  # Disk
Cache.setConfig(config)
logging.setup(level={
    'debug': logging.DEBUG,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}[config.get().get('logging level', 'warning').lower()])

VERSION = '0.3.4'
MOTTO = 'Let your workings remain a mystery, just show people the results.'
