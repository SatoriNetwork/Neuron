import asyncio
import websockets
import json
import os
import pathlib
import sqlite3
import pandas as pd
from typing import Dict, Any, Optional, Union, Tuple, Set
import sys
from io import StringIO
from satorilib.logging import INFO, setup, debug, info, warning, error

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sqlite import SqliteDatabase
from sqlite import generateUUID


class Message:

    def __init__(
        self,
        message: str,
    ):
        pass

    @property
    def endpoint(self):
        return self.message.get('endpoint')

    # ...


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

        # self.connected_peers: Set = set()
        self.db = SqliteDatabase(db_path, db_name)
        self.db.importFromDataFolder()  # can be disabled if new rows are added to the Database

    async def start_server(self):
        """Start the WebSocket server"""
        self.server = await websockets.serve(
            self.handle_connection, self.host, self.port
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

    async def send_message_to_client(self, peer_addr: Tuple[str, int], message: str):
        """
        Send a message to a specific connected client

        Args:
            peer_addr: The address of the client to send the message to
            message: The message to send (will be converted to JSON)

        Returns:
            bool: True if message was sent successfully, False if client not found
        """
        if peer_addr in self.connectedPeers:
            websocket = self.connectedPeers[peer_addr].websocket
            try:
                await websocket.send(json.dumps({"status": "message", "data": message}))
                return True
            except websockets.exceptions.ConnectionClosed:
                # Clean up the disconnected client
                del self.connectedPeers[peer_addr]
                return False
        return False

    async def handle_connection(
        self, websocket: websockets.WebSocketServerProtocol, msg: str = "No Updates"
    ):
        """Handle incoming connections and messages"""
        peer_addr: Tuple[str, int] = websocket.remote_address
        print(f"New connection from {peer_addr}")
        self.connectedPeers[peer_addr] = ConnectedPeer(peer_addr, websocket)
        print("Connected peers:", self.connectedPeers)

        try:
            # Start a separate task for sending additional messages
            asyncio.create_task(self.subscriptionUpdates(peer_addr, msg))

            # Handle incoming messages
            async for message in websocket:
                debug(f"Received request: {message}", print=True)
                try:
                    response = await self.handleRequest(peer_addr, websocket, message)
                    await self.connectedPeers[peer_addr].websocket.send(
                        json.dumps(response)
                    )
                    await self.notifySubscribers(self, peer_addr, message)
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
            print(f"Connection closed with {peer_addr}")
        finally:
            # Remove disconnected peer
            for key, cp in list(self.connectedPeers.items()):
                if cp.websocket == websocket:
                    del self.connectedPeers[key]

    # async def send_additional_messages(self, peer_addr):
    #     """Send additional messages to the client"""
    #     try:
    #         while peer_addr in self.connected_peers:
    #             await asyncio.sleep(10)
    #             tst_msg = {
    #                 "status": "success",
    #                 "data": "Message from external Putty"
    #             }
    #             await self.connected_peers[peer_addr].websocket.send(json.dumps(tst_msg))
    #     except Exception as e:
    #         print(f"Error sending additional messages: {e}")

    async def notifySubscribers(self, peer_addr: Tuple[str, int], msg: str):
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
        # finish
        # for peer in self.connected_peers.values():
        #    if msg.params.table_uuid in peer.subscriptions:
        #        await self.connected_peers[peer].websocket.send(msg.message)

    async def subscriptionUpdates(self, peer_addr, msg):
        try:
            while peer_addr in self.connectedPeers:
                tst_msg = {"status": "success", "data": msg}
                await self.connectedPeers[peer_addr].websocket.send(
                    json.dumps(tst_msg)
                )
        except Exception as e:
            print(f"Error sending additional messages: {e}")

    async def sendPeer(
        self, peerAddr: Tuple[str, int], request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a request to a specific peer"""
        # json: {
        #     "endpoint": "get stream data",
        #     "magic": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7"
        #     "status": "success", # response
        #     "params": {
        #         "table_uuid": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7",
        #     }
        #     "data": <any>
        # }

        # response = {
        #     "endpoint": "get stream data",
        #     "magic": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7",
        #     "status": "success", # response
        #     "params": {
        #         "table_uuid": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7",
        #     },
        #     "data": <any>
        # }

        if peerAddr not in self.connectedPeers:
            peerHost, peerPort = peerAddr
            success = await self.connectToPeer(peerHost, peerPort)
            if not success:
                return {"status": "error", "message": "Failed to connect to peer"}

        websocket = self.connectedPeers[peerAddr].websocket
        try:
            await websocket.send(json.dumps(request))
            response = await websocket.recv()
            result = json.loads(response)

            if result['status'] == 'ping':
                print("Pinged Successfully")
                return

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
        for connectedPeer in self.connectedPeers.values():
            await connectedPeer.websocket.close()
        self.connectedPeers.clear()

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
    ) -> Optional[pd.DataFrame]:
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

    async def handleRequest(
        self,
        peer_addr: Tuple[str, int],
        websocket: websockets.WebSocketServerProtocol,
        message: str,
    ) -> Dict[str, Any]:
        """
        Process incoming requests
        json: {
            "endpoint": "get stream data",
            "magic": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7"
            "status": "success", # response
            "params": {
                "table_uuid": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7",
            }
            "data": <any>
        }
        """
        request: Dict[str, Any] = json.loads(message)
        debug(request, print=True)

        endpoint = request.get('endpoint')

        # todo
        if endpoint == 'subscribe':
            self.connectedPeers[peer_addr].add_subcription(
                request.get('params').get('table_uuid')
            )
            # self.subscriptions[request.get('params').get('table_uuid')] = self.subscriptions.get(request.get('params').get('table_uuid'), []) + [self.connected_peers[peer_addr]]
            return {"status": "subscribed", "message": "your good?"}

        if endpoint == 'initiate-connection':
            return {"status": "Success", "message": "Connection"}
        elif 'table_uuid' not in request and endpoint != 'ping':
            return {"status": "error", "message": "Missing table_uuid parameter"}
        table_uuid = request['table_uuid']

        if endpoint == 'stream_data':
            df = await self._getStreamData(table_uuid)
            if df is None:
                return {
                    "status": "error",
                    "message": f"No data found for stream {table_uuid}",
                }
            return {"status": "success", "data": df.to_json(orient='split')}

        elif endpoint == 'date_in_range':
            from_date = request.get('from_date')
            to_date = request.get('to_date')
            if not from_date or not to_date:
                return {
                    "status": "error",
                    "message": "Missing from_date or to_date parameter",
                }

            df = await self._getStreamDataByDateRange(table_uuid, from_date, to_date)
            if df is None:
                return {
                    "status": "error",
                    "message": f"No data found for stream {table_uuid} in specified date range",
                }

            if 'ts' in df.columns:
                df['ts'] = df['ts'].astype(str)
            return {"status": "success", "data": df.to_json(orient='split')}

        elif endpoint == 'last_record_before':
            try:
                data_json = request.get('data')
                if data_json is None:
                    return {"status": "error", "message": "No timestamp data provided"}
                timestamp_df = pd.read_json(StringIO(data_json), orient='split')
                timestamp = timestamp_df['ts'].iloc[0]
                df = await self._getLastRecordBeforeTimestamp(table_uuid, timestamp)
                if df is None:
                    return {
                        "status": "error",
                        "message": f"No records found before timestamp for stream {table_uuid}",
                    }

                if 'ts' in df.columns:
                    df['ts'] = df['ts'].astype(str)
                return {"status": "success", "data": df.to_json(orient='split')}
            except Exception as e:
                return {
                    "status": "error",
                    "message": f"Error processing timestamp request: {str(e)}",
                }

        elif endpoint == 'insert':
            try:
                data_json = request.get('data')
                if data_json is None:
                    return {
                        "status": "error",
                        "message": "No data provided for insert operation",
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
                    "message": (
                        f"Data {'replaced' if replace else 'merged'} successfully"
                        if success
                        else "Failed to insert data"
                    ),
                    "data": updated_df.to_json(orient='split') if success else None,
                }
            except Exception as e:
                return {"status": "error", "message": f"Error inserting data: {str(e)}"}

        elif endpoint == 'delete':
            try:
                data_json = request.get('data')
                if data_json is not None:
                    data = pd.read_json(StringIO(data_json), orient='split')
                    timestamps = data['ts'].tolist()
                    for ts in timestamps:
                        self.db.editTable('delete', table_uuid, timestamp=ts)
                    return {
                        "status": "success",
                        "message": "Delete operation completed",
                    }
                else:
                    self.db.deleteTable(table_uuid)
                    return {
                        "status": "success",
                        "message": f"Table {table_uuid} deleted",
                    }
            except Exception as e:
                return {"status": "error", "message": f"Error deleting data: {str(e)}"}
        else:
            return {
                "status": "error",
                "message": f"Unknown request type: {endpoint}",
            }

    # async def sendRequest(self, peer_addr: Tuple[str, int], table_uuid: str = None, request_type: str = "stream_data", data: pd.DataFrame = None, replace: bool = False):
    #     """ Make request into appropriate format """
    #     request = {
    #         "type": request_type,
    #         "table_uuid": table_uuid
    #     }

    #     if request_type == "ping":
    #         request = {
    #         "type": request_type,
    #         }

    #     # Handle different request types
    #     if request_type == "date_in_range" and data is not None:
    #         if 'from_ts' in data.columns and 'to_ts' in data.columns:
    #             request["from_date"] = data['from_ts'].iloc[0]
    #             request["to_date"] = data['to_ts'].iloc[0]
    #         else:
    #             raise ValueError("DataFrame must contain 'from_ts' and 'to_ts' columns for date range queries")

    #     elif request_type == "last_record_before":
    #         if data is None:
    #             raise ValueError("DataFrame with timestamp is required for last record before requests")
    #         if 'ts' not in data.columns:
    #             raise ValueError("DataFrame must contain 'ts' column for last record before requests")

    #     if data is not None:
    #         request["data"] = data.to_json(orient='split')

    #     if request_type == "insert":
    #         request["replace"] = replace

    #     return await self.sendPeer(peer_addr, request)

    # todo
    async def sendRequest(
        self,
        peer_addr: Tuple[str, int],
        table_uuid: str = None,
        endpoint: str = "stream_data",
        data: pd.DataFrame = None,
        replace: bool = False,
    ):
        import datetime
        """Make request into appropriate format"""
        # json: {
        #     "endpoint": "get stream data",
        #     "magic": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7"
        #     "status": "success", # response
        #     "params": {
        #         "table_uuid": "23dc3133-5b3a-5b27-803e-70a07cf3c4f7",
        #     }
        #     "data": <any>
        # }
        # request = {
        #     "type": request_type,
        #     "table_uuid": table_uuid
        # }

        # magic number can be request_type and current_time
        time = datetime.now() # check
        request = {
            "endpoint": "get stream data",
            "magic": generateUUID({'endpoint': endpoint, 'currentTime': time}),
            "params": {
                "table_uuid": table_uuid,
                "replace": replace
            },
            "data": data
        }

        if endpoint == "initiate-connection":
            request = {
                "endpoint": endpoint,
                "magic": generateUUID({'endpoint': endpoint, 'currentTime': time})
            }

        if endpoint == "data-in-range" and request.get("data") is not None:
            if 'from_ts' in request.get("data").columns and 'to_ts' in request.get("data").columns:
                request["params"]["from_date"] = request.get("data")['from_ts'].iloc[0]
                request["params"]["to_date"] = request.get("data")['to_ts'].iloc[0]
            else:
                raise ValueError(
                    "DataFrame must contain 'from_ts' and 'to_ts' columns for date range queries"
                )

        elif endpoint == "record-at-or-before":
            if request.get("data") is None:
                raise ValueError(
                    "DataFrame with timestamp is required for last record before requests"
                )
            if 'ts' not in request.get("data").columns:
                raise ValueError(
                    "DataFrame must contain 'ts' column for last record before requests"
                )

        if request.get("data") is not None:
            request["data"] = request.get("data").to_json(orient='split')

        if endpoint == "insert":
            request["params"]["replace"] = replace

        return await self.sendPeer(peer_addr, request)

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
