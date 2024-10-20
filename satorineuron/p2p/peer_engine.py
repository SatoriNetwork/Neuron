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

PeerEngine (singleton)
    connects to the server, asking for peers, and then manages their connections
    - PeerManager (regular class)
    - PeerServerClient (regular class)
    - wait for updates: (thread listening to a Queue)
        - listen for what other connections the rest of the neuron wants to
            - make
            - break

Next Steps:
    - fix the PeerServer to work according to diagram
        - share wireguard connection details with clients
    - fix the PeerServerClient to work according to diagram
        - checkin with server (providing own details)
        - able to ask server to connect to a peer
        - heartbeat to tell server we're still around (10 minutes)
    - refactor whatever is needed and complete this PeerEngine
'''

import json
import threading
import time
from queue import Queue
from typing import List, Dict
from satorineuron import logging
# from satorilib.api.interfaces.p2p import P2PInterface
from satorineuron.p2p.peer_manager import PeerManager
# from satorineuron.p2p.peer_client import PeerServerClient
from satorineuron.p2p.wireguard_manager import (
    add_peer,
    remove_peer,
    list_peers,
    start_wireguard_service,
    start_port_listening,
    stop_port_listening,
    start_port_connection,
    stop_port_connection
)


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
        self.connectTo = Queue()  # start.peerEngine.connectTo.put('some peer')
        # PeerManager()
        # PeerServerClient()

    def start(self):
        # starts both PeerManager and PeerServerClient
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
