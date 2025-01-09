from main import DataPeer
import asyncio

async def main():
    peer = DataPeer("localhost", 8001, db_path="./client_data", db_name="client.db")
    await peer.run(connect_to=("localhost", 8000))
    # peer.connectToPeer("localhost", 8000)
    # response = await peer.sendToPeer(
    #     ("localhost", 8000),
    #     {
    #         "type": "stream_data",
    #         "table_uuid": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7"
    #     }
    # )
    # print(response)

if __name__ == "__main__":
    asyncio.run(main())