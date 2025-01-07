import asyncio
import websockets
import json
import os
import pathlib
import pandas as pd
from typing import Dict, Any, Optional
import sys
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
            return self.db.to_dataframe(table_uuid)
        except Exception as e:
            print(f"Error getting data for stream {table_uuid}: {e}")
            return None

    async def handle_request(self, websocket: websockets.WebSocketServerProtocol):
        try:
            async for message in websocket:
                print(f"Received request: {message}")
                try:
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
                        # replace with the new data
                    # if insert(uuid, replace=False)
                        # only merge, do not delete what is inside the existing database
                    # if delete(uuid):
                        # delete the whole table
                    # if delete( uuid, df):
                        # delete from database of what is inside the dataframe
                    
                    request: Dict[str, Any] = json.loads(message)
                    print(request)
                    if request.get('type') != 'stream_data':
                        response = {
                            "status": "error",
                            "message": f"Unknown request type: {request.get('type')}"
                        }
                    elif 'table_uuid' not in request:
                        response = {
                            "status": "error",
                            "message": "Missing table_uuid parameter"
                        }
                    else:
                        # Get data from SQLite
                        df = await self.get_stream_data(request['table_uuid'])
                        
                        if df is None:
                            response = {
                                "status": "error",
                                "message": f"No data found for stream {request['table_uuid']}"
                            }
                        else:
                            response = {
                                "status": "success",
                                "data": df.to_json(orient='split')
                            }

                    await websocket.send(json.dumps(response))
                    
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "status": "error",
                        "message": "Invalid JSON format"
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


