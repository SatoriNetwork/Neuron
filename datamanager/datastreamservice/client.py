import asyncio
import websockets
import json
import pathlib
import pandas as pd
from io import StringIO
import sqlite3
from typing import Dict, Any, Optional


# todo: inside rec folder, make .db and insert it that way
class StreamDatabase:
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

            if data is not None:
                request["data"] = data.to_json(orient='split')  
           
            if request_type == "insert":
                request["replace"] = replace

            await websocket.send(json.dumps(request))
            response: str = await websocket.recv()
            result: Dict[str, Any] = json.loads(response)
            
            # if result["status"] == "success":
            # save_dir: pathlib.Path = pathlib.Path("rec")
            # save_dir.mkdir(exist_ok=True)
            # df: pd.DataFrame = pd.read_json(StringIO(result["data"]), orient='split')
            # output_path: pathlib.Path = save_dir / f"{table_uuid}.csv"
            # df.to_csv(output_path, index=False, header=False)
            # print(f"\nData saved to {output_path}")
            # print(f"Total records: {len(df)}")

            if result["status"] == "success":
                
                if request_type == "delete":
                    # Delete the table from the database
                    db = StreamDatabase()
                    try:
                        if db.delete_table(table_uuid):
                            print(f"\nTable {table_uuid} successfully deleted from database")
                        else:
                            print(f"\nTable {table_uuid} not found in database")
                    except sqlite3.Error as e:
                        print(f"Database error during deletion: {e}")

                elif "data"  in result:
                     # Read the JSON data into a DataFrame
                    df: pd.DataFrame = pd.read_json(StringIO(result["data"]), orient='split')

                    # Save to database
                    db = StreamDatabase()
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

if __name__ == "__main__":
    # Replace with the actual stream ID you want to request
    table_uuid: str = '23dc3133-5b3a-5b27-803e-70a07cf3c4f7'
    # asyncio.run(request_stream_data(table_uuid))
    async def main():
        pass
        # Example 1: Get stream data
        # await request_stream_data(table_uuid)
        
        # # Example 2: Insert new data (merge)
        # new_data = pd.DataFrame({
        #     'ts': ['2025-01-04 15:27:35'],
        #     'value': [124.45],
        #     'hash': ['abc123def456']
        # })
        # await request_stream_data(table_uuid, "insert", new_data, replace=False)
        
        # Example 3: Delete specific records
        # records_to_delete = pd.DataFrame({
        #     'ts': ['2025-01-04 15:27:35']
        # })
        # await request_stream_data(table_uuid, "delete", records_to_delete)
        
        # # Example 4: Delete entire table
        # await request_stream_data(table_uuid, "delete")

    asyncio.run(main())