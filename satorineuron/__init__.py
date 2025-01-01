from satorineuron import config
from satorilib import logging
from satorilib.disk import Cache  # Disk
Cache.setConfig(config)
logging.setup(level={
    'debug': logging.DEBUG,
    'warning': logging.WARNING,
    'info': logging.INFO,
    'error': logging.ERROR,
    'critical': logging.CRITICAL,
}[config.get().get('logging level', 'warning').lower()])

VERSION = '0.3.6'
MOTTO = 'Let your workings remain a mystery, just show people the results.'
