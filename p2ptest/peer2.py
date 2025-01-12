# from Lib.satorilib.data import DataClient
from satorilib.data import DataClient
import asyncio
from satorilib.data.datamanager.helper import Message

async def main():
    peer2 = DataClient(db_path="./client", db_name="client.db")
    table_uuid = "23dc3133-5b3a-5b27-803e-70a07cf3c4f7"
    # resp = await peer2.sendRequest(("localhost", 24602), method="stream_data", table_uuid=table_uuid, sub=False)
    # resp: Message = await peer2.sendRequest(("localhost", 24602))
    resp: Message = await peer2.subscribe(("localhost", 24602),table_uuid)
    print(resp.to_dict())

if __name__ == "__main__":
    asyncio.run(main())