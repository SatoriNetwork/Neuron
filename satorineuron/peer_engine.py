import threading
import time
from typing import Dict, List, Union
from queue import Queue
import random

from satorineuron import logging
from satorineuron.common.structs import ConnectionTo
from satorilib.concepts.structs import StreamId
from satorilib.api.interfaces import SatoriPeer

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class PeerEngine(metaclass=SingletonMeta):
    def __init__(self):
        self.peers: Dict[str, SatoriPeer] = {}
        self.peer_streams: Dict[str, List[StreamId]] = {}
        self.connection_status: Dict[str, bool] = {}
        self.message_queue: Queue = Queue()
        self.is_running: bool = False
        self.thread: Union[threading.Thread, None] = None

    def start(self):
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            logging.info('Started peer engine', color='green')

    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join()
        logging.info('Stopped peer engine', color='yellow')

    def _run(self):
        while self.is_running:
            self._process_messages()
            self._check_connections()
            time.sleep(1)

    def _process_messages(self):
        while not self.message_queue.empty():
            message = self.message_queue.get()
            self._handle_message(message)

    def _handle_message(self, message):
        # Implement message handling logic here
        pass

    def _check_connections(self):
        for peer_id, peer in self.peers.items():
            is_connected = peer.is_connected()
            if is_connected != self.connection_status.get(peer_id):
                self.connection_status[peer_id] = is_connected
                self._update_connection_status(peer_id, is_connected)

    def _update_connection_status(self, peer_id: str, status: bool):
        logging.info(f'Peer {peer_id} connection status: {"Connected" if status else "Disconnected"}', color='cyan')
        # You might want to notify other parts of the system about this change

    def add_peer(self, peer: SatoriPeer):
        self.peers[peer.id] = peer
        self.connection_status[peer.id] = False
        logging.info(f'Added peer: {peer.id}', color='green')

    def remove_peer(self, peer_id: str):
        if peer_id in self.peers:
            del self.peers[peer_id]
            del self.connection_status[peer_id]
            logging.info(f'Removed peer: {peer_id}', color='yellow')

    def get_peer(self, peer_id: str) -> Union[SatoriPeer, None]:
        return self.peers.get(peer_id)

    def get_all_peers(self) -> List[SatoriPeer]:
        return list(self.peers.values())

    def send_message(self, peer_id: str, message: dict):
        peer = self.get_peer(peer_id)
        if peer:
            peer.send_message(message)
        else:
            logging.warning(f'Attempted to send message to unknown peer: {peer_id}', color='red')

    def broadcast_message(self, message: dict):
        for peer in self.peers.values():
            peer.send_message(message)

    def register_stream(self, peer_id: str, stream_id: StreamId):
        if peer_id not in self.peer_streams:
            self.peer_streams[peer_id] = []
        self.peer_streams[peer_id].append(stream_id)

    def get_peers_for_stream(self, stream_id: StreamId) -> List[SatoriPeer]:
        return [peer for peer_id, streams in self.peer_streams.items() 
                if stream_id in streams and peer_id in self.peers]

    def sync_stream(self, stream_id: StreamId):
        peers = self.get_peers_for_stream(stream_id)
        if peers:
            chosen_peer = random.choice(peers)
            # Implement sync logic here
            logging.info(f'Syncing stream {stream_id} with peer {chosen_peer.id}', color='cyan')
        else:
            logging.warning(f'No peers available for stream {stream_id}', color='yellow')

# Singleton instance
peer_engine = PeerEngine()

def get_peer_engine() -> PeerEngine:
    return peer_engine