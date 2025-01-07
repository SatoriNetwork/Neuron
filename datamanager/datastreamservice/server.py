import asyncio
import websockets
import json
import os
import pathlib
import pandas as pd
from typing import Dict, Any, Optional
import sys
from io import StringIO
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase

# three endpoints : table_uuid, sender_info and save to db ( if observation or whole dataframe ) 

class DataServer:
    def __init__(self):
        self.db = SqliteDatabase()
        self.db.importFromDataFolder()

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
                    # endpoints:
                    # get stream df from database (DONE)
                    # get stream df from database from date to date (inclusive)
                    # get last record before timestamp
                    # delete table
                    # delete stream df from database (just note)
                    # save by merging stream df to database
                    # subscribe to all new observations ( later )
                    # unsubscribe to all new observations ( later )

                    #endpoint : 
                    # if insert(uuid, replace=True):
                        # erase the data in table_uuid
                        # replace with only the new data
                    # if insert(uuid, replace=False)
                        # only merge, do not delete what is inside the existing database
                    # if delete(uuid):
                        # delete the whole table
                    # if delete( uuid, df):
                        # delete from database of what is inside the dataframe
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
                            success = self.db.dataframeToDatabase(table_uuid, data)

                            # Get updated data after insert
                            updated_df = await self.get_stream_data(table_uuid)
                            
                            response = {
                                "status": "success" if success else "error",
                                "message": f"Data {'replaced' if replace else 'merged'} successfully" if success else "Failed to insert data",
                                "data": updated_df.to_json(orient='split') if success else None
                            }
                            
                            # response = {
                            #     "status": "success" if success else "error",
                            #     "message": f"Data {'replaced' if replace else 'merged'} successfully" if success else "Failed to insert data"
                            # }
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
                            # else:
                            #     self.db.deleteTable(table_uuid)

                                # Get updated data after delete
                                updated_df = await self.get_stream_data(table_uuid)
                                
                                response = {
                                    "status": "success",
                                    "message": f"Delete operation completed",
                                    "data": updated_df.to_json(orient='split') if updated_df is not None else None
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


async def main():
    server = DataServer()
    async with websockets.serve(server.handle_request, "localhost", 8765):
        print("WebSocket server started on ws://localhost:8765")
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(main())


