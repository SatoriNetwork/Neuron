import asyncio
import websockets
import json
import os
import pandas as pd
from typing import Dict, Any, Optional, Union, Tuple, Set
from dataclasses import dataclass, asdict
import sys
from io import StringIO
from satorilib.logging import INFO, setup, debug, info, warning, error

# todo : fix this
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase
from sqlite import generateUUID


class Message:
    def __init__(self, message: dict):
        """
        Initialize Message object with a dictionary containing message data
        """
        self.message = message

    def to_dict(self) -> dict:
        """
        Convert the Message instance back to a dictionary
        """
        return {
            'endpoint': self.endpoint,
            'magic': self.magic,
            'status': self.status,
            'params': {
                'table_uuid': self.table_uuid,
                'replace': self.replace,
                'from_ts': self.fromDate,
                'to_ts': self.toDate,
            },
            'data': self.data,
        }

    @property
    def endpoint(self) -> str:
        """Get the endpoint"""
        return self.message.get('endpoint')

    @property
    def magic(self) -> str:
        """Get the magic UUID"""
        return self.message.get('magic')

    @property
    def status(self) -> str:
        """Get the status"""
        return self.message.get('status')

    @property
    def params(self) -> dict:
        """Get the params"""
        return self.message.get('params', {})

    @property
    def table_uuid(self) -> str:
        """Get the table_uuid from params"""
        return self.params.get('table_uuid')

    @property
    def replace(self) -> str:
        """Get the table_uuid from params"""
        return self.params.get('replace')

    @property
    def fromDate(self) -> str:
        """Get the table_uuid from params"""
        return self.params.get('from_ts')

    @property
    def toDate(self) -> str:
        """Get the table_uuid from params"""
        return self.params.get('to_ts')

    @property
    def data(self) -> any:
        """Get the data"""
        return self.message.get('data')

    def is_success(self) -> bool:
        """Get the status"""
        return self.status == 'success'


class ConnectedPeer:

    def __init__(
        self,
        hostPort: Tuple[str, int],
        websocket: websockets.WebSocketServerProtocol,
        subscriptions: Union[list, None] = None,
        publications: Union[list, None] = None,
    ):
        self.hostPort = hostPort
        self.websocket = websocket
        self.subscriptions = subscriptions or []
        self.publications = publications or []

    @property
    def host(self):
        return self.hostPort[0]

    @property
    def port(self):
        return self.hostPort[1]

    def add_subcription(self, table_uuid: str):
        self.subscriptions.append(table_uuid)


class DataPeer:
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
        self.connectedPeers: Dict[Tuple[str, int], ConnectedPeer] = {}
        # an optimization
        # self.subscriptions: Dict[int, ConnectedPeer] = {}
        self.db = SqliteDatabase(db_path, db_name)
        self.db.importFromDataFolder()  # can be disabled if new rows are added to the Database and new rows recieved are inside the database

    async def start_server(self):
        """Start the WebSocket server"""
        self.server = await websockets.serve(
            self.handleConnection, self.host, self.port
        )
        print(f"Server started on ws://{self.host}:{self.port}")

    async def connectToPeer(self, peerHost: str, peerPort: int):
        """Connect to another peer"""
        uri = f"ws://{peerHost}:{peerPort}"
        try:
            websocket = await websockets.connect(uri)
            self.connectedPeers[(peerHost, peerPort)] = ConnectedPeer(
                (peerHost, peerPort), websocket
            )
            debug(f"Connected to peer at {uri}", print=True)
            return True
        except Exception as e:
            error(f"Failed to connect to peer at {uri}: {e}")
            return False

    async def handleConnection(self, websocket: websockets.WebSocketServerProtocol):
        """Handle incoming connections and messages"""
        peerAddr: Tuple[str, int] = websocket.remote_address
        debug(f"New connection from {peerAddr}")
        self.connectedPeers[peerAddr] = ConnectedPeer(peerAddr, websocket)
        debug("Connected peers:", self.connectedPeers)
        try:
            # asyncio.create_task(self.subscriptionUpdates(peer_addr, msg))
            async for message in websocket:
                debug(f"Received request: {message}", print=True)
                try:
                    response = await self.handleRequest(peerAddr, websocket, message)
                    await self.connectedPeers[peerAddr].websocket.send(
                        json.dumps(response)
                    )
                    await self.notifySubscribers(self, peerAddr, message)
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
            for key, cp in list(self.connectedPeers.items()):
                if cp.websocket == websocket:
                    del self.connectedPeers[key]

    async def notifySubscribers(self, peerAddr: Tuple[str, int], msg: Message):
        '''
        is this message something anyone has subscribed to?
        if yes, await self.connected_peers[subscribig_peer].websocket.send(message)

        xc -> ys -> zc
        REST model
        client - can push to server any time
        server - can only respond to clinets, can handle lots of clients

        peer - can push to peers at any time and receive from peer at any timeserver and server can push to client


        our context:
        client - no  endpoints


        '''
        for peerAddr in self.connectedPeers.values():
           if msg.table_uuid in self.connectedPeers[peerAddr].subscriptions:
               await self.connectedPeers[peerAddr].websocket.send(json.dumps(msg.to_dict()))

    async def sendPeer(
        self, peerAddr: Tuple[str, int], request: Message
    ) -> Dict:
        """Send a request to a specific peer"""
        if peerAddr not in self.connectedPeers:
            peerHost, peerPort = peerAddr
            success = await self.connectToPeer(peerHost, peerPort)
            if not success:
                return {"status": "error", "magic": request.magic, "message": "Failed to connect to peer"}

        ws = self.connectedPeers[peerAddr].websocket
        try:
            await ws.send(json.dumps(request.to_dict()))
            response = Message(json.loads(await ws.recv()))
            if response.status == "success" and response.data is not None:
                try:
                    df = pd.read_json(StringIO(response.data), orient='split')
                    if response.endpoint in ["record-at-or-before", "data-in-range"]:
                        self.db.deleteTable(response.table_uuid)
                        self.db.createTable(response.table_uuid)
                    self.db._dataframeToDatabase(response.table_uuid, df)
                    info(f"\nData saved to database: {self.db.dbname}")
                    debug(f"Table name: {response.table_uuid}")
                except Exception as e:
                    error(f"Database error: {e}")
            return response.to_dict()
        except Exception as e:
            error(f"Error sending request to peer: {e}")
            return {"status": "error", "message": str(e)}

    async def disconnectAllPeers(self):
        """Disconnect from all peers and stop the server"""
        for connectedPeer in self.connectedPeers.values():
            await connectedPeer.websocket.close()
        self.connectedPeers.clear()
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
        if request.endpoint == 'subscribe' and request.table_uuid is not None:
            self.connectedPeers[peerAddr].add_subcription(request.table_uuid)
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
    peer1 = DataPeer("0.0.0.0", 8080)
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
