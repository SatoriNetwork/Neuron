import asyncio
import websockets
import json
import pathlib
import pandas as pd
from io import StringIO
from typing import Dict, Any

async def request_stream_data(table_uuid: str):
    """Request data for a specific stream ID"""
    try:
        async with websockets.connect("ws://localhost:8765") as websocket:
            print(f"Requesting data for stream {table_uuid}...")
            await websocket.send(json.dumps({
                "type": "stream_data",
                "table_uuid": table_uuid 
            }))
            
            response: str = await websocket.recv()
            result: Dict[str, Any] = json.loads(response)
            
            if result["status"] == "success":
                save_dir: pathlib.Path = pathlib.Path("rec")
                save_dir.mkdir(exist_ok=True)

                df: pd.DataFrame = pd.read_json(StringIO(result["data"]), orient='split')
                output_path: pathlib.Path = save_dir / f"{table_uuid}.csv"
                df.to_csv(output_path, index=False)
                print(f"\nData saved to {output_path}")
                print(f"Total records: {len(df)}")
            else:
                print(f"Error: {result['message']}")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"Connection closed unexpectedly: {e}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Replace with the actual stream ID you want to request
    table_uuid : str = '23dc3133-5b3a-5b27-803e-70a07cf3c4f7'
    asyncio.run(request_stream_data(table_uuid ))
