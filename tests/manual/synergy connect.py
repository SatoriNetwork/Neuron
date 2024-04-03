from satorilib.pubsub import SatoriPubSubConn
import satorineuron
pubsub = satorineuron.engine.establishConnection(
    url='ws://satorinet.io:3500', pubkey='self.wallet.publicKey', key='')
synergy = satorineuron.engine.establishConnection(
    url='ws://192.168.0.10:3500', pubkey='self.wallet.publicKey', key='')


def router(response: str):
    print(response)


conn = SatoriPubSubConn(uid='self.wallet.publicKey', router=router,
                        payload='self.wallet.publicKey', url='ws://satorinet.io:3500')
