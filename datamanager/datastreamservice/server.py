import asyncio
import websockets
import json
import os
import pathlib
import pandas as pd
from typing import Dict, Any, Optional

class DataServer:
    def __init__(self):
        self.base_path: str = "../data"

    async def get_stream_info(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """Get stream info for a specific stream ID when requested"""
        try:
            stream_path: pathlib.Path = pathlib.Path(self.base_path) / stream_id
            if not stream_path.exists():
                return None
            
            readme_path: pathlib.Path = stream_path / "readme.md"
            if readme_path.exists():
                with open(readme_path, 'r') as f:
                    stream_info: Dict[str, Any]  = json.load(f)
                    return {
                        "stream_info": stream_info
                    }
            return None
            
        except Exception as e:
            print(f"Error getting stream info: {e}")
            return None

    async def load_stream_data(self, stream_id: str) -> Optional[pd.DataFrame]:
        """Load data for a specific stream from its CSV file"""
        try:
            # Get the path to the data folder
            folder_path: pathlib.Path = pathlib.Path(self.base_path) / stream_id
            
            # Look for CSV files in the folder
            csv_files: list[pathlib.Path] = list(folder_path.glob("*.csv"))
            if not csv_files:
                return None

            # Load the first CSV file found
            data: pd.DataFrame = pd.read_csv(csv_files[0])
            return data

        except Exception as e:
            print(f"Error loading data for stream {stream_id}: {e}")
            return None

    async def handle_request(self, websocket: websockets.WebSocketServerProtocol):
        try:
            async for message in websocket:
                print(f"Received request: {message}")
                try:
                    request: Dict[str, Any] = json.loads(message)
                    
                    if request.get('type') == 'stream_data':
                        if 'stream_id' not in request:
                            response: Dict[str, str] = {
                                "status": "error",
                                "message": "Missing stream_id parameter"
                            }
                        else:
                            # 1. First check if stream exists and get its info
                            stream_info: Optional[Dict[str, Any]]  = await self.get_stream_info(request['stream_id'])
                            
                            if stream_info is None:
                                response = {
                                    "status": "error",
                                    "message": f"Stream {request['stream_id']} not found"
                                }
                            else:
                                # 2. If stream exists, load its data
                                data: Optional[pd.DataFrame] = await self.load_stream_data(request['stream_id'])
                                
                                if data is None:
                                    response = {
                                        "status": "error",
                                        "message": "Failed to load stream data"
                                    }
                                else:
                                    response = {
                                        "status": "success",
                                        # "stream_info": stream_info,
                                        "data": data.to_json(orient='split')
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


# data-flow :

# server runs first and starts listening
# client then gives request to the server with a streamID
# server picks up the request
# server checks if the streamID exists in the data folder
# if True, fetch data at that moment to serve the data to the client
# client recieves the data
