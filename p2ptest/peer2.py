# from Lib.satorilib.data import DataClient
from satorilib.data import DataClient
import asyncio

async def main():
    peer2 = DataClient(db_path="./client", db_name="client.db")
    table_uuid = "23dc3133-5b3a-5b27-803e-70a07cf3c4f7"
    resp = await peer2.sendRequest(("localhost", 24602), table_uuid=table_uuid, sub=True)
    print(resp.id)

if __name__ == "__main__":
    asyncio.run(main())