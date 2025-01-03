import asyncio
import websockets
import json
import pathlib
import pandas as pd
from io import StringIO
from typing import Dict, Any

async def request_stream_data(stream_id:str):
    """Request data for a specific stream ID"""
    async with websockets.connect("ws://localhost:8765") as websocket:
        # Request stream data
        print(f"Requesting data for stream {stream_id}...")
        await websocket.send(json.dumps({
            "type": "stream_data",
            "stream_id": stream_id
        }))
        
        # Get response
        response: str = await websocket.recv()
        result: Dict[str, Any] = json.loads(response)
        
        if result["status"] == "success":
            # print("\nStream info:", json.dumps(result["stream_info"], indent=2))
            save_dir: pathlib.Path = pathlib.Path("rec_data")
            save_dir.mkdir(exist_ok=True)

            # Deserialize the JSON data back to DataFrame
            # Use StringIO to handle the JSON string
            df: pd.DataFrame = pd.read_json(StringIO(result["data"]), orient='split')

            # Save to CSV
            output_path: pathlib.Path = save_dir / f"{stream_id}.csv"
            df.to_csv(output_path, index=False)
            print(f"\nData saved to {output_path}")
            print(f"Total records: {len(df)}")
        else:
            print(f"Error: {result['message']}")

if __name__ == "__main__":
    # Replace with the actual stream ID you want to request
    stream_id: str = 'zeAv-URFSz9f_hw57bTJ2c_FeoE-'
    asyncio.run(request_stream_data(stream_id))
