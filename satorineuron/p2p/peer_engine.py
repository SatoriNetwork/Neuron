'''
Installer functionality - (need to integrate p2p wireguard with this layer)
Neuron functionality - (need to integrate p2p with this layer)
p2p functionality - connects to server and manages peers
p2p server - (need upgrade to handle peers keys)

current:
start.py -> checkin() -> get key from server -> pass the key to pubsub -> pubsub interprets the key and knows what datastreams we publish and subscribe to

want:
start.py -> checkin() -> get key from server -> pass the key to p2p server -> p2p server interprets the key and knows what datastreams we publish and subscribe to (provide peers)

goal: from the neuron we can ask the p2p server for specific datastream connections rather than specific peers


'''

import json
import subprocess
import threading
import time
import requests
from queue import Queue, Empty
from typing import List, Dict
from satorineuron import logging
from satorineuron.p2p.peer_manager import PeerManager
from satorineuron.p2p.my_conf import WireguardInfo
from satorineuron.p2p.wireguard_manager import save_config

class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]

class PeerEngine(metaclass=SingletonMeta):
    '''Connects to server and manages peers based on datastream subscriptions'''

    def __init__(
        self, 
        interface="wg0", 
        config_file="peers.json", 
        port=51820, 
        publications: list[str] = None,
        subscriptions: list[str] = None,
    ):
        self.interface = interface
        self.config_file = config_file
        self.port = port
        self.my_info = WireguardInfo()
        self.wireguard_config = {}
        self.client_id = ''
        self.server_url = "http://188.166.4.120:51820"
        self.ip_address = self._get_unique_ip()
        self.connection_queue = Queue()
        self.peerManager = PeerManager(self.interface, self.config_file, self.port)
        self.publications = publications or []
        self.subscriptions = subscriptions or []
        self.connected_peers = set()
        self.running = False

    def _get_unique_ip(self):
        """Get a unique IP address from the PeerServer"""
        response = requests.get(f"{self.server_url}/get_unique_ip")
        if response.status_code == 200:
            return response.json()["ip_address"]
        else:
            raise Exception(f"Failed to get unique IP address: {response.status_code}")

    def start(self):
        """Start the PeerEngine and initialize connections"""
        logging.info('PeerEngine started', color='green')
        self.peerManager.start(self.ip_address)
        wg_info = self.my_info.get_wireguard_info()
        self.client_id = wg_info['public_key']
        self.start_background_tasks()
        self.start_listening()
        self.start_ping_loop()
        self.start_peer_check_loop()

    def start_listening(self):
        """Listen for and process new peer connection requests"""
        def listen_loop():
            while True:
                try:
                    peer_connection = self.connection_queue.get(timeout=1)
                    self.peerManager.add_peer(
                        peer_connection["public_key"],
                        peer_connection["allowed_ips"],
                        peer_connection["endpoint"]
                    )
                    save_config(self.interface)
                except Empty:
                    time.sleep(0.1)
                except Exception as e:
                    logging.error(f"Error in listen_loop: {str(e)}")

        threading.Thread(target=listen_loop, daemon=True).start()

    def connect_to_peers(self):
        """Connect to relevant peers based on complementary pub/sub relationships"""
        try:
            # Get all peers and their stream information
            response = requests.get(f"{self.server_url}/list_peers")
            if response.status_code != 200:
                raise Exception(f"Failed to get peers: {response.status_code}")
            
            peers = response.json()['peers']
            
            for peer in peers:
                peer_id = peer['peer_id']
                if peer_id == self.client_id:
                    continue

                should_connect = False
                
                # Check if this peer subscribes to any of our publications
                for pub in self.publications:
                    if pub in peer.get('subscriptions', []):
                        should_connect = True
                        break

                # Check if this peer publishes any of our subscriptions
                for sub in self.subscriptions:
                    if sub in peer.get('publications', []):
                        should_connect = True
                        break

                if should_connect and peer_id not in self.connected_peers:
                    self.request_connection(peer_id)

        except Exception as e:
            logging.error(f"Error in connect_to_peers: {str(e)}")

    def request_connection(self, peer_id: str):
        """Request connection to a specific peer through the server"""
        try:
            response = requests.post(
                f"{self.server_url}/connect",
                json={
                    "from_peer": self.client_id,
                    "to_peer": peer_id
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "connected":
                    peer_data = {
                        'public_key': data['to_peer'],
                        'allowed_ips': data['to_peer_config']['allowed_ips'],
                        'endpoint': data['to_peer_config']['endpoint']
                    }
                    self.connection_queue.put(peer_data)
                    self.connected_peers.add(peer_id)
                    logging.info(f"Successfully connected to peer {peer_id}", color="green")
                    return True
            
            logging.error(f"Failed to connect to peer {peer_id}")
            return False
            
        except Exception as e:
            logging.error(f"Error requesting connection to peer {peer_id}: {str(e)}")
            return False

    def checkin(self):
        """Perform check-in with server, including datastream information"""
        wg_info = self.my_info.get_wireguard_info()
        self.wireguard_config["wireguard_config"] = wg_info
        try:
            response = requests.post(
                f"{self.server_url}/checkin",
                json={
                    "peer_id": self.client_id,
                    "wireguard_config": self.wireguard_config["wireguard_config"],
                    "publications": self.publications,
                    "subscriptions": self.subscriptions
                }
            )
            return response.json()
        except Exception as e:
            logging.error(f"Checkin failed: {str(e)}")
            return None

    def add_publication(self, stream_name: str):
        """Add a publication stream and connect to relevant subscribers"""
        if stream_name not in self.publications:
            self.publications.append(stream_name)
            self.checkin()
            self.connect_to_peers()
            logging.info(f"Added publication stream: {stream_name}", color="green")

    def add_subscription(self, stream_name: str):
        """Add a subscription stream and connect to relevant publishers"""
        if stream_name not in self.subscriptions:
            self.subscriptions.append(stream_name)
            self.checkin()
            self.connect_to_peers()
            logging.info(f"Added subscription stream: {stream_name}", color="green")

    def remove_publication(self, stream_name: str):
        """Remove a publication stream"""
        if stream_name in self.publications:
            self.publications.remove(stream_name)
            self.checkin()
            logging.info(f"Removed publication stream: {stream_name}", color="green")

    def remove_subscription(self, stream_name: str):
        """Remove a subscription stream"""
        if stream_name in self.subscriptions:
            self.subscriptions.remove(stream_name)
            self.checkin()
            logging.info(f"Removed subscription stream: {stream_name}", color="green")

    def start_background_tasks(self):
        """Start background tasks for maintenance and updates"""
        self.running = True

        def background_loop():
            while self.running:
                self.checkin()
                self.connect_to_peers()
                time.sleep(1800)  # 30 minutes interval

        self.background_thread = threading.Thread(target=background_loop)
        self.background_thread.daemon = True
        self.background_thread.start()

    def start_ping_loop(self, interval=5):
        """Start background ping monitoring of connected peers"""
        def ping_peers():
            while self.running:
                time.sleep(interval)
                for peer in self.peerManager.list_peers():
                    peer_id = peer.get("public_key")
                    ping_ip = peer.get('allowed_ips', '').split('/')[0]
                    try:
                        self.run_ping_command(ping_ip)
                    except Exception as e:
                        logging.error(f"Failed to ping peer {peer_id}: {e}")
        
        threading.Thread(target=ping_peers, daemon=True).start()

    def start_peer_check_loop(self, interval=15):
        """Start a loop to periodically check for new peers"""
        def check_peers():
            while self.running:
                self.connect_to_peers()
                time.sleep(interval)

        threading.Thread(target=check_peers, daemon=True).start()

    def run_ping_command(self, ip: str):
        """Execute ping command to check peer connectivity"""
        result = subprocess.run(["ping", "-c", "1", ip], capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Ping to {ip} successful", color="blue")
        else:
            logging.error(f"Ping to {ip} failed: {result.stderr}", color="blue")

    def stop(self):
        """Stop the PeerEngine and cleanup"""
        self.running = False
        if hasattr(self, 'background_thread'):
            self.background_thread.join(timeout=1)
        logging.info("PeerEngine stopped", color="green")
