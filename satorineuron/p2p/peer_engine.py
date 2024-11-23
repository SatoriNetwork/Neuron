'''
Installer functionality - (need to integrate p2p wireguard with this layer)
Neuron functionality - (need to integrate p2p with this layer)
p2p functionality - connects to server and manages peers
p2p server - (need upgrade to handle peers keys)

current:complete
start.py -> checkin() -> get key from server -> pass the key to pubsub -> pubsub interprets the key and knows what datastreams we publish and subscribe to

want:
start.py -> checkin() -> get key from server -> pass the key to p2p server -> p2p server interprets the key and knows what datastreams we publish and subscribe to (provide peers)

goal: from the neuron we can ask the p2p server for specific datastream connections rather than specific peers


'''

import json
import socket
import struct
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
        caches:dict[str]= None,
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
        self.history = caches or {}
        self.connected_peers = set()
        self.running = False
        self.ping_interval = 10
        # self.cache_data = {}
        # self.stream_id_str = {}
        self.cache_retry_attempts = 3
        self.cache_retry_delay = 5  # seconds
        self.cache_expiry = 3600  # 1 hour
        self.local_cache = {}
        self.last_cache_update = {}
        self.cache_data = {}  # Initialize empty cache dictionary
        self.stream_history = {}  

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
        self.start_peer_check_loop()
        self.start_ping_loop(self.ping_interval)
        cache_data=self.get_cache_for_all_publications()
        print(json.dumps(cache_data, indent=2))
        

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
            current_peers = {peer['public_key']: peer for peer in self.peerManager.list_peers()}
            
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

                if should_connect:
                    # Check if peer exists and if its configuration has changed
                    if peer_id in current_peers:
                        existing_peer = current_peers[peer_id]
                        if self._peer_config_changed(existing_peer, peer):
                            logging.info(f"Peer {peer_id} configuration changed, updating...", color="yellow")
                            self.peerManager.remove_peer(peer_id)
                            self.connected_peers.discard(peer_id)
                            self.request_connection(peer_id)
                    elif peer_id not in self.connected_peers:
                        self.request_connection(peer_id)
        except Exception as e:
            logging.error(f"Error in connect_to_peers: {str(e)}")

    def _peer_config_changed(self, existing_peer: dict, new_peer: dict) -> bool:
        """
        Compare existing peer configuration with new peer configuration
        Returns True if there are relevant changes that require reconnection
        """
        try:
            # Extract relevant configuration from new_peer
            new_config = new_peer.get('wireguard_config', {})
            # new_endpoint = new_config.get('endpoint')
            new_allowed_ips = new_config.get('allowed_ips')

            # Compare with existing configuration
            if ( existing_peer.get('allowed_ips') != new_allowed_ips):
                return True

            return False
        except Exception as e:
            logging.error(f"Error comparing peer configurations: {str(e)}")
            return False

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
                    peer_data['wireguard_config'] = {
                    'persistent_keepalive': 300  # Set the desired keepalive interval in seconds
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
        cache_payload = {
            stream_id: {
                'data': cache_info['data'],
                'timestamp': cache_info['timestamp']
            }
            for stream_id, cache_info in self.stream_history.items()
        }
        try:
            response = requests.post(
                f"{self.server_url}/checkin",
                json={
                    "peer_id": self.client_id,
                    "wireguard_config": self.wireguard_config["wireguard_config"],
                    "publications": self.publications,
                    "subscriptions": self.subscriptions,
                    "caches": cache_payload
                }
            )
            return response.json()
        except Exception as e:
            logging.error(f"Checkin failed: {str(e)}")
            return None
        
    def sync_history_with_server(self):
        """Sync local history with server periodically"""
        try:
            for stream_id, cache_info in self.stream_history.items():
                self._sync_cache_with_server(stream_id, cache_info['data'])
        except Exception as e:
            logging.error(f"History sync failed: {str(e)}")
    # def sync_history_with_server(self):
    #     """Sync local history with server periodically"""
    #     try:
    #         for stream_id, cache in self.history.items():
    #             self.stream_id_str = str(stream_id) if not isinstance(stream_id, str) else stream_id
    #             self.cache_data = cache if isinstance(cache, (dict, list, str)) else str(cache)
    #             # cache_data = cache 
    #             # print(f"Stream ID: {stream_id_str}, Cache: {cache_data}")
    #             # print(cache_data)
    #             # response = requests.post(f"{self.server_url}/checkin", json={
    #             #     "peer_id": self.client_id,
    #             #     "stream_id": stream_id_str,  # Ensure it's a string
    #             #     "cache": cache_data
    #             # })
    #             # print(response)
    #     except Exception as e:
    #         logging.error(f"History sync failed: {str(e)}")
    def update_cache(self, stream_id: str, data: any):
        """Update cache for a specific stream"""
        try:
            encoded_stream_id = self._encode_stream_id(stream_id)
            self.cache_data[encoded_stream_id] = data
            self.stream_history[encoded_stream_id] = {
                'data': data,
                'timestamp': time.time()
            }
            # Sync with server immediately after update
            self._sync_cache_with_server(encoded_stream_id, data)
        except Exception as e:
            logging.error(f"Error updating cache: {str(e)}")

    def _sync_cache_with_server(self, stream_id: str, cache_data: any):
        """Sync specific cache data with server"""
        try:
            response = requests.post(
                f"{self.server_url}/update_cache",
                json={
                    "peer_id": self.client_id,
                    "stream_id": stream_id,
                    "cache": cache_data
                }
            )
            if response.status_code != 200:
                logging.error(f"Failed to sync cache with server: {response.status_code}")
        except Exception as e:
            logging.error(f"Error syncing cache with server: {str(e)}")

    def start_background_tasks(self):
        """Start background tasks for maintenance and updates"""
        self.running = True

        def background_loop():
            while self.running:
                self.sync_history_with_server()
                self.checkin()
                self.connect_to_peers()
                time.sleep(1800)  # 30 minutes interval 

        self.background_thread = threading.Thread(target=background_loop)
        self.background_thread.daemon = True
        self.background_thread.start()

    def start_ping_loop(self, interval=10):
        """Start background ping monitoring of connected peers"""
        def ping_peers():
            while self.running:
                try:
                    peers = self.peerManager.list_peers()
                    if not peers:
                        logging.debug("No peers to ping", color="blue")
                    for peer in peers:
                        if not self.running:
                            break
                        peer_id = peer.get("public_key")
                        allowed_ips = peer.get('allowed_ips', '')
                        if allowed_ips:
                            ping_ip = allowed_ips.split('/')[0]
                            try:
                                self.run_ping_command(ping_ip)
                            except Exception as e:
                                logging.error(f"Failed to ping peer {peer_id}: {e}", color="red")
                except Exception as e:
                    logging.error(f"Error in ping loop: {str(e)}", color="red")
                finally:
                    time.sleep(interval)
        
        threading.Thread(target=ping_peers, daemon=True, 
                        name="peer-ping-monitor").start()
        logging.info(f"Started ping monitoring with {interval}s interval", color="green")

    def start_peer_check_loop(self, interval=15):
        """Start a loop to periodically check for new peers"""
        def check_peers():
            while self.running:
                self.connect_to_peers()
                time.sleep(interval)

        threading.Thread(target=check_peers, daemon=True).start()

    def run_ping_command(self, ip: str):
        """Execute ping command to check peer connectivity"""
        # try:
            # Initial ping attempt
        result = subprocess.run(["ping", "-c", "1", "-W", "2", ip], 
                            capture_output=True, text=True)
        if result.returncode == 0:
            logging.debug(f"Ping to {ip} successful", color="blue")
            return
        subprocess.run(f"wg-quick down {self.interface}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(f"wg-quick up {self.interface}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(["ping", "-c", "1", "-W", "2", ip], 
                            capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Ping to {ip} successful", color="blue")
            return
        
    def _encode_stream_id(self, stream_id):
        """
        Safely encode stream ID for URL transmission without double encoding.
        Returns the JSON string directly for requests params to handle.
        """
        try:
            if isinstance(stream_id, dict):
                return json.dumps(stream_id)
            return str(stream_id)
        except Exception as e:
            logging.error(f"Error encoding stream ID: {str(e)}")
            raise

    def get_cache(self, stream_id):
        """
        Fetch cached data from the server for a specific stream ID with fixed encoding.
        """
        try:
            # Check local cache first
            if hasattr(self, 'local_cache') and hasattr(self, '_is_cache_valid'):
                if self._is_cache_valid(stream_id):
                    logging.debug(f"Returning cached data for stream ID: {stream_id}")
                    return {"status": "success", "cache": self.local_cache[stream_id]}

            # Prepare the stream_id without pre-encoding
            stream_id_param = self._encode_stream_id(stream_id)
            
            try:
                response = requests.get(
                    f"{self.server_url}/get_cache",
                    params={"stream_id": stream_id_param},  # Let requests handle the encoding
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        if hasattr(self, '_update_local_cache'):
                            self._update_local_cache(stream_id, data["cache"])
                        return data
                    
                elif response.status_code == 404:
                    logging.info(f"No cache data available for stream: {stream_id}")
                    return {"status": "success", "cache": []}
                
                else:
                    logging.warning(f"Unexpected response status: {response.status_code}")
                    return {"status": "error", "message": f"Server returned status {response.status_code}"}
                    
            except requests.exceptions.RequestException as e:
                logging.error(f"Request failed for stream ID {stream_id}: {str(e)}")
                return {"status": "error", "message": str(e)}
                
        except Exception as e:
            logging.error(f"Unexpected error in get_cache for stream ID {stream_id}: {str(e)}")
            return {"status": "error", "message": str(e)}

    def get_cache_for_all_publications(self):
        """
        Fetch cached data from the server for all publications with improved logging.
        """
        if not self.publications:
            logging.info("No publications available to fetch cache for.")
            return {}

        all_cache_data = {}
        failed_publications = []

        for publication in self.publications:
            try:
                logging.debug(f"Attempting to fetch cache for publication: {publication}")
                response = self.get_cache(publication)
                
                if response and response.get("status") == "success":
                    cache_data = response.get("cache", [])
                    if cache_data or isinstance(cache_data, list):
                        all_cache_data[publication] = cache_data
                        logging.debug(f"Successfully fetched cache for {publication}")
                    else:
                        logging.info(f"No cache data available for {publication}")
                else:
                    failed_publications.append(publication)
                    error_msg = response.get('message') if response else 'Unknown error'
                    logging.warning(f"Failed to fetch cache for {publication}: {error_msg}")
                
            except Exception as e:
                failed_publications.append(publication)
                logging.error(f"Error processing publication {publication}: {str(e)}")

        if failed_publications:
            logging.warning(f"Failed publications: {', '.join(str(p) for p in failed_publications)}")
        
        logging.info(f"Successfully fetched cache for {len(all_cache_data)} publications")
        return all_cache_data
        
    def stop(self):
        """Stop the PeerEngine and cleanup"""
        self.running = False
        if hasattr(self, 'background_thread'):
            self.background_thread.join(timeout=1)
        logging.info("PeerEngine stopped", color="green")
