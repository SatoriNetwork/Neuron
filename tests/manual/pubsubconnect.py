from satorineuron.synergy.engine import SynergyManager
from satorineuron.structs.pubsub import SignedStreamId
from satorineuron.structs.start import StartupDagStruct
from satorineuron.relay import RawStreamRelayEngine, ValidateRelayStream
from satorineuron.common.structs import ConnectionTo
from satorineuron import logging
from satorilib.asynchronous import AsyncThread
from satorilib.pubsub import SatoriPubSubConn
from satorilib.server.api import CheckinDetails
from satorilib.server import SatoriServerClient
from satorilib.api import disk
from satorilib.concepts.structs import StreamId, Stream
import satoriengine
import satorineuron
from queue import Queue
from reactivex.subject import BehaviorSubject
import threading
import json
import time
import os
from typing import Union
from satorilib.api.wallet import RavencoinWallet, EvrmoreWallet
from satorineuron import config
from satorilib import logging
from satorineuron.init import engine
from satorilib.api.disk import Cache  # Disk
Cache.setConfig(config)
vaultPath = config.walletPath('vault.yaml')
vaultPath
urlServer = 'https://satorinet.io'
referrer = None
# r = RavencoinWallet(vaultPath, reserve=0.01, isTestnet=True, password=password)
# r()
# rserver = SatoriServerClient(r, url=urlServer)
# rdetails = CheckinDetails(rserver.checkin(referrer=referrer))
# rdetails.key[0:5]
e = EvrmoreWallet(vaultPath, reserve=0.01, isTestnet=False, password=password)
e()
eserver = SatoriServerClient(e, url=urlServer)
edetails = CheckinDetails(eserver.checkin(referrer=referrer))
edetails.key[0:5]
signature = e.sign(edetails.key)
esub = SatoriPubSubConn(uid=e.publicKey, router=print, payload=f'{signature.decode()}|{edetails.key}',
                        url='ws://satorinet.io:3002', onConnect=lambda: print('connected-'), onDisconnect=lambda: print('-disconnected'))
