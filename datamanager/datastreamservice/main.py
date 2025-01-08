import asyncio
import websockets
import json
import os
import pathlib
import sqlite3
import pandas as pd
from typing import Dict, Any, Optional
import sys
from io import StringIO
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase

class DataServer:
    def __init__(self):
        self.db = SqliteDatabase()
        self.db.importFromDataFolder()

    async def get_stream_data(self, table_uuid: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific stream directly from SQLite database"""
        try:
            df = self.db._toDataframe(table_uuid)
            if df is None or df.empty:
                return None
            return df
        except Exception as e:
            print(f"Error getting data for stream {table_uuid}: {e}")
            return None

    async def get_stream_data_by_date_range(self, table_uuid: str, from_date: str, to_date: str) -> Optional[pd.DataFrame]:
        """Get stream data within a specific date range (inclusive)"""
        try:
            df = self.db._toDataframe(table_uuid)
            
            if df is None or df.empty:
                return None
            
            # Convert string dates to datetime
            from_ts = pd.to_datetime(from_date)
            to_ts = pd.to_datetime(to_date)
            
            # Ensure ts column is datetime
            df['ts'] = pd.to_datetime(df['ts'])
            # Filter data within range (inclusive)
            filtered_df = df[(df['ts'] >= from_ts) & (df['ts'] <= to_ts)]
            
            return filtered_df if not filtered_df.empty else None
        except Exception as e:
            print(f"Error getting data for stream {table_uuid} in date range: {e}")
            return None

    async def get_last_record_before_timestamp(self, table_uuid: str, timestamp: str) -> Optional[pd.DataFrame]:
        """Get the last record before the specified timestamp"""
        try:
            df = self.db._toDataframe(table_uuid)
            if df is None or df.empty:
                return None
            
            # Convert string timestamp to datetime
            ts = pd.to_datetime(timestamp)
            
            # Ensure ts column is datetime
            df['ts'] = pd.to_datetime(df['ts'])

            # First check for exact match
            exact_match = df[df['ts'] == ts]
            if not exact_match.empty:
                return exact_match

            
            # Get records before the timestamp

            before_ts = df[df['ts'] < ts]
            
            if before_ts.empty:
                return None
                
            # Get the last record
            last_record = before_ts.iloc[[-1]]
            
            return last_record
        except Exception as e:
            print(f"Error getting last record before timestamp for stream {table_uuid}: {e}")
            return None

    async def handle_request(self, websocket: websockets.WebSocketServerProtocol):
        try:
            async for message in websocket:
                print(f"Received request: {message}")
                try:
                    request: Dict[str, Any] = json.loads(message)
                    print(request)

                    if 'table_uuid' not in request:
                        response = {
                            "status": "error",
                            "message": "Missing table_uuid parameter"
                        }
                        await websocket.send(json.dumps(response))
                        continue

                    table_uuid = request['table_uuid']

                    if request.get('type') == 'stream_data':
                        # Get stream data functionality
                        df = await self.get_stream_data(table_uuid)
                        if df is None:
                            response = {
                                "status": "error",
                                "message": f"No data found for stream {table_uuid}"
                            }
                        else:
                            response = {
                                "status": "success",
                                "data": df.to_json(orient='split')  # Convert DataFrame to JSON string
                            }

                    elif request.get('type') == 'date_range_data':
                        # Handle date range request
                        from_date = request.get('from_date')
                        to_date = request.get('to_date')
                        
                        if not from_date or not to_date:
                            response = {
                                "status": "error",
                                "message": "Missing from_date or to_date parameter"
                            }
                        else:
                            df = await self.get_stream_data_by_date_range(table_uuid, from_date, to_date)
                        
                            if df is None:
                                response = {
                                    "status": "error",
                                    "message": f"No data found for stream {table_uuid} in specified date range"
                                }
                            else:
                                if 'ts' in df.columns:
                                    df['ts'] = df['ts'].astype(str)
                                response = {
                                    "status": "success",
                                    "data": df.to_json(orient='split')
                                }

                    elif request.get('type') == 'last_record_before':
                        try:
                            data_json = request.get('data')
                            if data_json is None:
                                raise ValueError("No timestamp data provided")
                            
                            # Convert JSON string to DataFrame
                            timestamp_df = pd.read_json(StringIO(data_json), orient='split')
                            timestamp = timestamp_df['ts'].iloc[0]
                            
                            df = await self.get_last_record_before_timestamp(table_uuid, timestamp)
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
                        # Handle insert operation
                        try:
                            data_json = request.get('data')
                            if data_json is None:
                                raise ValueError("No data provided for insert operation")
                            
                            # Convert JSON string to DataFrame
                            data = pd.read_json(StringIO(data_json), orient='split')
                            replace = request.get('replace', False)
                            
                            if replace:
                                # First delete the existing table
                                self.db.deleteTable(table_uuid)
                                # Create new table
                                self.db.createTable(table_uuid)
                            
                            # Insert/merge the data
                            success = self.db._dataframeToDatabase(table_uuid, data)

                            # Get updated data after insert
                            updated_df = await self.get_stream_data(table_uuid)
                            
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
                        # Handle delete operation
                        try:
                            data_json = request.get('data')
                            if data_json is not None:
                                # Convert JSON string to DataFrame
                                data = pd.read_json(StringIO(data_json), orient='split')
                                # Delete specific records
                                timestamps = data['ts'].tolist()
                                # Delete records one by one
                                for ts in timestamps:
                                    self.db.editTable('delete', table_uuid, timestamp=ts)
                                response = {
                                    "status": "success",
                                    "message": f"Delete operation completed",
                                    
                                }
                            else:
                                # Delete entire table
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
            print("Client connection closed")
        except Exception as e:
            print(f"Error handling client: {e}")


class DataClient:
    def __init__(self, db_path: pathlib.Path = None):
        if db_path is None:
            db_dir = pathlib.Path("rec")
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "stream_data.db"
        self.db_path = db_path
    
    def save_dataframe(self, table_uuid: str, df: pd.DataFrame) -> None:
        """Save DataFrame to SQLite database"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Get column names and types for creating table
            columns = df.dtypes.items()
            create_table_sql = f'CREATE TABLE IF NOT EXISTS "{table_uuid}" ('
            create_table_sql += ', '.join([
                f"'{col}' {self._get_sqlite_type(dtype)}" 
                for col, dtype in columns
            ])
            create_table_sql += ')'
            
            # Create table and insert data
            conn.execute(f"DROP TABLE IF EXISTS '{table_uuid}'")
            conn.execute(create_table_sql)
            
            # Convert DataFrame to list of tuples for insertion
            data = [tuple(x) for x in df.values]
            placeholders = ",".join(["?" for _ in df.columns])
            
            conn.executemany(f"INSERT INTO '{table_uuid}' VALUES ({placeholders})", data)
            conn.commit()
            
            # Verify the data
            count = conn.execute(f"SELECT COUNT(*) FROM '{table_uuid}'").fetchone()[0]
            return count
            
        except sqlite3.Error as e:
            raise e
        finally:
            conn.close()
    
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

async def request_stream_data(table_uuid: str, request_type: str = "stream_data", data: pd.DataFrame = None, replace: bool = False):
    try:
        async with websockets.connect("ws://localhost:8765") as websocket:
            print(f"Requesting data for stream {table_uuid}...")
            request = {
                "type": request_type,
                "table_uuid": table_uuid
            }

            # Add date range parameters if provided
            if request_type == "date_range_data" and data is not None:
                # Extract from_date and to_date from the DataFrame
                if 'from_ts' in data.columns and 'to_ts' in data.columns:
                    request["from_date"] = data['from_ts'].iloc[0]
                    request["to_date"] = data['to_ts'].iloc[0]
                else:
                    raise ValueError("DataFrame must contain 'from_ts' and 'to_ts' columns for date range queries")
            
            
            # Add timestamp parameter if provided
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
                     # Read the JSON data into a DataFrame
                    df: pd.DataFrame = pd.read_json(StringIO(result["data"]), orient='split')

                    # Save to database
                    db = DataClient()
                    try:
                        record_count = db.save_dataframe(table_uuid, df)
                        print(f"\nData saved to database: {db.db_path}")
                        print(f"Table name: {table_uuid}")
                        print(f"Total records: {record_count}")
                        
                    except sqlite3.Error as e:
                        print(f"Database error: {e}")
                else:
                       print("Server response:", result['message'])
            else:
                print(f"Error: {result['message']}")
                
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    # Start server
    server = DataServer()
    async with websockets.serve(server.handle_request, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever
    
    # Wait for server to start
    await asyncio.sleep(1)
    
    # Create client
    client = DataClient()
    table_uuid: str = '23dc3133-5b3a-5b27-803e-70a07cf3c4f7'
    # Example 1: Get stream data
    # await request_stream_data(table_uuid)
    
    # # Example 2: Insert new data (merge)
    # new_data = pd.DataFrame({
    #     'ts': ['2025-01-04 15:27:35'],
    #     'value': [124.45],
    #     'hash': ['abc123def456']
    # })
    # await request_stream_data(table_uuid, "insert", new_data, replace=False)
    # # Create the new row
    
    # Example 3: Delete specific records
    # records_to_delete = pd.DataFrame({
    #     'ts': ['2025-01-04 15:27:35']
    # })
    # db = SqliteDatabase(data_dir = "./rec",dbname="stream_data.db")
    # df = db.to_dataframe(table_uuid)
    # await request_stream_data(table_uuid, "delete", df)
    
    # # Example 4: Delete entire table
    # await request_stream_data(table_uuid, "delete")

    # Example 5: Get data for a specific date range
    # records_to_fetch = pd.DataFrame({
    #     'from_ts': ["2024-11-07 03:50:00.834062"],
    #     'to_ts': ["2024-11-20 15:00:00.912330"]
    # })
    # await request_stream_data(
    #     table_uuid,
    #     request_type="date_range_data",
    #     data=records_to_fetch
    # )

    
    # Example 6: Get last record before timestamp
    # timestamp_df = pd.DataFrame({
    #     'ts': ['2024-11-20 15:00:00.912330']  # Same timestamp as before
    # })
    # await request_stream_data(
    #     table_uuid,
    #     request_type="last_record_before",
    #     data=timestamp_df
    # )

if __name__ == "__main__":
    asyncio.run(main())