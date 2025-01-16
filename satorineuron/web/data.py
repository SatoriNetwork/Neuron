# from Lib.satorilib.data.datamanager import DataServer
import asyncio
from satorilib.data.datamanager import DataServer

async def runServerForever():
    server = DataServer('0.0.0.0', 24602, "../../data")
    await server.startServer()
    await asyncio.Future()  

asyncio.run(runServerForever())