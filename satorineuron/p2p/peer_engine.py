import json
import socket
import struct
import signal
import subprocess
import sys
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

def dict_to_stream_key(stream_dict: dict) -> str:
    """Convert a stream dictionary to a unique string key"""
    if not isinstance(stream_dict, dict):
        return str(stream_dict)
    return f"{stream_dict.get('source', '')}.{stream_dict.get('author', '')}.{stream_dict.get('stream', '')}.{stream_dict.get('target', '')}"

def stream_key_to_dict(key: str) -> dict:
    """Convert a stream key string back to a dictionary"""
    parts = key.split('.')
    if len(parts) == 4:
        return {
            'source': parts[0],
            'author': parts[1],
            'stream': parts[2],
            'target': parts[3]
        }
    return key

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
        self.publications = [dict_to_stream_key(pub) for pub in (publications or [])]
        self.subscriptions = [dict_to_stream_key(sub) for sub in (subscriptions or [])]
        self.cache_objects: Dict[str, Cache] = caches or {}  # Store Cache objects
        self.connected_peers = set()
        self.running = False
        self.ping_interval = 10
        self._peer_subscriptions_cache = {}
        self._peer_subscriptions_timestamp = {}
        self.subscription_cache_ttl = 1800
    
    def signal_handler(signum, frame):
        peer_engine = PeerEngine()
        peer_engine.stop()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
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
        self.start_cache_server()
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
                        'endpoint': data['to_peer_config']['endpoint'],
                        'persistent_keepalive': 25 
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

    def connect_to_peers(self):
        """Connect to relevant peers based on complementary pub/sub relationships."""
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

                # Format and log subscriptions/publications for debug
                peer_subscriptions = [dict_to_stream_key(sub) for sub in peer.get('subscriptions', [])]
                peer_publications = [dict_to_stream_key(pub) for pub in peer.get('publications', [])]

                logging.debug(f"My Publications: {self.publications}")
                logging.debug(f"My Subscriptions: {self.subscriptions}")
                logging.debug(f"Peer Publications for {peer_id}: {peer_publications}")
                logging.debug(f"Peer Subscriptions for {peer_id}: {peer_subscriptions}")

                # Match logic for connecting peers
                should_connect = any(pub in peer_subscriptions for pub in self.publications) or \
                                 any(sub in peer_publications for sub in self.subscriptions)

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
    
    @staticmethod
    def get_peer_data(server_url: str, client_id: str):
        """
        Retrieve cache data from the server for a specific peer and print it
        """
        try:
            payload = {"peer_id": client_id}
            
            response = requests.get(
                f"{server_url}/get_peer_data",
                params=payload
            )
            
            if response.status_code == 200:
                cache_data = json.loads(response.text, cls=StreamIdDecoder)
                
                if isinstance(cache_data, dict) and 'cache_data' in cache_data:
                    formatted_data = {}
                    
                    logging.info("\n=== Retrieved Peer Data ===", color="cyan")
                    
                    for key, value in cache_data['cache_data'].items():
                        try:
                            # Convert the string key back to a dictionary if it matches the format
                            stream_id = stream_key_to_dict(key)
                            formatted_key = dict_to_stream_key(stream_id)
                            formatted_data[formatted_key] = value
                            
                            # Print the data immediately
                            logging.info("\nStream Key:", color="cyan")
                            logging.info(f"  {formatted_key}", color="white")
                            
                            logging.info("Cache Data:", color="cyan")
                            if hasattr(value, 'data'):
                                if isinstance(value.data, dict):
                                    for k, v in value.data.items():
                                        logging.info(f"  {k}: {v}", color="white")
                                else:
                                    logging.info(f"  {value.data}", color="white")
                            else:
                                logging.info(f"  {value}", color="white")
                            
                            # Print additional cache object attributes if they exist
                            if hasattr(value, 'last_updated'):
                                logging.info(f"Last Updated: {value.last_updated}", color="white")
                            if hasattr(value, 'version'):
                                logging.info(f"Version: {value.version}", color="white")
                            
                            logging.info("-" * 50, color="blue")
                            
                        except Exception as e:
                            logging.error(f"Error processing cache entry {key}: {str(e)}")
                            continue
                    
                    logging.info("Successfully retrieved peer data", color="green")
                    return formatted_data
                else:
                    logging.error("Invalid response format from server")
                    return None
            else:
                logging.error(f"Failed to retrieve peer data. Status code: {response.status_code}")
                return None
                
        except Exception as e:
            logging.error(f"Unexpected error retrieving peer data: {str(e)}")
            return None

    @staticmethod
    def update_peer_data(server_url: str, client_id: str, cache_data: dict):
        """
        Upload cache data to the server using the update_peer endpoint
        """
        try:
            formatted_data = {}
            for stream_id, cache_obj in cache_data.items():
                # Ensure consistent key format whether stream_id is dict or string
                key = dict_to_stream_key(stream_id)
                formatted_data[key] = cache_obj

            payload = {
                "peer_id": client_id,
                "cache_data": formatted_data
            }

            json_data = json.dumps(payload, cls=StreamIdEncoder)

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
                        # Retrieve the updated data to verify
                        retrieved_data = self.get_peer_data(self.server_url, self.client_id)
                        if retrieved_data:
                            logging.info("Successfully retrieved updated peer cache data", color="green")
                            self.cache_objects = retrieved_data  # Update local cache with retrieved data
                        else:
                            logging.warning("Failed to retrieve updated peer cache data", color="yellow")
                    else:
                        logging.warning("Failed to update peer cache data after checkin", color="yellow")
                
                # Return the original checkin response
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

    def get_peer_subscriptions(self, peer_id: str) -> list[str]:
        current_time = time.time()
        cached_data = self._peer_subscriptions_cache.get(peer_id)
        last_update = self._peer_subscriptions_timestamp.get(peer_id, 0)
        
        if cached_data and (current_time - last_update) < self.subscription_cache_ttl:
            return cached_data

        try:
            response = requests.get(f"{self.server_url}/peer_subscriptions", 
                                  params={"peer_id": peer_id})
            if response.status_code == 200:
                data = response.json()
                subscriptions = [dict_to_stream_key(sub) for sub in data.get("subscriptions", [])]
                self._peer_subscriptions_cache[peer_id] = subscriptions
                self._peer_subscriptions_timestamp[peer_id] = current_time
                return subscriptions
            return []
        except Exception as e:
            logging.error(f"Error retrieving subscriptions for peer {peer_id}: {str(e)}")
            return cached_data if cached_data else []


    def start_peer_check_loop(self, interval=15):
        """Start a loop to periodically check for new peers"""
        def check_peers():
            while self.running:
                self.connect_to_peers()
                time.sleep(interval)

        threading.Thread(target=check_peers, daemon=True).start()

    def send_cache_to_peer(self, peer_ip: str, cache_data: dict, peer_subscriptions: list[str]):
        """Send filtered cache data to a connected peer over TCP."""
        if not hasattr(self, '_last_send_times'):
            self._last_send_times = {}
        
        current_time = time.time()
        if current_time - self._last_send_times.get(peer_ip, 0) < 30:
            return False

        formatted_subscriptions = [dict_to_stream_key(sub) for sub in peer_subscriptions]
        filtered_cache = {
            key: value for key, value in cache_data.items()
            if dict_to_stream_key(stream_key_to_dict(key)) in formatted_subscriptions
        }
        
        if not filtered_cache:
            logging.info(f"No matching cache data for peer {peer_ip}. Subscriptions: {formatted_subscriptions}")
            return False

        PORT = 51821
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect((peer_ip, PORT))
            serialized_data = self._serialize_stream_data(filtered_cache)
            data_size = len(serialized_data)
            sock.sendall(struct.pack('!I', data_size))
            sock.sendall(serialized_data.encode())
            ack = sock.recv(2)
            if ack == b'OK':
                logging.info(f"Successfully sent filtered cache data to peer {peer_ip}", color="green")
                self._last_send_times[peer_ip] = current_time
                return True
            else:
                logging.error(f"Failed to get acknowledgment from peer {peer_ip}")
                return False

    def start_cache_server(self):
        def handle_client(client_socket, client_address):
            try:
                client_socket.settimeout(5)  # Add timeout
                size_data = client_socket.recv(4)
                if not size_data:
                    return
                
                data_size = struct.unpack('!I', size_data)[0]
                received_data = b''
                
                while len(received_data) < data_size:
                    chunk = client_socket.recv(min(4096, data_size - len(received_data)))
                    if not chunk:
                        break
                    received_data += chunk
                
                if len(received_data) == data_size:
                    received_cache = self._deserialize_stream_data(received_data.decode())
                    print("Received Cache Data:")
                    for key, value in received_cache.items():
                        print(f"Stream Key: {key}")
                        print(f"Cache Value: {value}")
                        print("-" * 50)
                    client_socket.sendall(b'OK')
                    logging.info(f"Received cache data from {client_address[0]}", color="green")
                    
            except socket.timeout:
                logging.warning(f"Connection timeout from {client_address[0]}")
            except ConnectionResetError:
                logging.warning(f"Connection reset by {client_address[0]}")
            except Exception as e:
                logging.error(f"Error handling client {client_address}: {str(e)}")
            finally:
                try:
                    client_socket.close()
                except:
                    pass

        def server_loop():
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.settimeout(1)  # Add timeout for accept()
            PORT = 51821
            
            try:
                server.bind(('0.0.0.0', PORT))
                server.listen(5)
                logging.info(f"Cache server listening on port {PORT}", color="green")
                
                while self.running:
                    try:
                        client_socket, client_address = server.accept()
                        threading.Thread(target=handle_client, 
                                    args=(client_socket, client_address),
                                    daemon=True).start()
                    except socket.timeout:
                        continue
                    except Exception as e:
                        if self.running:
                            logging.error(f"Accept error: {str(e)}")
                        time.sleep(1)
                        
            except Exception as e:
                logging.error(f"Server error: {str(e)}")
            finally:
                server.close()
        
        threading.Thread(target=server_loop, daemon=True).start()

    def start_ping_loop(self, interval=10):
        def ping_peers():
            while self.running:
                try:
                    peers = self.peerManager.list_peers()
                    if not peers:
                        logging.debug("No peers to ping", color="blue")
                        time.sleep(interval)
                        continue
                        
                    for peer in peers:
                        if not self.running:
                            break
                        peer_id = peer.get("public_key")
                        allowed_ips = peer.get('allowed_ips', '')
                        
                        if allowed_ips:
                            ping_ip = allowed_ips.split('/')[0]
                            peer_subscriptions = self.get_peer_subscriptions(peer_id)
                            self.run_ping_command(ping_ip, peer_subscriptions)
                            
                except Exception as e:
                    logging.error(f"Error in ping loop: {str(e)}", color="red")
                finally:
                    time.sleep(interval)

        threading.Thread(target=ping_peers, daemon=True, 
                        name="peer-ping-monitor").start()
        logging.info(f"Started ping monitoring with {interval}s interval", color="green")

    def run_ping_command(self, ip: str,peer_subscriptions):
        """Execute ping command to check peer connectivity and send cache data if successful"""
        # try:
        result = subprocess.run(["ping", "-c", "1", "-W", "2", ip], 
                            capture_output=True, text=True)
        if result.returncode == 0:
            logging.debug(f"Ping to {ip} successful", color="blue")
            # Get peer ID from IP address
            peer = next((p for p in self.peerManager.list_peers() if p.get('allowed_ips', '').split('/')[0] == ip), None)
            if peer and self.cache_objects:
                peer_id = peer.get("public_key")
                self.send_cache_to_peer(ip, self.cache_objects, peer_subscriptions)
            return
        subprocess.run(f"wg-quick down {self.interface}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)    
        subprocess.run(f"wg-quick up {self.interface}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        result = subprocess.run(["ping", "-c", "1", "-W", "2", ip], 
                            capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Ping to {ip} successful", color="blue")
            # Retry cache send after interface reset
            peer = next((p for p in self.peerManager.list_peers() if p.get('allowed_ips', '').split('/')[0] == ip), None)
            if peer and self.cache_objects:
                peer_id = peer.get("public_key")
                self.send_cache_to_peer(ip, self.cache_objects, peer_subscriptions)
            return
            
    # def stop(self):
    #     """Stop the PeerEngine and cleanup"""
    #     self.running = False
    #     if hasattr(self, 'background_thread'):
    #         self.background_thread.join(timeout=1)
    #     logging.info("PeerEngine stopped", color="green")
    def stop(self):
        """Stop the PeerEngine and cleanup all components"""
        # Signal all threads to stop
        self.running = False
        
        # Wait for background threads to finish
        if hasattr(self, 'background_thread'):
            self.background_thread.join(timeout=2)
        
        # Close all active socket connections
        try:
            # Create a socket to connect to our own server to trigger acceptance loop exit
            cleanup_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            cleanup_socket.connect(('127.0.0.1', 51821))
            cleanup_socket.close()
        except:
            pass
            
        # Clean up Wireguard interface
        try:
            subprocess.run(
                f"wg-quick down {self.interface}", 
                shell=True, 
                check=True,
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
        except Exception as e:
            logging.error(f"Error cleaning up Wireguard interface: {str(e)}")
        
        # Clear queues
        while not self.connection_queue.empty():
            try:
                self.connection_queue.get_nowait()
            except Empty:
                break
                
        # Clear caches
        self._peer_subscriptions_cache.clear()
        self._peer_subscriptions_timestamp.clear()
        if hasattr(self, '_last_send_times'):
            self._last_send_times.clear()
        
        logging.info("PeerEngine stopped", color="green")
