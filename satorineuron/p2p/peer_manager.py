import json
import threading
import time
from typing import List, Dict
from satorineuron import logging
# from satorilib.api.interfaces.p2p import P2PInterface
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


class PeerManager():
    ''' keeps track of peers and manages connections '''

    def __init__(self, interface="wg0", config_file="peers.json", port=51820):
        self.interface = interface
        self.config_file = config_file
        self.port = port
        self.peers = self.load_peers()
        self.active_connections: Dict[str, bool] = {}
        self.connection_lock = threading.Lock()
        self.is_running = False
        self.connection_thread = None
        self.listening = False
        self.connecting = False

    def start(self,unique_ip):
        if not self.is_running:
            self.is_running = True
            logging.info(start_wireguard_service(
                self.interface,unique_ip), color='green')
            self.connection_thread = threading.Thread(
                target=self._maintain_connections)
            self.connection_thread.daemon = True
            self.connection_thread.start()
            logging.info('PeerManager started', color='green')

    def stop(self):
        self.is_running = False
        if self.connection_thread:
            self.connection_thread.join()
        self._disconnect_all_peers()
        logging.info('PeerManager stopped', color='yellow')

    def load_peers(self):
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_peers(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.peers, f, indent=2)

    def add_peer(self, public_key: str, allowed_ips: str, endpoint: str = None):
        new_peer = {
            "public_key": public_key,
            "allowed_ips": allowed_ips,
            "endpoint": endpoint
        }
        self.peers.append(new_peer)
        logging.info(add_peer(self.interface, public_key,
                     allowed_ips, endpoint), color='cyan')
        self.save_peers()
        with self.connection_lock:
            self.active_connections[public_key] = False

    def remove_peer(self, public_key: str):
        self.peers = [
            peer for peer in self.peers if peer['public_key'] != public_key]
        logging.info(remove_peer(self.interface, public_key), color='cyan')
        self.save_peers()
        with self.connection_lock:
            if public_key in self.active_connections:
                del self.active_connections[public_key]

    def list_peers(self) -> List[Dict[str, str]]:
        return list_peers(self.interface)

    def _maintain_connections(self):
        '''
        wireguard automatically connects to peers when they are added to the
        config file
        '''
        while self.is_running:
            current_peers = self.list_peers()
            with self.connection_lock:
                for peer in current_peers:
                    self.active_connections[peer['public_key']] = True
                for public_key in list(self.active_connections.keys()):
                    if public_key not in [p['public_key'] for p in current_peers]:
                        self.active_connections[public_key] = False
            time.sleep(60)  # Check connections every minute

    def _disconnect_all_peers(self):
        for peer in self.peers:
            try:
                remove_peer(self.interface, peer['public_key'])
                logging.info(
                    f"Disconnected from peer: {peer['public_key']}", color='yellow')
            except Exception as e:
                logging.warning(
                    f"Error disconnecting from peer {peer['public_key']}: {str(e)}", color='red')

    def start_listening(self):
        if not self.listening:
            self.listening = True
            logging.info(
                f"Starting port listening on {self.port}", color='green')
            try:
                start_port_listening(self.port)
            except KeyboardInterrupt:
                logging.info("Stopping listener...", color='yellow')
            finally:
                self.stop_listening()
                logging.info("Listener stopped.", color='yellow')

    def stop_listening(self):
        if self.listening:
            self.listening = False
            stop_port_listening()

    def start_connection(self, target_ip: str):
        if not self.connecting:
            self.connecting = True
            logging.info(
                f"Connecting to {target_ip}:{self.port}", color='green')
            try:
                start_port_connection(target_ip, self.port)
            except KeyboardInterrupt:
                logging.info("Stopping connection...", color='yellow')
            finally:
                self.stop_connection()
                logging.info("Connection stopped.", color='yellow')

    def stop_connection(self):
        if self.connecting:
            self.connecting = False
            stop_port_connection()

    def get_connection_status(self) -> Dict[str, bool]:
        return dict(self.active_connections)
