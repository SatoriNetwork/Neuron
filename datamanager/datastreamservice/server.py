'''

refactor and test
---
create a server - rendezvous server
--- 
integrate with neuron-dataClient
integrate with engine-dataClient
---
subsume all logic currently used in engine for managing data on disk
---
make sure it's all working together
---
p2p - get histories (just request history of data)
p2p - replace pubsub servers (start using subscriptions)
---
relay if necessary?
---



'''

import asyncio
import websockets
import json
import os
import queue
import pandas as pd
from typing import Dict, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, asdict
import sys
from io import StringIO
from satorilib.logging import INFO, setup, debug, info, warning, error

# todo : fix this
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase, generateUUID

class DataServer:
    def __init__(
        self,
        host: str,
        port: int,
        db_path: str = "../../data",
        db_name: str = "data.db",
    ):

        self.host = host
        self.port = port
        self.server = None
        self.connectedClients: Dict[Tuple[str, int], ConnectedPeer] = {}
        # an optimization
        # self.subscriptions: Dict[int, ConnectedPeer] = {}
        self.subscriptions: dict[Subscription, queue.Queue] = {}
        self.responses: dict[str, dict] = {}
        self.db = SqliteDatabase(db_path, db_name)
        self.db.importFromDataFolder()  # can be disabled if new rows are added to the Database and new rows recieved are inside the database

    async def start_server(self):
        """Start the WebSocket server"""
        self.server = await websockets.serve(
            self.handleConnection, self.host, self.port
        )
        print(f"Server started on ws://{self.host}:{self.port}")

    async def handleConnection(self, websocket: websockets.WebSocketServerProtocol):
        """Handle incoming connections and messages"""
        peerAddr: Tuple[str, int] = websocket.remote_address
        debug(f"New connection from {peerAddr}")
        self.connectedClients[peerAddr] = self.connectedClients.get(peerAddr, ConnectedPeer(peerAddr, websocket))
        debug("Connected peers:", self.connectedClients)
        try:
            async for message in websocket:
                debug(f"Received request: {message}", print=True)
                try:
                    response = await self.handleRequest(peerAddr, websocket, message)
                    await self.connectedClients[peerAddr].websocket.send(
                        json.dumps(response)
                    )
                    # await websocket.send(json.dumps(response))
                    debug("Response sent", print=True)
                except json.JSONDecodeError:
                    await websocket.send(
                        json.dumps(
                            {"status": "error", "message": "Invalid JSON format"}
                        )
                    )
                except Exception as e:
                    await websocket.send(
                        json.dumps(
                            {
                                "status": "error",
                                "message": f"Error processing request: {str(e)}",
                            }
                        )
                    )
        except websockets.exceptions.ConnectionClosed:
            print(f"Connection closed with {peerAddr}")
        finally:
            # Remove disconnected peer
            for key, cp in list(self.connectedClients.items()):
                if cp.websocket == websocket:
                    del self.connectedClients[key]

    async def notifySubscribers(self, msg: Message):
        '''
        is this message something anyone has subscribed to?
        if yes, await self.connected_peers[subscribig_peer].websocket.send(message)
        '''
        for peerAddr in self.connectedClients.values():
           if msg.table_uuid in self.connectedClients[peerAddr].subscriptions:
               await self.connectedClients[peerAddr].websocket.send(msg.to_json())

    async def disconnectAllPeers(self):
        """Disconnect from all peers and stop the server"""
        for connectedPeer in self.connectedClients.values():
            await connectedPeer.websocket.close()
        self.connectedClients.clear()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        info("Disconnected from all peers and stopped server")

    
    async def handleRequest(
        self,
        peerAddr: Tuple[str, int],
        websocket: websockets.WebSocketServerProtocol,
        message: str,
    ) -> Dict:
        # can make a function which can reduce the redundancy
        request: Message = Message(json.loads(message))

        # TODO: need and endpoint to notify subscribers
        # neuron-dataClient, raw data -> dataClient --ws-> datamanager.dataServer
        #self.notifySubscribers(request) 

        if request.endpoint == 'subscribe' and request.table_uuid is not None:
            self.connectedClients[peerAddr].add_subcription(request.table_uuid)
            return {
                "status": "success",
                "magic": request.magic,
                "message": f"Subscribed to {request.table_uuid}",
            }
        elif request.endpoint == 'initiate-connection':
            return {
                "status": "Success",
                "magic": request.magic,
                "message": "Connection established",
            }

        if request.table_uuid is None:
            return {
                "status": "error",
                "magic": request.magic,
                "message": "Missing table_uuid parameter",
            }

        if request.endpoint == 'stream_data':
            df = await self._getStreamData(request.table_uuid)
            if df is None:
                return {
                    "status": "error",
                    "magic": request.magic,
                    "message": f"No data found for stream {request.table_uuid}",
                }
            return {
                "status": "success",
                "magic": request.magic,
                "data": df.to_json(orient='split'),
            }

        elif request.endpoint == 'data-in-range':
            if not request.fromDate or not request.toDate:
                return {
                    "status": "error",
                    "magic": request.magic,
                    "message": "Missing from_date or to_date parameter",
                }

            df = await self._getStreamDataByDateRange(
                request.table_uuid, request.fromDate, request.toDate
            )
            if df is None:
                return {
                    "status": "error",
                    "magic": request.magic,
                    "message": f"No data found for stream {request.table_uuid} in specified date range",
                }

            if 'ts' in df.columns:
                df['ts'] = df['ts'].astype(str)
            return {
                "status": "success",
                "magic": request.magic,
                "data": df.to_json(orient='split'),
            }

        elif request.endpoint == 'record-at-or-before':
            try:
                if request.data is None:
                    return {"status": "error", "message": "No timestamp data provided"}
                timestamp_df = pd.read_json(StringIO(request.data), orient='split')
                timestamp = timestamp_df['ts'].iloc[0]
                df = await self._getLastRecordBeforeTimestamp(
                    request.table_uuid, timestamp
                )
                if df is None:
                    return {
                        "status": "error",
                        "magic": request.magic,
                        "message": f"No records found before timestamp for stream {request.table_uuid}",
                    }

                if 'ts' in df.columns:
                    df['ts'] = df['ts'].astype(str)
                return {
                    "status": "success",
                    "magic": request.magic,
                    "data": df.to_json(orient='split'),
                }
            except Exception as e:
                return {
                    "status": "error",
                    "magic": request.magic,
                    "message": f"Error processing timestamp request: {str(e)}",
                }

        elif request.endpoint == 'insert':
            try:
                if request.data is None:
                    return {
                        "status": "error",
                        "magic": request.magic,
                        "message": "No data provided for insert operation",
                    }
                data = pd.read_json(StringIO(request.data), orient='split')
                if request.replace:
                    self.db.deleteTable(request.table_uuid)
                    self.db.createTable(request.table_uuid)
                success = self.db._dataframeToDatabase(request.table_uuid, data)
                updated_df = await self._getStreamData(request.table_uuid)
                return {
                    "status": "success" if success else "error",
                    "magic": request.magic,
                    "message": (
                        f"Data {'replaced' if request.replace else 'merged'} successfully"
                        if success
                        else "Failed to insert data"
                    ),
                    "data": updated_df.to_json(orient='split') if success else None,
                }
            except Exception as e:
                return {
                    "status": "error",
                    "magic": request.magic,
                    "message": f"Error inserting data: {str(e)}",
                }

        elif request.endpoint == 'delete':
            try:
                if request.data is not None:
                    data = pd.read_json(StringIO(request.data), orient='split')
                    timestamps = data['ts'].tolist()
                    for ts in timestamps:
                        self.db.editTable('delete', request.table_uuid, timestamp=ts)
                    return {
                        "status": "success",
                        "magic": request.magic,
                        "message": "Delete operation completed",
                    }
                else:
                    self.db.deleteTable(request.table_uuid)
                    return {
                        "status": "success",
                        "magic": request.magic,
                        "message": f"Table {request.table_uuid} deleted",
                    }
            except Exception as e:
                return {
                    "status": "error",
                    "magic": request.magic,
                    "message": f"Error deleting data: {str(e)}",
                }
        else:
            return {
                "status": "error",
                "magic": request.magic,
                "message": f"Unknown request type: {request.endpoint}",
            }

    async def sendRequest(
        self,
        peer_addr: Tuple[str, int],
        table_uuid: str = None,
        endpoint: str = "stream_data",
        data: pd.DataFrame = None,
        replace: bool = False,
        fromDate: str = None,
        toDate: str = None,
    ) -> Dict:
        
        from datetime import datetime
        magicStr: str = str(
            generateUUID({'endpoint': endpoint, 'currentTime': datetime.now()})
        )

        if endpoint == "initiate-connection":
            request = Message({"endpoint": endpoint, "magic": magicStr})
        elif endpoint == "data-in-range" and data is not None:
            if 'from_ts' in data.columns and 'to_ts' in data.columns:
                fromDate = data['from_ts'].iloc[0]
                toDate = data['to_ts'].iloc[0]
            else:
                raise ValueError(
                    "DataFrame must contain 'from_ts' and 'to_ts' columns for date range queries"
                )
        elif endpoint == "record-at-or-before":
            if data is None:
                raise ValueError(
                    "DataFrame with timestamp is required for last record before requests"
                )
            if 'ts' not in data.columns:
                raise ValueError(
                    "DataFrame must contain 'ts' column for last record before requests"
                )

        if data is not None:
            data = data.to_json(orient='split')

        request = Message(
            {
                "endpoint": endpoint,
                "magic": magicStr,
                "params": {
                    "table_uuid": table_uuid,
                    "replace": replace,
                    "from_ts": fromDate,
                    "to_ts": toDate,
                },
                "data": data,
            }
        )
        return await self.sendPeer(peer_addr, request)
    

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

    async def _getStreamDataByDateRange(
        self, table_uuid: str, from_date: str, to_date: str
    ) -> pd.DataFrame:
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

    async def _getLastRecordBeforeTimestamp(
        self, table_uuid: str, timestamp: str
    ) -> pd.DataFrame:
        """Get the last record before the specified timestamp (inclusive)"""
        try:
            df = self.db._databasetoDataframe(table_uuid)
            if df is None or df.empty:
                return pd.DataFrame()
            ts = pd.to_datetime(timestamp)
            df['ts'] = pd.to_datetime(df['ts'])
            if not df.loc[df['ts'] == ts].empty:  # First check for exact match
                return df.loc[df['ts'] == ts]
            before_ts = df.loc[
                df['ts'] < ts
            ]  # check for timestamp before specified timestamp
            return before_ts.iloc[[-1]] if not before_ts.empty else pd.DataFrame()
        except Exception as e:
            error(
                f"Error getting last record before timestamp for stream {table_uuid}: {e}"
            )

    # todo : is there need of this?
    # @staticmethod
    # def _get_sqlite_type(dtype):
    #     """Convert pandas dtype to SQLite type"""
    #     if "int" in str(dtype):
    #         return "INTEGER"
    #     elif "float" in str(dtype):
    #         return "REAL"
    #     elif "datetime" in str(dtype):
    #         return "TIMESTAMP"
    #     else:
    #         return "TEXT"


async def main():
    # Start server
    # Create two peers
    peer1 = DataServer("0.0.0.0", 8080)
    await peer1.start_server()
    await asyncio.Future()  # run forever

    # peer1 = DataServer("ws://localhost:8765")
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
