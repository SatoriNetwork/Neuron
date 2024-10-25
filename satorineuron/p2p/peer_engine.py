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

Next step:
PeerEngine (singleton)
    connects to the server, asking for peers, and then manages their connections
    - PeerManager (regular class)
    - PeerServerClient (regular class)
    - wait for updates: (thread listening to a Queue)
        - listen for what other connections the rest of the neuron wants to
            - make
            - break

# Next Steps:complete
#     - fix the PeerServer to work according to diagram
#         - share wireguard connection details with clients
#     - fix the PeerServerClient to work according to diagram
#         - checkin with server (providing own details)
#         - able to ask server to connect to a peer
#         - heartbeat to tell server we're still around (10 minutes)
#     - refactor whatever is needed and complete this PeerEngine
'''

import json
import threading
import time
import requests
from queue import Queue
from typing import List, Dict
from satorineuron import logging
from satorineuron.p2p.peer_manager import PeerManager
from satorineuron.p2p.peer_client import MessageClient
from satorineuron.p2p.my_conf import WireguardInfo
# from satorineuron.p2p.wireguard_manager import (
#     add_peer,
#     remove_peer,
#     list_peers,
#     start_wireguard_service,
#     start_port_listening,
#     stop_port_listening,
#     start_port_connection,
#     stop_port_connection
# )


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
        self.peerManager.start()
        self.checkin()
        self.get_peers()
        pass

    def start_listening(self):
        '''
        wireguard automatically connects to peers when they are added to the
        config file
        '''
        while True:
            requestedPeerConnection = self.connectTo.get()
            # something like this:
            # result = self.PeerServerClient.requestConnect(requestedPeerConnection)
            # self.PeerManager.addPeer(result)

    def get_peers(self):
        """Get list of all peers from the server"""
        try:
            response = requests.get(f"{self.server_url}/list_peers")
            if response.status_code == 200:
                print(response.json()['peers'])
                return response.json()['peers']
                
            else:
                raise Exception(f"Failed to get peers: {response.status_code}")
            
        except Exception as e:
            print(f"Error getting peers: {str(e)}")
            return []

    def checkin(self):
        """Perform check-in with server, also serves as heartbeat"""
        wg_info = self.my_info.get_wireguard_info()
        # print(wg_info)
        self.wireguard_config["wireguard_config"]=wg_info
        # print(self.wireguard_config)
        try:
            response = requests.post(
                f"{self.server_url}/checkin",
                json={
                    "peer_id": self.client_id,
                    "wireguard_config": self.wireguard_config
                }
            )
            return response.json()
        except Exception as e:
            print(f"Checkin failed: {e}")
            return None
