import asyncio
import websockets
import json
import pathlib
import pandas as pd
from io import StringIO
import sqlite3
from typing import Dict, Any, Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase
from satorilib.logging import INFO, setup, debug, info, warning, error



class DataClient:
    def __init__(self, db_path: str = "./client_data", db_name: str = "client.db"):
        if not os.path.exists(db_path):
            os.makedirs(db_path)
        self.clientdb = SqliteDatabase(data_dir=db_path, dbname=db_name)

    async def request_stream_data(self, table_uuid: str, request_type: str = "stream_data", data: pd.DataFrame = None, replace: bool = False):
        try:
            async with websockets.connect("ws://localhost:8765") as websocket:
                print(f"Requesting data for stream {table_uuid}...")
                request = {
                    "type": request_type,
                    "table_uuid": table_uuid
                }
                if request_type == "date_in_range" and data is not None:
                    if 'from_ts' in data.columns and 'to_ts' in data.columns:
                        request["from_date"] = data['from_ts'].iloc[0]
                        request["to_date"] = data['to_ts'].iloc[0]
                    else:
                        raise ValueError("DataFrame must contain 'from_ts' and 'to_ts' columns for date range queries")
                elif request_type == "last_record_before":
                    if data is None:
                        raise ValueError("DataFrame with timestamp is required for last record before requests")
                    if 'ts' not in data.columns:
                        raise ValueError("DataFrame must contain 'ts' column for last record before requests")

                if data is not None:
                    request["data"] = data.to_json(orient='split')  
            
                if request_type == "insert":
                    request["replace"] = replace

                await websocket.send(json.dumps(request))
                response: str = await websocket.recv()
                result: Dict[str, Any] = json.loads(response)

                if result["status"] == "success":
                    if "data"  in result:
                        df: pd.DataFrame = pd.read_json(StringIO(result["data"]), orient='split')
                        # debug(df, print=True)
                        try:
                            if request_type == "last_record_before" or request_type == "date_in_range":
                                self.clientdb.deleteTable(table_uuid)
                                self.clientdb.createTable(table_uuid)
                            self.clientdb._dataframeToDatabase(table_uuid, df)
                            info(f"\nData saved to database: {self.clientdb.dbname}")
                            debug(f"Table name: {table_uuid}")
                        except sqlite3.Error as e:
                            error(f"Database error: {e}")
                    else:
                        debug("Server response:", result['message'], print=True)
                else:
                    error(f"Error: {result['message']}")
                    
        except websockets.exceptions.ConnectionClosedError as e:
            error(f"Connection closed unexpectedly: {e}")
        except Exception as e:
            error(f"Error: {e}")

    @staticmethod
    def _get_sqlite_type(dtype):
        """Convert pandas dtype to SQLite type"""
        if "int" in str(dtype):
            return "INTEGER"
        elif "float" in str(dtype):
            return "REAL"
        elif "datetime" in str(dtype):
            return "TIMESTAMP"
        else:
            return "TEXT"

if __name__ == "__main__":
    # Replace with the actual stream ID you want to request
    table_uuid: str = '23dc3133-5b3a-5b27-803e-70a07cf3c4f7'
    # asyncio.run(request_stream_data(table_uuid))
    async def main():
        client = DataClient()
        # pass
        # Example 1: Get stream data
        # await client.request_stream_data(table_uuid)
        
        # # Example 2: Insert new data (merge)
        # new_data = pd.DataFrame({
        #     'ts': ['2025-01-04 15:27:35'],
        #     'value': [124.45],
        #     'hash': ['abc123def456']
        # })
        # await client.request_stream_data(table_uuid, "insert", new_data, replace=False)
        # # Create the new row
       
        # Example 3: Delete specific records
        # records_to_delete = pd.DataFrame({
        #     'ts': ['2025-01-04 15:27:35']
        # })
        # db = SqliteDatabase(data_dir = "./rec",dbname="stream_data.db")
        # df = db.to_dataframe(table_uuid)
        # await client.request_stream_data(table_uuid, "delete", records_to_delete)
        
        # # Example 4: Delete entire table
        # await client.request_stream_data(table_uuid, "delete")

        # Example 5: Get data for a specific date range
        # records_to_fetch = pd.DataFrame({
        #     'from_ts': ["2024-11-07 03:50:00.834062"],
        #     'to_ts': ["2024-11-20 16:00:00.912330"]
        # })
        # await client.request_stream_data(
        #     table_uuid,
        #     request_type="date_in_range",
        #     data=records_to_fetch
        # )

        
        # Example 6: Get last record before timestamp
        # timestamp_df = pd.DataFrame({
        #     'ts': ['2024-11-20 15:00:00.912330']  # Same timestamp as before
        # })
        # await client.request_stream_data(
        #     table_uuid,
        #     request_type="last_record_before",
        #     data=timestamp_df
        # )

    asyncio.run(main())