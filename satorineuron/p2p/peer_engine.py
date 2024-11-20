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
        self.ping_interval = 10
        self.history = {}  # New attribute to store historical data for streams

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
        # self.start_ping_loop()
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
                peer_endpoint = peer['wireguard_config'].get('endpoint')
                
                if not peer_endpoint:
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
                        # break
                        # Fetch and store history for the subscription
                        history_data = self.request_history(peer_endpoint, sub)
                        if history_data:
                            self.history.setdefault("subscriptions", {})[sub] = history_data


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
                # if should_connect:
                    # Request historical data
                    for sub in self.subscriptions:
                        if sub in peer.get('publications', []):
                            self.request_history(peer_endpoint, sub)
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
            new_endpoint = new_config.get('endpoint')
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

    # def checkin(self):
    #     """Perform check-in with server, including datastream information"""
    #     wg_info = self.my_info.get_wireguard_info()
    #     self.wireguard_config["wireguard_config"] = wg_info
    #     try:
    #         response = requests.post(
    #             f"{self.server_url}/checkin",
    #             json={
    #                 "peer_id": self.client_id,
    #                 "wireguard_config": self.wireguard_config["wireguard_config"],
    #                 "publications": self.publications,
    #                 "subscriptions": self.subscriptions
    #             }
    #         )
    #         # return response.json()
            
    #     # except Exception as e:
    #     #     logging.error(f"Checkin failed: {str(e)}")
    #     #     return None
            
    #         if response.status_code == 200:
    #             checkin_data = response.json()
    #             logging.debug(f"Checkin response: {checkin_data}")
                
    #             publications = checkin_data.get("publications", [])
    #             subscriptions = checkin_data.get("subscriptions", [])
                
    #             for publication in publications:
    #                 stream = publication.get("stream")
    #                 if stream:
    #                     self._update_history([{"stream": stream}], "publications")
    #                     self.get_history("publications", stream)
                
    #             for subscription in subscriptions:
    #                 stream = subscription.get("stream")
    #                 if stream:
    #                     self._update_history([{"stream": stream}], "subscriptions")
    #                     self.get_history("subscriptions", stream)
                        
    #             return checkin_data
    #         else:
    #             logging.error(f"Checkin failed with status code {response.status_code}")
    #             return None
    #     except requests.exceptions.RequestException as e:
    #         logging.error(f"Network error during checkin: {str(e)}")
    #         return None
    #     except Exception as e:
    #         logging.error(f"Unexpected error during checkin: {str(e)}")
    #         return None
    def checkin(self):
        """Perform check-in with server, including datastream information"""
        try:
            wg_info = self.my_info.get_wireguard_info()
            if not isinstance(wg_info, dict):
                logging.error(f"Invalid WireGuard info format: expected dict, got {type(wg_info)}")
                return None

            payload = {
                "peer_id": self.client_id,
                "wireguard_config": wg_info,
                "publications": self.publications,
                "subscriptions": self.subscriptions
            }
            
            response = requests.post(
                f"{self.server_url}/checkin",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                try:
                    checkin_data = response.json()
                    logging.debug(f"Checkin response: {checkin_data}")
                    
                    # Only process publications and subscriptions if they exist in the response
                    if isinstance(checkin_data, dict):
                        publications = checkin_data.get("publications", [])
                        subscriptions = checkin_data.get("subscriptions", [])
                        
                        if isinstance(publications, list):
                            for publication in publications:
                                if isinstance(publication, dict):
                                    stream = publication.get("stream")
                                    if stream:
                                        self._update_history([{"stream": stream}], "publications")
                                        self.get_history("publications", stream)
                        
                        if isinstance(subscriptions, list):
                            for subscription in subscriptions:
                                if isinstance(subscription, dict):
                                    stream = subscription.get("stream")
                                    if stream:
                                        self._update_history([{"stream": stream}], "subscriptions")
                                        self.get_history("subscriptions", stream)
                        
                        return checkin_data
                    else:
                        logging.error(f"Invalid checkin response format: expected dict, got {type(checkin_data)}")
                        return None
                        
                except json.JSONDecodeError as e:
                    logging.error(f"Failed to parse checkin response: {str(e)}")
                    return None
            else:
                logging.error(f"Checkin failed with status code {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Network error during checkin: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Unexpected error during checkin: {str(e)}")
            return None

        
    def _update_history(self, streams: list, stream_type: str):
        if not isinstance(streams, list):
            logging.error(f"Invalid streams format for {stream_type}: expected list, got {type(streams)}")
            return
            
        for stream_data in streams:
            if not isinstance(stream_data, dict):
                logging.error(f"Invalid stream format: expected dict, got {type(stream_data)}")
                continue
                
            stream_id = stream_data.get("stream")
            peer_endpoint = stream_data.get("endpoint")
            
            if not stream_id:
                logging.error("Missing stream ID in stream data")
                continue
                
            if peer_endpoint:
                history_data = self.request_history(peer_endpoint, stream_id)
                if history_data:
                    if stream_type not in self.history:
                        self.history[stream_type] = {}
                    self.history[stream_type][stream_id] = history_data
                    logging.info(f"Updated history for {stream_type} stream {stream_id}")


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

    def request_history(self, peer_endpoint: str, stream_id: str):
        """Request historical data for a specific stream from a peer."""
        try:
            url = f"http://{peer_endpoint}/get_history"
            payload = {
                "stream_id": stream_id,
                "kwargs": {"limit": 1000}  # Example of additional parameters
            }
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                history = response.json()
                logging.info(f"Received history for stream {stream_id} from {peer_endpoint}")
                return history
            else:
                logging.warning(f"Failed to fetch history from {peer_endpoint}: {response.status_code}")
                return None
        except Exception as e:
            logging.error(f"Error requesting history from {peer_endpoint}: {str(e)}")
            return None

    def get_history(self, stream_type: str, stream_id: str):
        """Retrieve historical data for a specific stream."""
        print(self.history.get(stream_type, {}).get(stream_id, None))
        return self.history.get(stream_type, {}).get(stream_id, None)
            
    def stop(self):
        """Stop the PeerEngine and cleanup"""
        self.running = False
        if hasattr(self, 'background_thread'):
            self.background_thread.join(timeout=1)
        logging.info("PeerEngine stopped", color="green")
