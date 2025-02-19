import asyncio
from satorineuron import config
from satorilib.datamanager import DataServer
from satorilib.wallet.evrmore.identity import EvrmoreIdentity 

async def runServerForever():
    server = DataServer('0.0.0.0', 24602, EvrmoreIdentity(config.walletPath('wallet.yaml')))
    await server.startServer()
    await asyncio.Future()  

asyncio.run(runServerForever())