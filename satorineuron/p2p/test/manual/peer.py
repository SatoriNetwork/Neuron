from satorineuron.p2p.peer_manager import PeerManager
from typing import List, Dict

# Get the PeerManager instance
peer_engine = PeerManager()

# Start the peer engine
peer_engine.start()

# Add a peer (replace with actual values)
# peer_engine.remove_peer_peer("8gIspO1tyen6T7rf1bITrnBEGKvB9gf06JP+NXbt0FA=")


def add_peer(public_key: str, allowed_ips: str, endpoint: str = None):
    peer_engine.add_peer(public_key, allowed_ips, endpoint)


def remove_peer(public_key: str):
    peer_engine.remove_peer(public_key)


def list_peers() -> List[Dict[str, str]]:
    return peer_engine.list_peers()


def start_listening():
    peer_engine.start_listening()


def stop_listening():
    peer_engine.stop_listening()


def start_connection(target_ip: str):
    peer_engine.start_connection(target_ip)


def stop_connection():
    peer_engine.stop_connection()


def get_peer_connection_status() -> Dict[str, bool]:
    return peer_engine.get_connection_status()


# List peers
peers = peer_engine.list_peers()
print("Current peers:", peers)

# You can add more operations here
# When done, stop the peer engine
peer_engine.stop()
