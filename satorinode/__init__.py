# from satorinode import spoof
# from satorinode import init
from satorinode import config
from satorilib import logging
from satorilib.api.wallet import Wallet
from satorilib.api.disk import Disk
Disk.setConfig(config)
logging.setup()
