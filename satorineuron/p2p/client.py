import requests
import time
import threading
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, Set, List
import datetime

@dataclass
class MessageStats:
    """Track message statistics for a peer"""
    messages: List[float] = None  # List of message timestamps
    total_messages: int = 0
    last_warning_time: float = 0
    
    def __post_init__(self):
        self.messages = []

class RateLimitConfig:
    """Configuration for rate limiting"""
    def __init__(self,
                 window_size: int = 60,  # Time window in seconds
                 message_limit: int = 10,  # Max messages per window
                 warning_threshold: float = 0.7,  # Percentage of limit that triggers warning
                 warning_cooldown: int = 300):  # Cooldown period for warnings in seconds
        self.window_size = window_size
        self.message_limit = message_limit
        self.warning_threshold = warning_threshold
        self.warning_cooldown = warning_cooldown

class MessageClient:
    def __init__(self, server_url, client_id):
        self.server_url = server_url.rstrip('/')
        self.client_id = client_id
        self.running = False
        self.connected_peers = set()
        
        # Rate limiting setup
        self.rate_limit_config = RateLimitConfig()
        self.peer_stats: Dict[str, MessageStats] = defaultdict(MessageStats)
        
        # Message history
        self.message_history: List[dict] = []
        self.max_history = 100  # Keep last 100 messages
        
        # Threading lock for thread-safe operations
        self.lock = threading.Lock()

    def update_message_stats(self, peer_id: str, timestamp: float) -> bool:
        """
        Update message statistics for a peer and check if rate limit is exceeded
        Returns: True if peer should be disconnected
        """
        with self.lock:
            stats = self.peer_stats[peer_id]
            current_time = time.time()
            
            # Add new message timestamp
            stats.messages.append(timestamp)
            stats.total_messages += 1
            
            # Remove messages outside the window
            window_start = current_time - self.rate_limit_config.window_size
            stats.messages = [t for t in stats.messages if t > window_start]
            
            # Count messages in current window
            messages_in_window = len(stats.messages)
            
            # Check warning threshold
            warning_limit = self.rate_limit_config.message_limit * self.rate_limit_config.warning_threshold
            if (messages_in_window >= warning_limit and 
                current_time - stats.last_warning_time > self.rate_limit_config.warning_cooldown):
                stats.last_warning_time = current_time
                print(f"\nWARNING: Peer {peer_id} is sending messages at {messages_in_window}/{self.rate_limit_config.message_limit} of rate limit")
            
            # Check if rate limit exceeded
            return messages_in_window > self.rate_limit_config.message_limit

    def add_to_message_history(self, message: dict):
        """Add message to history with timestamp"""
        with self.lock:
            self.message_history.append({
                **message,
                'received_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            if len(self.message_history) > self.max_history:
                self.message_history.pop(0)

    def show_message_history(self, peer_id=None):
        """Display message history, optionally filtered by peer"""
        with self.lock:
            print("\nMessage History:")
            for msg in self.message_history:
                if peer_id is None or msg['from'] == peer_id:
                    print(f"[{msg['received_at']}] From {msg['from']}: {msg['message']}")

    def get_peer_stats(self, peer_id=None):
        """Get messaging statistics for one or all peers"""
        with self.lock:
            if peer_id:
                if peer_id in self.peer_stats:
                    stats = self.peer_stats[peer_id]
                    return {
                        'peer_id': peer_id,
                        'total_messages': stats.total_messages,
                        'messages_in_window': len(stats.messages),
                        'rate_limit': self.rate_limit_config.message_limit
                    }
                return None
            else:
                return {
                    peer: {
                        'total_messages': stats.total_messages,
                        'messages_in_window': len(stats.messages),
                        'rate_limit': self.rate_limit_config.message_limit
                    }
                    for peer, stats in self.peer_stats.items()
                }

    def checkin(self):
        try:
            response = requests.post(
                f"{self.server_url}/checkin",
                json={"peer_id": self.client_id},
                headers={"Content-Type": "application/json"}
            )
            return response.json()
        except Exception as e:
            print(f"Checkin failed: {e}")
            return None

    def connect_to_peer(self, peer_id):
        try:
            response = requests.post(
                f"{self.server_url}/connect",
                json={
                    "from_peer": self.client_id,
                    "to_peer": peer_id
                },
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                with self.lock:
                    self.connected_peers.add(peer_id)
                    # Reset stats for new connection
                    self.peer_stats[peer_id] = MessageStats()
                return response.json()
            return None
        except Exception as e:
            print(f"Connection failed: {e}")
            return None

    def disconnect_from_peer(self, peer_id):
        try:
            response = requests.post(
                f"{self.server_url}/disconnect",
                json={
                    "from_peer": self.client_id,
                    "to_peer": peer_id
                },
                headers={"Content-Type": "application/json"}
            )
            if response.status_code == 200:
                with self.lock:
                    self.connected_peers.discard(peer_id)
            return response.json()
        except Exception as e:
            print(f"Disconnection failed: {e}")
            return None

    def send_message(self, to_peer, message):
        if to_peer not in self.connected_peers:
            print(f"Error: Not connected to peer {to_peer}")
            return None
            
        try:
            response = requests.post(
                f"{self.server_url}/send_message",
                json={
                    "from_peer": self.client_id,
                    "to_peer": to_peer,
                    "message": message
                },
                headers={"Content-Type": "application/json"}
            )
            return response.json()
        except Exception as e:
            print(f"Failed to send message: {e}")
            return None

    def receive_messages(self):
        try:
            response = requests.post(
                f"{self.server_url}/receive_messages",
                json={"peer_id": self.client_id},
                headers={"Content-Type": "application/json"}
            )
            data = response.json()
            
            if data and data.get('messages'):
                for msg in data['messages']:
                    peer_id = msg['from']
                    timestamp = msg['timestamp']
                    
                    # Add message to history
                    self.add_to_message_history(msg)
                    
                    # Check rate limiting
                    if self.update_message_stats(peer_id, timestamp):
                        print(f"\nRate limit exceeded for peer {peer_id}. Disconnecting...")
                        self.disconnect_from_peer(peer_id)
                        print(f"Disconnected from peer {peer_id} due to rate limiting")
            
            return data
        except Exception as e:
            print(f"Failed to receive messages: {e}")
            return None

    def list_peers(self):
        try:
            response = requests.get(f"{self.server_url}/peers")
            return response.json()
        except Exception as e:
            print(f"Failed to list peers: {e}")
            return None

    def start_background_tasks(self):
        self.running = True
        
        def background_loop():
            while self.running:
                self.checkin()
                messages = self.receive_messages()
                time.sleep(5)
        
        self.background_thread = threading.Thread(target=background_loop)
        self.background_thread.daemon = True
        self.background_thread.start()

    def stop(self):
        self.running = False
        if hasattr(self, 'background_thread'):
            self.background_thread.join()

if __name__ == "__main__":
    SERVER_URL = "http://188.166.4.120:51820"
    CLIENT_ID = input("Enter your client ID: ")
    
    client = MessageClient(SERVER_URL, CLIENT_ID)
    client.start_background_tasks()
    
    print(f"Client started with ID: {CLIENT_ID}")
    print("Rate limit configuration:")
    print(f"- Maximum {client.rate_limit_config.message_limit} messages per {client.rate_limit_config.window_size} seconds")
    print(f"- Warning at {client.rate_limit_config.warning_threshold * 100}% of limit")
    
    try:
        while True:
            print("\n1. List all peers")
            print("2. Connect to peer")
            print("3. Disconnect from peer")
            print("4. Send a message")
            print("5. Show connected peers")
            print("6. Show message history")
            print("7. Show peer statistics")
            print("8. Exit")
            choice = input("Choose an option: ")
            
            if choice == "1":
                peers = client.list_peers()
                print("\nActive peers:")
                for peer_id, last_seen in peers.items():
                    if peer_id != CLIENT_ID:
                        print(f"Peer ID: {peer_id}, Last seen: {time.ctime(last_seen)}")
            
            elif choice == "2":
                peer_id = input("Enter peer ID to connect to: ")
                result = client.connect_to_peer(peer_id)
                if result:
                    print(f"Successfully connected to {peer_id}")
                else:
                    print("Connection failed")
            
            elif choice == "3":
                peer_id = input("Enter peer ID to disconnect from: ")
                result = client.disconnect_from_peer(peer_id)
                if result:
                    print(f"Successfully disconnected from {peer_id}")
            
            elif choice == "4":
                if not client.connected_peers:
                    print("No connected peers. Please connect to a peer first.")
                    continue
                    
                print("\nConnected peers:", list(client.connected_peers))
                peer_id = input("Enter peer ID to send message to: ")
                if peer_id not in client.connected_peers:
                    print("Not connected to this peer. Please connect first.")
                    continue
                    
                message = input("Enter your message: ")
                result = client.send_message(peer_id, message)
                if result:
                    print("Message sent successfully!")
            
            elif choice == "5":
                print("\nConnected peers:", list(client.connected_peers))
            
            elif choice == "6":
                peer_id = input("Enter peer ID to filter (or press Enter for all): ").strip()
                client.show_message_history(peer_id if peer_id else None)
            
            elif choice == "7":
                peer_id = input("Enter peer ID to check (or press Enter for all): ").strip()
                stats = client.get_peer_stats(peer_id if peer_id else None)
                print("\nPeer Statistics:")
                if peer_id and stats:
                    print(f"\nPeer {stats['peer_id']}:")
                    print(f"- Total messages: {stats['total_messages']}")
                    print(f"- Messages in current window: {stats['messages_in_window']}/{stats['rate_limit']}")
                elif peer_id and not stats:
                    print(f"No statistics available for peer {peer_id}")
                else:
                    for peer, peer_stats in stats.items():
                        print(f"\nPeer {peer}:")
                        print(f"- Total messages: {peer_stats['total_messages']}")
                        print(f"- Messages in current window: {peer_stats['messages_in_window']}/{peer_stats['rate_limit']}")

            elif choice == "8":
                break
                
    finally:
        client.stop()