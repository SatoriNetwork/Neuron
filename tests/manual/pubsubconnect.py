from satorilib.pubsub import SatoriPubSubConn
from satorilib.server.api import CheckinDetails
from satorilib.server import SatoriServerClient
from satorilib.wallet import EvrmoreWallet
from satorineuron import config
from satorilib.disk import Cache  # Disk
Cache.setConfig(config)
vaultPath = config.walletPath('vault.yaml')
vaultPath
urlServer = 'https://central.satorinet.io'
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
esub = SatoriPubSubConn(uid=e.pubkey, router=print, payload=f'{signature.decode()}|{edetails.key}',
                        url='ws://pubsub.satorinet.io:3002', onConnect=lambda: print('connected-'), onDisconnect=lambda: print('-disconnected'))
