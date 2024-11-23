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
import pickle
import requests
from queue import Queue, Empty
from typing import List, Dict
from satorineuron import logging
from satorineuron.p2p.peer_manager import PeerManager
from satorineuron.p2p.my_conf import WireguardInfo
from satorineuron.p2p.wireguard_manager import save_config
from satorilib.api.disk.cache import Cache

class StreamIdEncoder(json.JSONEncoder):
    """Custom JSON encoder for handling StreamId objects and other custom types"""
    def default(self, obj):
        if hasattr(obj, 'to_dict'):  # Handle StreamId objects
            return {'_type': 'StreamId', 'data': obj.to_dict()}
        if isinstance(obj, Cache):
            return {
                '_type': 'Cache',
                'data': pickle.dumps(obj).hex()
            }
        return super().default(obj)

class StreamIdDecoder(json.JSONDecoder):
    """Custom JSON decoder for handling StreamId objects and other custom types"""
    def __init__(self, *args, **kwargs):
        json.JSONDecoder.__init__(self, object_hook=self.object_hook, *args, **kwargs)
    
    def object_hook(self, dct):
        if '_type' in dct:
            if dct['_type'] == 'StreamId':
                from satorilib.api.stream import StreamId  # Import here to avoid circular imports
                return StreamId.from_dict(dct['data'])
            elif dct['_type'] == 'Cache':
                return pickle.loads(bytes.fromhex(dct['data']))
        return dct

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
        caches: Dict[str, Cache] = None,
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
        self.cache_objects: Dict[str, Cache] = caches or {}  # Store Cache objects
        self.connected_peers = set()
        self.running = False
        self.ping_interval = 10
        self.last_cache_update = {}
    
    def _serialize_stream_data(self, data):
        """Serialize data with custom encoder for StreamId and Cache objects"""
        return json.dumps(data, cls=StreamIdEncoder)

    def _deserialize_stream_data(self, data_str):
        """Deserialize data with custom decoder for StreamId and Cache objects"""
        return json.loads(data_str, cls=StreamIdDecoder)

    def _encode_stream_id(self, stream_id):
        """Safely encode stream ID for storage and transmission"""
        try:
            # Handle StreamId objects
            if hasattr(stream_id, 'to_dict'):
                return json.dumps({'_type': 'StreamId', 'data': stream_id.to_dict()}, 
                                cls=StreamIdEncoder)
            # Handle dictionary stream IDs
            elif isinstance(stream_id, dict):
                return json.dumps(stream_id, cls=StreamIdEncoder)
            # Handle string stream IDs
            return str(stream_id)
        except Exception as e:
            logging.error(f"Error encoding stream ID: {str(e)}")
            raise

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
        # print(self.cache_objects)
        self.start_background_tasks()
        self.start_listening()
        self.start_peer_check_loop()
        self.start_ping_loop(self.ping_interval)
        self._initialize_caches()
        cache_data=self.get_cache_for_all_publications()
        print(json.dumps(cache_data, indent=2))

    def _initialize_caches(self):
        """Initialize caches for all publications during startup"""
        try:
            for publication in self.publications:
                # Get initial cache data from server
                response = self.get_cache(publication)
                if response and response.get("status") == "success":
                    self.update_cache(publication, response.get("cache", []))
        except Exception as e:
            logging.error(f"Error initializing caches: {str(e)}")    

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
        """Perform check-in with server, including Cache objects"""
        try:
            wg_info = self.my_info.get_wireguard_info()
            self.wireguard_config["wireguard_config"] = wg_info
            
            # Prepare cache payload using proper serialization
            cache_payload = {
                self._encode_stream_id(stream_id): {
                    'cache_object': cache_obj,
                    'timestamp': self.last_cache_update.get(stream_id, time.time())
                }
                for stream_id, cache_obj in self.cache_objects.items()
            }
            
            # Log the cache payload for debugging
            print("Cache payload being sent to the server:")
            # print(json.dumps(cache_payload, indent=2, cls=StreamIdEncoder))  # Use custom encoder
            
            # Serialize data with custom encoder
            json_data = json.dumps({
                "peer_id": self.client_id,
                "wireguard_config": self.wireguard_config["wireguard_config"],
                "publications": [self._encode_stream_id(pub) for pub in self.publications],
                "subscriptions": [self._encode_stream_id(sub) for sub in self.subscriptions],
                "caches": cache_payload
            }, cls=StreamIdEncoder)  # Apply the custom encoder here
            
            response = requests.post(
                f"{self.server_url}/checkin",
                headers={'Content-Type': 'application/json'},
                data=json_data
            )
            
            if response.status_code == 200:
                # Deserialize response with custom decoder
                return self._deserialize_stream_data(response.text)
            
            logging.error(f"Checkin failed with status code: {response.status_code}")
            return None
            
        except Exception as e:
            logging.error(f"Checkin failed: {str(e)}")
            return None

        
    def handle_new_data(self, stream_id: str, data: any):
        """Handle new data received for a stream"""
        try:
            # Update cache with new data
            self.update_cache(stream_id, data)
            
            # Additional data handling logic here...
            
        except Exception as e:
            logging.error(f"Error handling new data for stream {stream_id}: {str(e)}") 

    def sync_history_with_server(self):
        """Sync local history with server periodically"""
        try:
            current_time = time.time()
            
            # Only sync caches that have been updated recently
            for stream_id in self.publications:
                last_update = self.last_cache_update.get(stream_id, 0)
                if current_time - last_update < 1800:  # 30 minutes
                    cache_data = self.local_cache.get(stream_id, [])
                    self._sync_cache_with_server(stream_id, cache_data)
                    
        except Exception as e:
            logging.error(f"History sync failed: {str(e)}")

    def update_cache(self, stream_id: str, cache_obj: Cache):
        """Update cache with a Cache object for a specific stream"""
        try:
            encoded_stream_id = self._encode_stream_id(stream_id)
            current_time = time.time()
            
            self.cache_objects[encoded_stream_id] = cache_obj
            self.last_cache_update[encoded_stream_id] = current_time
            
            # Sync with server using proper serialization
            json_data = self._serialize_stream_data({
                "peer_id": self.client_id,
                "stream_id": stream_id,
                "cache": cache_obj
            })
            
            response = requests.post(
                f"{self.server_url}/update_cache",
                headers={'Content-Type': 'application/json'},
                data=json_data
            )
            
            if response.status_code != 200:
                logging.error(f"Failed to sync cache with server: {response.status_code}")
                
        except Exception as e:
            logging.error(f"Error updating cache for stream {stream_id}: {str(e)}")
            raise
    
    def _sync_cache_with_server(self, stream_id: str, cache_obj: Cache):
        """
        Sync Cache object with server
        
        Args:
            stream_id (str): The stream identifier (can be StreamId object or string)
            cache_obj (Cache): The Cache object to sync
        """
        try:
            # Use the new serialization helper which handles both StreamId and Cache objects
            json_data = self._serialize_stream_data({
                "peer_id": self.client_id,
                "stream_id": stream_id,  # Will be properly encoded by StreamIdEncoder
                "cache": cache_obj       # Will be properly encoded by StreamIdEncoder
            })
            
            response = requests.post(
                f"{self.server_url}/update_cache",
                headers={'Content-Type': 'application/json'},
                data=json_data
            )
            
            if response.status_code == 200:
                encoded_stream_id = self._encode_stream_id(stream_id)
                logging.debug(f"Successfully synced cache object for stream {encoded_stream_id}")
            else:
                logging.error(f"Failed to sync cache with server: {response.status_code}")
                if response.text:
                    logging.error(f"Server response: {response.text}")
                    
        except Exception as e:
            logging.error(f"Error syncing cache with server: {str(e)}")
            raise  # Propagate the error to be handled by the caller
    
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

    def get_cache(self, stream_id: str):
        """Retrieve Cache object for a specific stream"""
        try:
            encoded_stream_id = self._encode_stream_id(stream_id)
            
            if encoded_stream_id in self.cache_objects:
                last_update = self.last_cache_update.get(encoded_stream_id, 0)
                if time.time() - last_update < 1800:  # 30 minutes
                    return self.cache_objects[encoded_stream_id]
            
            try:
                response = requests.get(
                    f"{self.server_url}/get_cache",
                    params={"stream_id": encoded_stream_id},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = self._deserialize_stream_data(response.text)
                    if isinstance(data, dict) and 'cache' in data:
                        cache_obj = data['cache']
                        if isinstance(cache_obj, Cache):
                            self.update_cache(stream_id, cache_obj)
                            return cache_obj
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Server request failed for stream {encoded_stream_id}: {str(e)}")
                if encoded_stream_id in self.cache_objects:
                    return self.cache_objects[encoded_stream_id]
                
        except Exception as e:
            logging.error(f"Error in get_cache for stream {stream_id}: {str(e)}")
        
        return None

    def get_cache_for_all_publications(self) -> Dict[str, Cache]:
        """
        Fetch Cache objects from the server for all publications.
        
        Returns:
            Dict[str, Cache]: Dictionary mapping publication IDs to their Cache objects
        """
        if not self.publications:
            logging.info("No publications available to fetch cache for.")
            return {}

        all_cache_objects = {}
        failed_publications = []

        for publication in self.publications:
            try:
                logging.debug(f"Attempting to fetch cache for publication: {publication}")
                cache_obj = self.get_cache(publication)
                
                if cache_obj is not None:
                    all_cache_objects[publication] = cache_obj
                    logging.debug(f"Successfully fetched cache for {publication}")
                else:
                    logging.info(f"No cache data available for {publication}")
                    
            except Exception as e:
                failed_publications.append(publication)
                logging.error(f"Error processing publication {publication}: {str(e)}")

        if failed_publications:
            logging.warning(f"Failed publications: {', '.join(str(p) for p in failed_publications)}")
        
        logging.info(f"Successfully fetched cache for {len(all_cache_objects)} publications")
        return all_cache_objects
        
    def stop(self):
        """Stop the PeerEngine and cleanup"""
        self.running = False
        if hasattr(self, 'background_thread'):
            self.background_thread.join(timeout=1)
        logging.info("PeerEngine stopped", color="green")
