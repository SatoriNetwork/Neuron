# from Lib.satorilib.data import DataServer
import asyncio
from satorilib.data import DataServer, DataClient

async def main():
    peer1 = DataServer("localhost", 24602)
    await peer1.start_server()
    await asyncio.Future()  

if __name__ == "__main__":
    asyncio.run(main())