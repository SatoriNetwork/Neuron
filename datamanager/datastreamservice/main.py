import asyncio
import websockets
import json
import os
import pathlib
import sqlite3
import pandas as pd
from typing import Dict, Any, Optional, Union,Tuple
import sys
from io import StringIO
from satorilib.logging import INFO, setup, debug, info, warning, error
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase

# Todo : 

#self.subscribers: dict[str, str] = {} # {table_uuid: websocketconn/}
#self.publications =

# peer1, peer2 starts a server
# peer3 send a message to peer2
# peer2 receives message and sends to peer1
# peer1 recieves and prints it, then its a success

# management of multiple peers connections through our websocket server/client
# - can we identify which peer gave us a message
# - can we send a message to a specific peer
# perhaps use a package that wraps websockets to provide this functionality
# like socketify or others



class DataPeer:
    def __init__(self, host: str, port: int, db_path: str = "../../data", db_name: str = "data.db"):
        
        self.host = host
        self.port = port
        self.server = None
        self.connected_peers: Dict[Tuple[str, int], websockets.WebSocketServerProtocol] = {}
        self.db = SqliteDatabase(db_path, db_name)
        self.db.importFromDataFolder() # can be disabled if new rows are added to the Database

    async def start_server(self):
        """Start the WebSocket server"""
        self.server = await websockets.serve(self.handle_connection, self.host, self.port)
        print(f"Server started on ws://{self.host}:{self.port}")

    async def connect_to_peer(self, peer_host: str, peer_port: int):
        """Connect to another peer"""
        uri = f"ws://{peer_host}:{peer_port}"
        try:
            websocket = await websockets.connect(uri)
            self.connected_peers[(peer_host, peer_port)] = websocket
            print(f"Connected to peer at {uri}")
            return True
        except Exception as e:
            print(f"Failed to connect to peer at {uri}: {e}")
            return False

    async def handle_connection(self, websocket: websockets.WebSocketServerProtocol, path: str):
        """Handle incoming connections and messages"""
        peer_addr = websocket.remote_address
        print(f"New connection from {peer_addr}")
        self.connected_peers[peer_addr] = websocket
        print("Connected peers:", self.connected_peers)
        try:
            async for message in websocket:
                debug(f"Received request: {message}", print=True)
                try:
                    response = await self.handleRequest(websocket, message)
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
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed with {peer_addr}")
        finally:
            # Remove disconnected peer
            for key, ws in list(self.connected_peers.items()):
                if ws == websocket:
                    del self.connected_peers[key]

    async def send_request(self, peer_addr: Tuple[str, int], request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to a specific peer"""
        if peer_addr not in self.connected_peers:
            peer_host, peer_port = peer_addr
            success = await self.connect_to_peer(peer_host, peer_port)
            if not success:
                return {"status": "error", "message": "Failed to connect to peer"}

        websocket = self.connected_peers[peer_addr]
        try:
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            result = json.loads(response)

            # Handle database operations for successful responses
            if result["status"] == "success" and "data" in result:
                try:
                    df = pd.read_json(StringIO(result["data"]), orient='split')
                    table_uuid = request.get('table_uuid')
                    request_type = request.get('type', '')
                    
                    # Update local database
                    if request_type in ["last_record_before", "date_in_range"]:
                        self.db.deleteTable(table_uuid)
                        self.db.createTable(table_uuid)
                    self.db._dataframeToDatabase(table_uuid, df)
                    info(f"\nData saved to database: {self.db.dbname}")
                    debug(f"Table name: {table_uuid}")
                except Exception as e:
                    error(f"Database error: {e}")
            
            return result
        except Exception as e:
            print(f"Error sending request to peer: {e}")
            return {"status": "error", "message": str(e)}
        
    async def disconnect(self):
        """Disconnect from all peers and stop the server"""
        # Close all peer connections
        for websocket in self.connected_peers.values():
            await websocket.close()
        self.connected_peers.clear()
        
        # Stop the server if it's running
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        print("Disconnected from all peers and stopped server")


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

    async def handleRequest(self, websocket: websockets.WebSocketServerProtocol, message: str) -> Dict[str, Any]:
        """Process incoming requests"""
        request: Dict[str, Any] = json.loads(message)
        debug(request, print=True)
        
        if 'table_uuid' not in request:
            return {
                "status": "error",
                "message": "Missing table_uuid parameter"
            }
            
        table_uuid = request['table_uuid']
        request_type = request.get('type')
        
        if request_type == 'stream_data':
            df = await self._getStreamData(table_uuid)
            if df is None:
                return {
                    "status": "error",
                    "message": f"No data found for stream {table_uuid}"
                }
            return {
                "status": "success",
                "data": df.to_json(orient='split')
            }
            
        elif request_type == 'date_in_range':
            from_date = request.get('from_date')
            to_date = request.get('to_date')
            if not from_date or not to_date:
                return {
                    "status": "error",
                    "message": "Missing from_date or to_date parameter"
                }
            
            df = await self._getStreamDataByDateRange(table_uuid, from_date, to_date)
            if df is None:
                return {
                    "status": "error",
                    "message": f"No data found for stream {table_uuid} in specified date range"
                }
            
            if 'ts' in df.columns:
                df['ts'] = df['ts'].astype(str)
            return {
                "status": "success",
                "data": df.to_json(orient='split')
            }
            
        elif request_type == 'last_record_before':
            try:
                data_json = request.get('data')
                if data_json is None:
                    return {
                        "status": "error",
                        "message": "No timestamp data provided"
                    }
                timestamp_df = pd.read_json(StringIO(data_json), orient='split')
                timestamp = timestamp_df['ts'].iloc[0]
                df = await self._getLastRecordBeforeTimestamp(table_uuid, timestamp)
                if df is None:
                    return {
                        "status": "error",
                        "message": f"No records found before timestamp for stream {table_uuid}"
                    }
                
                if 'ts' in df.columns:
                    df['ts'] = df['ts'].astype(str)
                return {
                    "status": "success",
                    "data": df.to_json(orient='split')
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error processing timestamp request: {str(e)}"
                }
                
        elif request_type == 'insert':
            try:
                data_json = request.get('data')
                if data_json is None:
                    return {
                        "status": "error",
                        "message": "No data provided for insert operation"
                    }
                data = pd.read_json(StringIO(data_json), orient='split')
                replace = request.get('replace', False)
                if replace:
                    self.db.deleteTable(table_uuid)
                    self.db.createTable(table_uuid)
                success = self.db._dataframeToDatabase(table_uuid, data)   
                updated_df = await self._getStreamData(table_uuid)
                return {
                    "status": "success" if success else "error",
                    "message": f"Data {'replaced' if replace else 'merged'} successfully" if success else "Failed to insert data",
                    "data": updated_df.to_json(orient='split') if success else None
                }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error inserting data: {str(e)}"
                }
                
        elif request_type == 'delete':
            try:
                data_json = request.get('data')
                if data_json is not None:
                    data = pd.read_json(StringIO(data_json), orient='split')
                    timestamps = data['ts'].tolist()
                    for ts in timestamps:
                        self.db.editTable('delete', table_uuid, timestamp=ts)
                    return {
                        "status": "success",
                        "message": "Delete operation completed"
                    }
                else:
                    self.db.deleteTable(table_uuid)
                    return {
                        "status": "success",
                        "message": f"Table {table_uuid} deleted"
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error deleting data: {str(e)}"
                }
        else:
            return {
                "status": "error",
                "message": f"Unknown request type: {request_type}"
            }

    async def request_stream_data(self, peer_addr: Tuple[str, int], table_uuid: str, request_type: str = "stream_data", data: pd.DataFrame = None, replace: bool = False):
        """Request stream data from a specific peer"""
        request = {
            "type": request_type,
            "table_uuid": table_uuid
        }

        # Handle different request types
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

        return await self.send_request(peer_addr, request)

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
    # Create two peers
    peer1 = DataPeer("localhost", 8001)
    await peer1.start_server()
    await asyncio.Future()  # run forever

    # peer1 = DataPeer("ws://localhost:8765")
    # async with websockets.serve(peer1.handleRequest, "localhost", 8765):
    #     print("WebSocket server started on ws://localhost:8765")
    #     await asyncio.Future()  # run forever

    # Wait for server to start
    # await asyncio.sleep(1)

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


