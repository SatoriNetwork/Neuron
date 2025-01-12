import asyncio
import websockets
import json
import os
import time
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

class Subscription:
    def __init__(
        self,
        method: str,
        params: Union[list, None] = None,
        callback: Union[callable, None] = None
    ):
        self.method = method
        self.params = params or []
        self.shortLivedCallback = callback

    def __hash__(self):
        return hash((self.method, tuple(self.params)))

    def __eq__(self, other):
        if isinstance(other, Subscription):
            return self.method == other.method and self.params == other.params
        return False

    def __call__(self, *args, **kwargs):
        '''
        This is the callback that is called when a subscription is triggered.
        it takes time away from listening to the socket, so it should be short-
        lived, like saving the value to a variable and returning, or logging,
        or triggering a thread to do something such as listen to the queue and
        do some long-running process with the data from the queue.
        example:
            def foo(*args, **kwargs):
                print(f'foo. args:{args}, kwargs:{kwargs}')
        '''
        if self.shortLivedCallback is None:
            return None
        return self.shortLivedCallback(*args, **kwargs)
    
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
            'method': self.method,
            'id': self.id,
            'sub': self.sub,
            'status': self.status,
            'params': {
                'table_uuid': self.table_uuid,
                'replace': self.replace,
                'from_ts': self.fromDate,
                'to_ts': self.toDate,
            },
            'data': self.data,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @property
    def method(self) -> str:
        """Get the method"""
        return self.message.get('method')

    @property
    def id(self) -> str:
        """Get the id UUID"""
        return self.message.get('id')

    @property
    def status(self) -> str:
        """Get the status"""
        return self.message.get('status')

    @property
    def sub(self) -> str:
        """Get the sub"""
        return self.message.get('sub')

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

    @property
    def is_success(self) -> bool:
        """Get the status"""
        return self.status == 'success'
    
    @property
    def isSubscription(self) -> bool:
        """ server will indicate with True or False """
        return self.sub
        
    @property
    def isResponse(self) -> bool:
        """ server will indicate with True or False """
        return not self.isSubscription

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
        self.stop = asyncio.Event()

    @property
    def host(self):
        return self.hostPort[0]

    @property
    def port(self):
        return self.hostPort[1]

    @property
    def isClient(self):
        return self.hostPort[1] != 24602
    
    @property
    def isServer(self):
        return not self.isClient

    def add_subcription(self, table_uuid: str):
        self.subscriptions.append(table_uuid)


class DataClient:
    def __init__(
        self,
        host: str,
        port: int,
        db_path: str = "../../data",
        db_name: str = "data.db",
        server: Union[DataServer, None], #import
    ):

        self.host = host
        self.port = port
        self.server = server
        self.connectedServers: Dict[Tuple[str, int], ConnectedPeer] = {}
        # an optimization
        # self.subscriptions: Dict[int, ConnectedPeer] = {}
        self.subscriptions: dict[Subscription, queue.Queue] = {}
        self.responses: dict[str, Message] = {}
        self.db = SqliteDatabase(db_path, db_name)

    async def connectToPeer(self, peerHost: str, peerPort: int) -> bool:
        """Connect to another peer"""
        uri = f"ws://{peerHost}:{peerPort}"
        try:
            websocket = await websockets.connect(uri)
            self.connectedServers[(peerHost, peerPort)] = ConnectedPeer(
                (peerHost, peerPort), websocket
            )
            asyncio.create_task(self.listenToPeer(self.connectedServers[(peerHost, peerPort)]))
            debug(f"Connected to peer at {uri}", print=True)
            return True
        except Exception as e:
            error(f"Failed to connect to peer at {uri}: {e}")
            return False


    async def listenToPeer(self, peer: ConnectedPeer):
        """Listen for messages from a connected peer"""

        def handleMultipleMessages(buffer: str):
            ''' split on the first newline to handle multiple messages '''
            return buffer.partition('\n')

        async def listen():
            try:
                response = Message(json.loads(await peer.websocket.recv()))
                await self.handleMessage(response)
            except websockets.exceptions.ConnectionClosed:
                self.disconnect(peer)

        while not peer.stop.is_set():
            await listen()
 
    def findSubscription(self, subscription: Subscription) -> Subscription:
        for s in self.subscriptions.keys():
            if s == subscription:
                return s
        return subscription

    @staticmethod
    def _generateCallId() -> str:
        return str(time.time())

    async def handleMessage(self, message: Message) -> None:
        if message.isSubscription:
            if self.server is not None: 
                self.server.notifySubscribers(message)
            subscription = self.findSubscription(
                subscription=Subscription(message.method, params=[]))
            q = self.subscriptions.get(subscription) # when we ask for a subscription we save.
            if isinstance(q, queue.Queue):
                q.put(message)
            subscription(message)
        elif message.isResponse:
            self.responses[
                message.get('id', self._generateCallId())] = message

    def listenForSubscriptions(self, method: str, params: list) -> dict:
        return self.subscriptions[Subscription(method, params)].get()

    def listenForResponse(self, callId: Union[str, None] = None) -> Union[dict, None]:
        then = time.time()
        while time.time() < then + 30:
            response = self.responses.get(callId)
            if response is not None:
                del self.responses[callId]
                self.cleanUpResponses()
                return response
            time.sleep(1)
        return None

    def cleanUpResponses(self):
        '''
        clear all stale responses since the key is a stringed time.time()
        '''
        currentTime = time.time()
        stale = 30
        keysToDelete = []
        for key in self.responses.keys():
            try:
                if float(key) < currentTime - stale:
                    keysToDelete.append(key)
            except Exception as e:
                warning(f'error in cleanUpResponses {e}')
        for key in keysToDelete:
            del self.responses[key]

    # todo add all
    async def handleResponse(self, response: Message) -> None:
        if response.status == "success" and response.data is not None:
            try:
                df = pd.read_json(StringIO(response.data), orient='split')
                if response.method in ["record-at-or-before", "data-in-range"]:
                    self.db.deleteTable(response.table_uuid)
                    self.db.createTable(response.table_uuid)
                self.db._dataframeToDatabase(response.table_uuid, df)
                info(f"\nData saved to database: {self.db.dbname}")
                debug(f"Table name: {response.table_uuid}")
            except Exception as e:
                error(f"Database error: {e}")

    async def disconnect(self, peer: ConnectedPeer) -> None:
        peer.stop.set()
        await peer.websocket.close()
        del peer

    async def disconnectAll(self):
        """Disconnect from all peers and stop the server"""
        for connectedPeer in self.connectedServers.values():
            self.disconnect(connectedPeer)
        info("Disconnected from all peers and stopped server")

    async def connect(
        self,
        peerAddr: Tuple[str, int],
        request: Message,
    ) -> Dict:
        if peerAddr not in self.connectedServers:
            peerHost, peerPort = peerAddr
            success = await self.connectToPeer(peerHost, peerPort)
            if not success:
                return {"status": "error", "id": request.id, "message": "Failed to connect to peer"}

    async def send(
        self, 
        peerAddr: Tuple[str, int], 
        request: Message, 
        sendOnly: bool = False,
    ) -> Dict:
        """Send a request to a specific peer"""
        if request.id is None:
            request.id = self._generateCallId()
        self.connect(peerAddr, request)
        msg = request.to_json()
        try:
            await self.connectedServers[peerAddr].websocket.send(msg)
            if sendOnly:
                return None
            return self.listenForResponse(request.id)
        except Exception as e:
            error(f"Error sending request to peer: {e}")
            return {"status": "error", "message": str(e)}
    
    # should we need this?
    #def resubscribe(self):
    #    if self.connected():
    #        for subscription in self.subscriptions.keys():
    #            self.subscribe(subscription.method, *subscription.params)

    # Refactor: could be made to look like sendRequest creating method from passed in details:
    async def subscribe(
        self,
        peerAddr: Tuple[str, int], 
        request: Message, 
        callback: Union[callable, None] = None,
    ):
        self.subscriptions[
            Subscription(request.method, request.params, callback=callback)
        ] = queue.Queue()
        return await self.send(peerAddr, request)

    async def sendRequest(
        self,
        peer_addr: Tuple[str, int],
        table_uuid: str = None,
        method: str = "stream_data",
        data: pd.DataFrame = None,
        replace: bool = False,
        fromDate: str = None,
        toDate: str = None,
    ) -> Dict:
        
        from datetime import datetime
        idStr: str = str(
            generateUUID({'method': method, 'currentTime': datetime.now()})
        )

        if method == "initiate-connection":
            request = Message({"method": method, "id": idStr})
        elif method == "data-in-range" and data is not None:
            if 'from_ts' in data.columns and 'to_ts' in data.columns:
                fromDate = data['from_ts'].iloc[0]
                toDate = data['to_ts'].iloc[0]
            else:
                raise ValueError(
                    "DataFrame must contain 'from_ts' and 'to_ts' columns for date range queries"
                )
        elif method == "record-at-or-before":
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
                "method": method,
                "id": idStr,
                "params": {
                    "table_uuid": table_uuid,
                    "replace": replace,
                    "from_ts": fromDate,
                    "to_ts": toDate,
                },
                "data": data,
            }
        )
        return await self.send(peer_addr, request)
    

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
    peer1 = DataClient("0.0.0.0", 8080)
    await peer1.start_server()
    await asyncio.Future()  # run forever

    # peer1 = DataClient("ws://localhost:8765")
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
