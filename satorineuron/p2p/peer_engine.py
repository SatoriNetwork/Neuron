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
                
                for pub in self.publications:
                    if pub in peer.get('subscriptions', []):
                        should_connect = True
                        break

                for sub in self.subscriptions:
                    if sub in peer.get('publications', []):
                        should_connect = True
                        break

                if should_connect:
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
            new_config = new_peer.get('wireguard_config', {})
            new_allowed_ips = new_config.get('allowed_ips')

            if existing_peer.get('allowed_ips') != new_allowed_ips:
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
        
    @staticmethod
    def update_peer_data(server_url: str, client_id: str, cache_data: dict):
        """
        Upload cache data to the server using the update_peer endpoint
        
        Args:
            server_url (str): The base URL of the peer server
            client_id (str): The public key of the client
            cache_data (dict): Dictionary mapping stream IDs to Cache objects
        """
        try:
            # Convert the stream IDs and cache objects into a format suitable for transmission
            formatted_data = {}
            for stream_id, cache_obj in cache_data.items():
                # Convert stream_id dict to a string key
                if isinstance(stream_id, dict):
                    key = f"{stream_id['source']}.{stream_id['author']}.{stream_id['stream']}.{stream_id['target']}"
                else:
                    key = str(stream_id)
                
                formatted_data[key] = cache_obj

            # Prepare the payload
            payload = {
                "peer_id": client_id,
                "cache_data": formatted_data
            }

            # # Print the data being uploaded
            # logging.info("Uploading the following data to server:", color="cyan")
            # for key, value in formatted_data.items():
            #     logging.info(f"Stream ID: {key}", color="cyan")
            #     if hasattr(value, 'data'):
            #         logging.info(f"Cache Data: {value.data}", color="cyan")
            #     else:
            #         logging.info(f"Cache Data: {value}", color="cyan")

            # Serialize the payload using the custom encoder
            json_data = json.dumps(payload, cls=StreamIdEncoder)

            # Send the request
            response = requests.post(
                f"{server_url}/update_peer",
                headers={'Content-Type': 'application/json'},
                data=json_data
            )

            if response.status_code == 200:
                logging.info("Successfully updated peer data", color="green")
                return response.json()
            else:
                logging.error(f"Failed to update peer data. Status code: {response.status_code}")
                return None

        except Exception as e:
            logging.error(f"Error updating peer data: {str(e)}")
            return None
        
    def get_peer_data(self):
        """
        Retrieve cache data from the server based on publications.
        
        Returns:
            dict: Dictionary mapping stream IDs (as dictionaries) to Cache objects
                Returns None if the request fails
        """
        try:
            # Prepare the request payload with publications
            payload = {
                "peer_id": self.client_id,
                "publications": [self._encode_stream_id(pub) for pub in self.publications]
            }

            # Serialize the payload using the custom encoder
            json_data = json.dumps(payload, cls=StreamIdEncoder)

            # Send the request to get peer data
            response = requests.post(
                f"{self.server_url}/get_peer_data",
                headers={'Content-Type': 'application/json'},
                data=json_data
            )

            if response.status_code == 200:
                # Deserialize the response using the custom decoder
                raw_data = self._deserialize_stream_data(response.text)
                
                if not isinstance(raw_data, dict):
                    logging.error("Invalid data format received from server")
                    return None

                # Process and validate the received data
                processed_data = {}
                
                # Filter out system-level keys that shouldn't be treated as stream IDs
                system_keys = {'cache_data', 'message', 'peer_id', 'request_timestamp', 'status', 'streams_found'}
                
                for stream_id_str, cache_data in raw_data.items():
                    try:
                        # Skip system-level keys
                        if stream_id_str in system_keys:
                            continue
                            
                        # Parse the string stream ID back into a dictionary
                        if isinstance(stream_id_str, str) and '.' in stream_id_str:
                            parts = stream_id_str.split('.')
                            if len(parts) == 4:  # Ensure we have all required parts
                                source, author, stream, target = parts
                                stream_id = {
                                    'source': source,
                                    'author': author,
                                    'stream': stream,
                                    'target': target
                                }
                            else:
                                logging.warning(f"Skipping malformed stream ID: {stream_id_str}")
                                continue
                        elif isinstance(stream_id_str, dict):
                            stream_id = stream_id_str
                        else:
                            logging.warning(f"Skipping invalid stream ID format: {stream_id_str}")
                            continue

                        # Validate cache data
                        if isinstance(cache_data, Cache):
                            processed_data[json.dumps(stream_id)] = cache_data
                        elif isinstance(cache_data, dict) and '_type' in cache_data and cache_data['_type'] == 'Cache':
                            try:
                                cache_obj = pickle.loads(bytes.fromhex(cache_data['data']))
                                if isinstance(cache_obj, Cache):
                                    processed_data[json.dumps(stream_id)] = cache_obj
                                else:
                                    logging.warning(f"Invalid cache object for stream {stream_id}")
                            except Exception as e:
                                logging.warning(f"Error deserializing cache data for stream {stream_id}: {str(e)}")
                        else:
                            logging.warning(f"Skipping invalid cache data format for stream {stream_id}")

                    except Exception as e:
                        logging.error(f"Error processing stream ID {stream_id_str}: {str(e)}")
                        continue

                # Log only valid processed data
                if processed_data:
                    logging.info("Retrieved the following data from server:", color="cyan")
                    for stream_id, cache_obj in processed_data.items():
                        logging.info(f"Stream ID: {stream_id}", color="cyan")
                        if hasattr(cache_obj, 'data'):
                            logging.info(f"Cache Data: {cache_obj.data}", color="cyan")
                        else:
                            logging.info(f"Cache Data: {cache_obj}", color="cyan")

                    logging.info("Successfully retrieved peer data", color="green")
                else:
                    logging.warning("No valid cache data found in server response")

                return processed_data

            else:
                logging.error(f"Failed to retrieve peer data. Status code: {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Network error retrieving peer data: {str(e)}")
            return None
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding server response: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error retrieving peer data: {str(e)}")
            return None
    
    def checkin(self):
        """Perform check-in with server and update peer data"""
        try:
            wg_info = self.my_info.get_wireguard_info()
            self.wireguard_config["wireguard_config"] = wg_info
            
            # Serialize data with custom encoder
            json_data = json.dumps({
                "peer_id": self.client_id,
                "wireguard_config": self.wireguard_config["wireguard_config"],
                "publications": [self._encode_stream_id(pub) for pub in self.publications],
                "subscriptions": [self._encode_stream_id(sub) for sub in self.subscriptions],
            }, cls=StreamIdEncoder)
            
            response = requests.post(
                f"{self.server_url}/checkin",
                headers={'Content-Type': 'application/json'},
                data=json_data
            )
            
            if response.status_code == 200:
                # After successful checkin, update peer data
                if self.cache_objects:
                    update_result = self.update_peer_data(
                        self.server_url,
                        self.client_id,
                        self.cache_objects
                    )
                    if update_result:
                        logging.info("Successfully updated peer cache data after checkin", color="green")
                        
                        # After successful update, get peer data
                        peer_data = self.get_peer_data()
                        if peer_data is not None:
                            logging.info("Successfully retrieved updated peer data", color="green")
                            return peer_data
                        else:
                            logging.warning("Failed to retrieve peer data after update", color="yellow")
                    else:
                        logging.warning("Failed to update peer cache data after checkin", color="yellow")
                else:
                    # If there are no cache objects to update, still get peer data
                    peer_data = self.get_peer_data()
                    if peer_data is not None:
                        logging.info("Successfully retrieved peer data", color="green")
                        return peer_data
                
                # If we reach here, return the original checkin response
                return self._deserialize_stream_data(response.text)
            
            logging.error(f"Checkin failed with status code: {response.status_code}")
            return None
            
        except Exception as e:
            logging.error(f"Checkin failed: {str(e)}")
            return None

        
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
        
    def stop(self):
        """Stop the PeerEngine and cleanup"""
        self.running = False
        if hasattr(self, 'background_thread'):
            self.background_thread.join(timeout=1)
        logging.info("PeerEngine stopped", color="green")
