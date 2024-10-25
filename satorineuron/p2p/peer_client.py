import requests
import time
import threading
import json
from dataclasses import dataclass
from satorineuron.p2p.wireguard_manager import start_wireguard_service, add_peer, save_config, list_peers, start_port_listening, start_port_connection, stop_port_listening

@dataclass
class WireguardConfig:
    public_key: str
    endpoint: str
    allowed_ips: str

class MessageClient:
    def __init__(self, server_url, client_id, wireguard_config):
        self.server_url = server_url.rstrip('/')
        self.client_id = client_id
        self.wireguard_config = wireguard_config
        self.running = False
        self.connected_peers = set()
        self.listening = False
        self.peer_wireguard_configs = {}
        self.ensure_wireguard_running()
    
    def ensure_wireguard_running(self):
        interface = "wg0"  # or whatever interface name you're using
        result = start_wireguard_service(interface)
        print(result)

    def checkin(self):
        """Perform check-in with server, also serves as heartbeat"""
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
                self.connected_peers.add(peer_id)

                to_peer_config = response_data['to_peer_config']
                print(f"WireGuard config for peer {peer_id}: {to_peer_config}")
                
                # Store the peer's WireGuard config
                self.peer_wireguard_configs[peer_id] = to_peer_config
                
                # Apply WireGuard configuration
                interface = "wg0"
                add_peer(interface, 
                        to_peer_config['public_key'], 
                        to_peer_config['allowed_ips'], 
                        to_peer_config['endpoint'])
                save_config(interface)
                print(f"Peer {peer_id} configuration saved and applied")
                return True
             
            else:
                print(f"Connection failed: {response_data.get('message', 'Unknown error')}")
                return False
                
        except Exception as e:
            print(f"Connection failed: {e}")
            return False

    def start_listening(self):
        """Start port listening mode"""
        if not self.listening:
            self.listening = True
            port =51821
            print(f"\nStarting port listening on {port}")
            print("Press Ctrl+C to stop listening and return to menu...")
            print("-" * 50)

            try:
                start_port_listening(port)
            except KeyboardInterrupt:
                print("\nStopping listener...")
            finally:
                self.stop_listening()
                print("\nListener stopped. Returning to menu...")
                time.sleep(1)

    def stop_listening(self):
        """Stop port listening"""
        if self.listening:
            self.listening = False
            stop_port_listening()
    

    def test_connection(self, peer_id):
        """Test WireGuard connection with peer"""
        try:
            config = self.peer_wireguard_configs.get(peer_id)
            if not config:
                return False
            
            # Test the connection using port communication
            port = 51821
            allowed_ip=config['allowed_ips'].split('/')[0]
            start_port_connection(allowed_ip,port)
            time.sleep(1)  # Give time for listener to start
            return True
            
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
        
    def list_peers(self):
        """Get list of all peers and their last seen timestamps"""
        try:
            return self.get_peers()
        except Exception as e:
            print(f"Error listing peers: {str(e)}")
            return None
        
    def get_peers(self):
        """Get list of all peers from the server"""
        try:
            response = requests.get(f"{self.server_url}/list_peers")
            if response.status_code == 200:
                return response.json()['peers']
            else:
                raise Exception(f"Failed to get peers: {response.status_code}")
        except Exception as e:
            print(f"Error getting peers: {str(e)}")
            return []
        
    def start_background_tasks(self):
        """Start background checkin task"""
        self.running = True

        def background_loop():
            while self.running:
                self.checkin()
                time.sleep(600)  # 10 minute interval for heartbeat

        self.background_thread = threading.Thread(target=background_loop)
        self.background_thread.daemon = True
        self.background_thread.start()

    def stop(self):
        """Stop background tasks"""
        self.running = False
        if hasattr(self, 'background_thread'):
            self.background_thread.join()

if __name__ == "__main__":
    SERVER_URL = "http://188.166.4.120:51820"
    CLIENT_ID = input("Enter your client ID: ")
    
    # WireGuard configuration setup
    print("\nEnter your WireGuard configuration:")
    public_key = input("Public key: ")
    endpoint = input("Endpoint (IP:Port): ")
    allowed_ips = input("Allowed IPs: ")
    
    wireguard_config = {
        "public_key": public_key,
        "endpoint": endpoint,
        "allowed_ips": allowed_ips
    }

    client = MessageClient(SERVER_URL, CLIENT_ID, wireguard_config)
    client.start_background_tasks()

    print(f"\nClient started with ID: {CLIENT_ID}")
    print(f"Performing check-ins every 10 minutes")

    # try:
    while True:
        try:
            print("\nAvailable Commands:")
            print("1. Connect to peer")
            print("2. Show connected peers")
            print("3. set connection with peer")
            print("4. Test connection with peer")
            print("5. List peers")
            print("6. Exit")
            
            choice = input("\nChoose an option: ")

            if choice == "1":
                peer_id = input("Enter peer ID to connect to: ")
                result = client.connect_to_peer(peer_id)
                if result:
                    print(f"Successfully connected to {peer_id}")
                else:
                    print("Connection failed")
            
            elif choice == "2":
                if client.connected_peers:
                    print("\nConnected peers:", list(client.connected_peers))
                    print("\nPeer WireGuard Configurations:")
                    for peer_id, config in client.peer_wireguard_configs.items():
                        print(f"\nPeer {peer_id}:")
                        print(json.dumps(config, indent=2))
                else:
                    print("\nNo connected peers")

            elif choice == "3":
                client.start_listening()
                
            elif choice == "4":
                if not client.connected_peers:
                    print("\nNo connected peers to test")
                    continue
                    
                peer_id = input("Enter peer ID to test connection with: ")
                if peer_id not in client.connected_peers:
                    print("Not connected to this peer")
                    continue
                    
                if client.test_connection(peer_id):
                    print(f"Connection with {peer_id} is working")
                else:
                    print(f"Connection with {peer_id} failed")

            elif choice == "5":
                peers = client.get_peers()
                if peers:
                    print("\nActive peers:")
                    for peer in peers:
                        if peer['peer_id'] != CLIENT_ID:  # Don't show our own entry
                            print(f"Peer ID: {peer['peer_id']}")
                            print(f"Last seen: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(peer['last_seen']))}")
                            print(f"WireGuard config: {peer['wireguard_config']}")
                            print("-" * 50)
                else:
                    print("\nNo peers found or error retrieving peer list")
            
            elif choice == "6":
                print("\nShutting down client...")
                client.stop()  # Stop background tasks
                break  # Break out of the main loop
            
            else:
                print("\nInvalid option. Please try again.")

        except KeyboardInterrupt:
            print("\nReceived interrupt signal. Shutting down...")
            exit(0)
            # continue
        # finally:
        #     print("Cleaning up...")
        #     client.stop()  # Ensure background tasks are stopped
        #     print("Client shutdown complete.")
        #     exit(0)  # Ensure the program exits
