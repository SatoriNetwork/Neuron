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
from queue import Queue , Empty
from typing import List, Dict
from satorineuron import logging
from satorineuron.p2p.peer_manager import PeerManager
# from satorineuron.p2p.peer_client import MessageClient
from satorineuron.p2p.my_conf import WireguardInfo
from satorineuron.p2p.wireguard_manager import save_config


class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(
                SingletonMeta, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class PeerEngine(metaclass=SingletonMeta):
    ''' connects to server and manages peers '''

    def __init__(self, interface="wg0", config_file="peers.json", port=51820):
        # create these:
        self.interface = interface
        self.config_file=config_file
        self.port=port
        self.my_info = WireguardInfo()
        self.wireguard_config= {}
        self.client_id=''
        self.server_url="http://188.166.4.120:51820"
        self.ip_address = self._get_unique_ip()
        self.connectTo = Queue() 
        self.peerManager = PeerManager(self.interface,self.config_file,self.port)
        self.publications = []
        self.subscriptions = []

    def _get_unique_ip(self):
        """Get a unique IP address from the PeerServer"""
        response = requests.get(f"{self.server_url}/get_unique_ip")
        if response.status_code == 200:
            return response.json()["ip_address"]
        else:
            raise Exception(f"Failed to get unique IP address: {response.status_code}")

    def start(self):
        # starts both PeerManager and PeerServerClient
        logging.info('PeerEngine started', color='green')  
        self.peerManager.start(self._get_unique_ip())
        wg_info = self.my_info.get_wireguard_info()
        self.client_id=wg_info['public_key']
        self.start_background_tasks()
        # self.start_listening()
        # self.start_ping_loop()

    def start_listening(self):
        '''
        wireguard automatically connects to peers when they are added to the
        config file
        '''
        while True:
            try: 
                requestedPeerConnection = self.connectTo.get(block=False)
                self.peerManager.add_peer( 
                            requestedPeerConnection["wireguard_config"]['public_key'], 
                            requestedPeerConnection["wireguard_config"]['allowed_ips'], 
                            requestedPeerConnection["wireguard_config"]['endpoint'])
                save_config(self.interface)
            except Empty:
                break  # Exit the loop when queue is empty

    def get_peers(self):
        """Get list of all peers from the server"""
        try:
            response = requests.get(f"{self.server_url}/list_peers")
            if response.status_code == 200:
                all_peers = response.json()['peers']
                other_peers = [peer for peer in all_peers if peer['peer_id'] != self.client_id]
                # return other_peers
                for peer in other_peers:
                        peer_data = {
                            'id': peer['peer_id'],
                            'wireguard_config': peer['wireguard_config']
                        }
                        self.connectTo.put(peer_data)
                        # self.connect_to_peer(peer_data['id'])
                return other_peers
            else:
                raise Exception(f"Failed to get peers: {response.status_code}")
            
        except Exception as e:
            print(f"Error getting peers: {str(e)}")
            return []

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
            print(f"Checkin failed: {e}")
            return None

    def request_datastream(self, stream_name):
        """Request connection to peers for a specific datastream"""
        try:
            response = requests.post(
                f"{self.server_url}/connect_datastream",
                json={
                    "peer_id": self.client_id,
                    "stream": stream_name
                }
            )
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "connected":
                    peer_data = {
                        'id': data['to_peer'],
                        'wireguard_config': data['to_peer_config']
                    }
                    self.connectTo.put(peer_data)
                return data
            else:
                raise Exception(f"Failed to request datastream: {response.status_code}")
        except Exception as e:
            print(f"Datastream request failed: {e}")
            return None

    def add_publication(self, stream_name):
        """Add a publication stream"""
        if stream_name not in self.publications:
            self.publications.append(stream_name)
            self.checkin()  # Update server with new publication

    def add_subscription(self, stream_name):
        """Add a subscription stream"""
        if stream_name not in self.subscriptions:
            self.subscriptions.append(stream_name)
            self.checkin()  # Update server with new subscription
            self.request_datastream(stream_name)  # Request connection to relevant peers

    def start_background_tasks(self):
        """Start background checkin task"""
        self.running = True

        def background_loop():
            while self.running:
                self.checkin()
                self.get_peers()
                time.sleep(60*30)

        self.background_thread = threading.Thread(target=background_loop)
        self.background_thread.daemon = True
        self.background_thread.start()

    def start_ping_loop(self, interval=5):
        def ping_peers():
            while True:
                time.sleep(interval)
                for  peer in self.peerManager.list_peers():
                    peer_id = peer.get("public_key")
                    ping_ip = peer.get('allowed_ips', '').split('/')[0]
                    try:
                        self.run_ping_command(ping_ip)
                    except Exception as e:
                        logging.error(f"Failed to ping peer {peer_id}: {e}")
        
        # Start pinging in a separate thread to avoid blocking other operations
        threading.Thread(target=ping_peers, daemon=True).start()

    def run_ping_command(self, ip):
        # Run the system ping command
        result = subprocess.run(["ping", "-c", "1", ip], capture_output=True, text=True)
        # print(result)
        if result.returncode == 0:
            logging.info(f"Ping to {ip} successful: {result.stdout}", color="blue")
        else:
            logging.error(f"Ping to {ip} failed: {result.stderr}", color="blue")

    def connect_to_peer(self, peer_id):
        """Request connection to another peer and configure WireGuard."""
        url = f"{self.server_url}/connect"
        data = {
            "from_peer": self.client_id,
            "to_peer": peer_id
        }

        try:
            response = requests.post(url, json=data)
            response_data = response.json()
            if response_data.get('status') == 'connected':
                print(f"Successfully connected to {peer_id}")
                return True
             
            else:
                print(f"Connection failed: {response_data.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
