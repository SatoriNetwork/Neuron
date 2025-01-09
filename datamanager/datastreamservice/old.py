import asyncio
import websockets
import json
import os
import pathlib
import sqlite3
import pandas as pd
from typing import Dict, Any, Optional, Union
import sys
from io import StringIO
from satorilib.logging import INFO, setup, debug, info, warning, error
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase

class DataServer:
    def __init__(self):
        #self.subscribers: dict[str, str] = {} # {table_uuid: websocketconn/}
        #self.publications =

        # management of multiple peers connections through our websocket server/client
        # - can we identify which peer gave us a message
        # - can we send a message to a specific peer
        # perhaps use a package that wraps websockets to provide this functionality
        # like socketify or others
        self.db = SqliteDatabase()
        self.db.importFromDataFolder() # can be disabled if new rows are added to the Database

    async def _getStreamData(self, table_uuid: str) -> pd.DataFrame:
        """Get data for a specific stream directly from SQLite database"""
        try:
            df = self.db._databasetoDataframe(table_uuid)
            if df is None or df.empty:
                debug("No data available to send")
                return pd.DataFrame()
            return df
        except Exception as e:
            error(f"Error getting data for stream {table_uuid}: {e}")

    async def _getStreamDataByDateRange(self, table_uuid: str, from_date: str, to_date: str) -> pd.DataFrame:
        """Get stream data within a specific date range (inclusive)"""
        try:
            df = self.db._databasetoDataframe(table_uuid)
            if df is None or df.empty:
                debug("No data available to send")
                return pd.DataFrame()
            from_ts = pd.to_datetime(from_date)
            to_ts = pd.to_datetime(to_date)
            df['ts'] = pd.to_datetime(df['ts'])
            filtered_df = df[(df['ts'] >= from_ts) & (df['ts'] <= to_ts)]
            return filtered_df if not filtered_df.empty else pd.DataFrame()
        except Exception as e:
            error(f"Error getting data for stream {table_uuid} in date range: {e}")

    async def _getLastRecordBeforeTimestamp(self, table_uuid: str, timestamp: str) -> Optional[pd.DataFrame]:
        """Get the last record before the specified timestamp (inclusive)"""
        try:
            df = self.db._databasetoDataframe(table_uuid)
            if df is None or df.empty:
                return pd.DataFrame()
            ts = pd.to_datetime(timestamp)
            df['ts'] = pd.to_datetime(df['ts'])
            if not df.loc[df['ts'] == ts].empty: # First check for exact match
                return df.loc[df['ts'] == ts]
            before_ts = df.loc[df['ts'] < ts] # check for timestamp before specified timestamp
            return before_ts.iloc[[-1]] if not before_ts.empty else pd.DataFrame()
        except Exception as e:
            error(f"Error getting last record before timestamp for stream {table_uuid}: {e}")

    async def handleRequest(self, websocket: websockets.WebSocketServerProtocol):
        try:
            async for message in websocket:
                debug(f"Received request: {message}", print=True)
                try:
                    request: Dict[str, Any] = json.loads(message)
                    debug(request, print=True)
                    if 'table_uuid' not in request:
                        response = {
                            "status": "error",
                            "message": "Missing table_uuid parameter"
                        }
                        await websocket.send(json.dumps(response))
                        continue
                    table_uuid = request['table_uuid']
                    if request.get('type') == 'stream_data':
                        df = await self._getStreamData(table_uuid)
                        if df is None:
                            response = {
                                "status": "error",
                                "message": f"No data found for stream {table_uuid}"
                            }
                        else:
                            response = {
                                "status": "success",
                                "data": df.to_json(orient='split')
                            }
                    elif request.get('type') == 'date_in_range':
                        from_date = request.get('from_date')
                        to_date = request.get('to_date')
                        if not from_date or not to_date:
                            response = {
                                "status": "error",
                                "message": "Missing from_date or to_date parameter"
                            }
                        else:
                            df = await self._getStreamDataByDateRange(table_uuid, from_date, to_date)
                            if df is None:
                                response = {
                                    "status": "error",
                                    "message": f"No data found for stream {table_uuid} in specified date range"
                                }
                            else:
                                if 'ts' in df.columns:
                                    df['ts'] = df['ts'].astype(str) # todo : needed?
                                response = {
                                    "status": "success",
                                    "data": df.to_json(orient='split')
                                }
                    elif request.get('type') == 'last_record_before':
                        try:
                            data_json = request.get('data')
                            if data_json is None:
                                raise ValueError("No timestamp data provided")
                            timestamp_df = pd.read_json(StringIO(data_json), orient='split')
                            timestamp = timestamp_df['ts'].iloc[0]
                            df = await self._getLastRecordBeforeTimestamp(table_uuid, timestamp)
                            if df is None:
                                response = {
                                    "status": "error",
                                    "message": f"No records found before timestamp for stream {table_uuid}"
                                }
                            else:
                                if 'ts' in df.columns:
                                    df['ts'] = df['ts'].astype(str)
                                response = {
                                    "status": "success",
                                    "data": df.to_json(orient='split')
                                }
                        except Exception as e:
                            response = {
                                "status": "error",
                                "message": f"Error processing timestamp request: {str(e)}"
                            }

                    elif request.get('type') == 'insert':
                        try:
                            data_json = request.get('data')
                            if data_json is None:
                                raise ValueError("No data provided for insert operation")
                            data = pd.read_json(StringIO(data_json), orient='split')
                            replace = request.get('replace', False)
                            if replace:
                                self.db.deleteTable(table_uuid)
                                self.db.createTable(table_uuid)
                            success = self.db._dataframeToDatabase(table_uuid, data)   
                            updated_df = await self._getStreamData(table_uuid)
                            response = {
                                "status": "success" if success else "error",
                                "message": f"Data {'replaced' if replace else 'merged'} successfully" if success else "Failed to insert data",
                                "data": updated_df.to_json(orient='split') if success else None
                            }
                        except Exception as e:
                            response = {
                                "status": "error",
                                "message": f"Error inserting data: {str(e)}"
                            }
                    elif request.get('type') == 'delete':
                        try:
                            data_json = request.get('data')
                            if data_json is not None: # Delete from what is inside the dataframe
                                data = pd.read_json(StringIO(data_json), orient='split')
                                timestamps = data['ts'].tolist()
                                for ts in timestamps:
                                    self.db.editTable('delete', table_uuid, timestamp=ts)
                                response = {
                                    "status": "success",
                                    "message": f"Delete operation completed",
                                }
                            else:
                                self.db.deleteTable(table_uuid)
                                response = {
                                    "status": "success",
                                    "message": f"Table {table_uuid} deleted"
                                }
                        except Exception as e:
                            response = {
                                "status": "error",
                                "message": f"Error deleting data: {str(e)}"
                            }
                    else:
                        response = {
                            "status": "error",
                            "message": f"Unknown request type: {request.get('type')}"
                        }
                    await websocket.send(json.dumps(response))
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": "Invalid JSON format"
                    }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": f"Error processing request: {str(e)}"
                    }))
        except websockets.exceptions.ConnectionClosedError:
            error("Client connection closed")
        except Exception as e:
            error(f"Error handling client: {e}")


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

async def main():
    # Start server
    server = DataServer()
    async with websockets.serve(server.handleRequest, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever

    # Wait for server to start
    await asyncio.sleep(1)

    # Create client
    # client = DataClient()
    # table_uuid: str = '23dc3133-5b3a-5b27-803e-70a07cf3c4f7'
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

if __name__ == "__main__":
    asyncio.run(main())
