# from Lib.satorilib.datamanager import DataServer
import asyncio
from satorilib.datamanager import DataServer

async def runServerForever():
    server = DataServer('0.0.0.0', 24602, "../../data")
    await server.startServer()
    await asyncio.Future()  

asyncio.run(runServerForever())