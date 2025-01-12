from main import DataPeer
import asyncio
import pandas as pd

async def main():
    peer2 = DataPeer("localhost", 8002, db_path="./client_data", db_name="client.db")
    await peer2.start_server()
    # await asyncio.Future()
    table_uuid = "23dc3133-5b3a-5b27-803e-70a07cf3c4f7"
    # Example 1: Get stream data
    # print("\n=== Example 1: Get Stream Data ===")
    
    ## if reqest available then request else keep pinging every 10 seconds


    # while True:
        # await peer2.pingForUpdates()
    # response = await peer2.sendRequest(
    #     ("localhost", 8080),
    #     table_uuid=table_uuid,
    #     endpoint="stream_data"
    # )
    # print(response)
    # await asyncio.sleep(10)
    # print("Stream data response:", response)

    # # Example 2: Insert new data (merge)
    # print("\n=== Example 2: Insert New Data ===")
    new_data = pd.DataFrame({
        'ts': ['2024-12-07 04:30:01.270985'],
        'value': [124.45],
        'hash': ['abc123def456']
    })
    response = await peer2.sendRequest(
        ("localhost", 8080),
        table_uuid,
        endpoint="insert",
        data=new_data,
        replace=False
    )
    print(response)

    # # Example 3: Delete specific records
    # print("\n=== Example 3: Delete Specific Records ===")
    # records_to_delete = pd.DataFrame({
    #     'ts': ['2025-01-04 15:27:35']
    # })
    # response = await peer2.sendRequest(
    #     ("localhost", 8080),
    #     table_uuid,
    #     endpoint="delete",
    #     data=records_to_delete
    # )
    # print("Delete specific records response:", response)

    # # Example 4: Delete entire table
    # print("\n=== Example 4: Delete Entire Table ===")
    # response = await peer2.sendRequest(
    #     ("localhost", 8080),
    #     table_uuid,
    #     endpoint="delete"
    # )
    # print("Delete table response:", response)

    # # Example 5: Get data for a specific date range
    # print("\n=== Example 5: Get Data by Date Range ===")
    # records_to_fetch = pd.DataFrame({
    #     'from_ts': ["2024-11-07 03:50:00.834062"],
    #     'to_ts': ["2024-11-20 16:00:00.912330"]
    # })
    # response = await peer2.sendRequest(
    #     ("localhost", 8080),
    #     table_uuid,
    #     endpoint="data-in-range",
    #     data=records_to_fetch
    # )
    # print("Date range response:", response)

    # # Example 6: Get last record before timestamp
    # print("\n=== Example 6: Get Last Record Before Timestamp ===")
    # timestamp_df = pd.DataFrame({
    #     'ts': ['2024-11-20 15:00:00.912330']
    # })
    # response = await peer2.sendRequest(
    #     ("localhost", 8080),
    #     table_uuid,
    #     endpoint="record-at-or-before",
    #     data=timestamp_df
    # )
    # print("Last record before timestamp response:", response)

if __name__ == "__main__":
    asyncio.run(main())