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
    def __init__(self, db_path: pathlib.Path = None):
        if db_path is None:
            db_dir = pathlib.Path("rec")
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "stream_data.db"
        self.db_path = db_path
        self.db = SqliteDatabase()
        self.db.importFromDataFolder()

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
        
    def delete_table(self, table_uuid: str) -> bool:
        """Delete a table from the SQLite database"""
        conn = sqlite3.connect(self.db_path)
        try:
            # Check if table exists
            table_exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", 
                (table_uuid,)
            ).fetchone() is not None
            
            if table_exists:
                conn.execute(f"DROP TABLE IF EXISTS '{table_uuid}'")
                conn.commit()
                return True
            return False
            
        except sqlite3.Error as e:
            raise e
        finally:
            conn.close()

    def save_dataframe(self, table_uuid: str, df: pd.DataFrame) -> int:
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

    async def get_stream_data(self, table_uuid: str) -> Optional[Dict[str, Any]]:
        """Get data for a specific stream directly from SQLite database"""
        try:
            df = self.db.to_dataframe(table_uuid)
            if df is None or df.empty:
                return None
            return df
        except Exception as e:
            print(f"Error getting data for stream {table_uuid}: {e}")
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
                        df = await self.get_stream_data(table_uuid)
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
                            
                            success = self.db.dataframeToDatabase(table_uuid, data)

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
                        
                        try:
                            data_json = request.get('data')
                            if data_json is not None:
                                
                                data = pd.read_json(StringIO(data_json), orient='split')
                                
                                timestamps = data['ts'].tolist()
                                
                                for ts in timestamps:
                                    self.db.editTable('delete', table_uuid, timestamp=ts)
                            
                                updated_df = await self.get_stream_data(table_uuid)
                                
                                response = {
                                    "status": "success",
                                    "message": f"Delete operation completed",
                                    "data": updated_df.to_json(orient='split') if updated_df is not None else None
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
            print("Client connection closed")
        except Exception as e:
            print(f"Error handling client: {e}")

async def request_stream_data(table_uuid: str, request_type: str = "stream_data", data: pd.DataFrame = None, replace: bool = False):
    try:
        async with websockets.connect("ws://localhost:8765") as websocket:
            print(f"Requesting data for stream {table_uuid}...")
            request = {
                "type": request_type,
                "table_uuid": table_uuid
            }

            if data is not None:
                request["data"] = data.to_json(orient='split')  
           
            if request_type == "insert":
                request["replace"] = replace

            await websocket.send(json.dumps(request))
            response: str = await websocket.recv()
            result: Dict[str, Any] = json.loads(response)
            

            if result["status"] == "success":
                ds = DataServer()
                
                if "data" in result:
                    df: pd.DataFrame = pd.read_json(StringIO(result["data"]), orient='split')
                    print("\nReceived data:")
                    try:
                        record_count = ds.save_dataframe(table_uuid, df)
                        print(f"\nData saved to database: {ds.db_path}")
                        print(f"Table name: {table_uuid}")
                        print(f"Total records: {record_count}")
                        
                    except sqlite3.Error as e:
                        print(f"Database error: {e}")

                elif request_type == "delete":
                    try:
                        ds.db.deleteTable(table_uuid)
                        if ds.delete_table(table_uuid):
                            print(f"\nTable {table_uuid} successfully deleted from database")
                        else:
                            print(f"\nTable {table_uuid} not found in database")
                    except sqlite3.Error as e:
                        print(f"Database error during deletion: {e}")

                else:
                       print("Server response:", result['message'])
            else:
                print(f"Error: {result['message']}")
                
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
    except Exception as e:
        print(f"Error: {e}")

async def run_server():
    server = DataServer()
    async with websockets.serve(server.handle_request, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever

async def run_example(example_number: int):
    table_uuid = '23dc3133-5b3a-5b27-803e-70a07cf3c4f7'
    
    if example_number == 1:
        # Get stream data
        print("\nGetting stream data...")
        await request_stream_data(table_uuid)
    
    elif example_number == 2:
        # Insert new data (merge)
        print("\nInserting new data...")
        new_data = pd.DataFrame({
            'ts': ['2025-01-04 15:27:35'],
            'value': [124.45],
            'hash': ['abc123def456']
        })
        await request_stream_data(table_uuid, "insert", new_data, replace=False)
    
    elif example_number == 3:
        # Delete specific records
        print("\nDeleting specific records...")
        records_to_delete = pd.DataFrame({
            'ts': ['2025-01-04 15:27:35']
        })
        await request_stream_data(table_uuid, "delete", records_to_delete)
    
    elif example_number == 4:
        # Delete entire table
        print("\nDeleting entire table...")
        await request_stream_data(table_uuid, "delete")

async def handle_user_input():
    while True:
        print("\nAvailable examples:")
        print("1. Get stream data")
        print("2. Insert new data")
        print("3. Delete specific records")
        print("4. Delete entire table")
        print("q. Quit")
        
        choice = input("\nEnter example number to run (or 'q' to quit): ")
        
        if choice.lower() == 'q':
            sys.exit(0)
        
        try:
            example_num = int(choice)
            if 1 <= example_num <= 4:
                await run_example(example_num)
            else:
                print("Invalid example number")
        except ValueError:
            print("Please enter a valid number or 'q' to quit")

async def main():
    # Run server and user input handler concurrently
    await asyncio.gather(
        run_server(),
        handle_user_input()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")