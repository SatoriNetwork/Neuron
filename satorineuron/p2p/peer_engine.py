'''
have:
start.py -> starts the PeerEngine -> config -> maintains connections -> waits for updates

want:
start.py ->
starts the PeerEngine ->
makes a connection to peerserver ->
gets peers, merges with config ->
connects to peers ->
maintains connections ->
waits for updates

Next step:complete
# PeerEngine (singleton)
#     connects to the server, asking for peers, and then manages their connections
#     - PeerManager (regular class)
#     - PeerServerClient (regular class)
#     - wait for updates: (thread listening to a Queue)
#         - listen for what other connections the rest of the neuron wants to
#             - make
#             - break

# Next Steps:complete
#     - fix the PeerServer to work according to diagram
#         - share wireguard connection details with clients
#     - fix the PeerServerClient to work according to diagram
#         - checkin with server (providing own details)
#         - able to ask server to connect to a peer
#         - heartbeat to tell server we're still around (10 minutes)
#     - refactor whatever is needed and complete this PeerEngine

Next step:
peerEngine
    send a ping message to the peer which is connected to the neuron
    receive a message back and show it as logs
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
from satorineuron.p2p.peer_client import MessageClient
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
        self.client_id="client 1"
        self.server_url="http://188.166.4.120:51820"
        self.connectTo = Queue()  # start.peerEngine.connectTo.put('some peer')
        # PeerManager()
        self.peerManager = PeerManager(self.interface,self.config_file,self.port)
        # PeerServerClient()

    def start(self):
        # starts both PeerManager and PeerServerClient
        logging.info('PeerEngine started', color='green')
        self.peerManager.start()
        self.start_background_tasks()
        self.get_peers()
        self.start_listening()
        self.start_ping_loop()
        # pass

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
            # print(requestedPeerConnection)
            # something like this:
            # result = self.PeerServerClient.requestConnect(requestedPeerConnection)
            # self.PeerManager.addPeer(result)

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
                return other_peers
            else:
                raise Exception(f"Failed to get peers: {response.status_code}")
            
        except Exception as e:
            print(f"Error getting peers: {str(e)}")
            return []

    def checkin(self):
        """Perform check-in with server, also serves as heartbeat"""
        wg_info = self.my_info.get_wireguard_info()
        self.wireguard_config["wireguard_config"]=wg_info
        try:
            response = requests.post(
                f"{self.server_url}/checkin",
                json={
                    "peer_id": self.client_id,
                    "wireguard_config": self.wireguard_config["wireguard_config"]
                }
            )
            return response.json()
        except Exception as e:
            print(f"Checkin failed: {e}")
            return None
        
    def start_background_tasks(self):
        """Start background checkin task"""
        self.running = True

        def background_loop():
            while self.running:
                self.checkin()
                time.sleep(60*10)

        self.background_thread = threading.Thread(target=background_loop)
        self.background_thread.daemon = True
        self.background_thread.start()

    def start_ping_loop(self, interval=5):
        def ping_peers():
            while True:
                time.sleep(interval)
                for  peer in self.peerManager.list_peers():
                    # print(peer)
                    peer_id = "client 2"
                    ping_ip = peer.get('allowed_ips', '').split('/')[0]
                    try:
                        self.run_ping_command(ping_ip)
                    except Exception as e:
                        logging.error(f"Failed to ping peer {peer_id}: {e}")
                # time.sleep(interval)
        
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
