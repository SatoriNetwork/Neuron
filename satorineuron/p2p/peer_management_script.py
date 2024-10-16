import json
import subprocess
import threading
import time
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

class PeerManager:
    def __init__(self, interface="wg0", config_file="peers.json", port=51820):
        self.interface = interface
        self.config_file = config_file
        self.port = port
        self.peers = self.load_peers()
        self.listening = False
        self.connecting = False
        
        # Start the WireGuard service
        print(start_wireguard_service(self.interface))

    def load_peers(self):
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return []

    def save_peers(self):
        with open(self.config_file, 'w') as f:
            json.dump(self.peers, f, indent=2)

    def add_peer(self, public_key, allowed_ips, endpoint=None):
        new_peer = {
            "public_key": public_key,
            "allowed_ips": allowed_ips,
            "endpoint": endpoint
        }
        self.peers.append(new_peer)
        print(add_peer(self.interface, public_key, allowed_ips, endpoint))
        self.save_peers()

    def remove_peer(self, public_key):
        self.peers = [peer for peer in self.peers if peer['public_key'] != public_key]
        print(remove_peer(self.interface, public_key))
        self.save_peers()

    def list_peers(self):
        return list_peers(self.interface)

    def start_listening(self):
        """Start port listening mode"""
        if not self.listening:
            self.listening = True
            print(f"\nStarting port listening on {self.port}")
            print("Press Ctrl+C to stop listening and return to menu...")
            print("-" * 50)
            
            try:
                start_port_listening(self.port)
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

    def start_connection(self, target_ip):
        """Start connection to target IP"""
        if not self.connecting:
            self.connecting = True
            print(f"\nConnecting to {target_ip}:{self.port}")
            print("Press Ctrl+C to stop connection and return to menu...")
            print("-" * 50)
            
            try:
                start_port_connection(target_ip, self.port)
            except KeyboardInterrupt:
                print("\nStopping connection...")
            finally:
                self.stop_connection()
                print("\nConnection stopped. Returning to menu...")
                time.sleep(1)

    def stop_connection(self):
        """Stop connection"""
        if self.connecting:
            self.connecting = False
            stop_port_connection()

def main():
    manager = PeerManager()

    while True:
        print("\nWireGuard Peer Management")
        print("1. Add Peer")
        print("2. Remove Peer")
        print("3. List Peers")
        print("4. Start Port Listening")
        print("5. Connect to Peer")
        print("6. Exit")
        
        try:
            choice = input("Enter your choice (1-6): ")

            if choice == "1":
                public_key = input("Enter peer's public key: ")
                allowed_ips = input("Enter allowed IPs (e.g., 10.0.0.2/32): ")
                endpoint = input("Enter endpoint (optional, press Enter to skip): ")
                manager.add_peer(public_key, allowed_ips, endpoint if endpoint else None)

            elif choice == "2":
                public_key = input("Enter peer's public key to remove: ")
                manager.remove_peer(public_key)

            elif choice == "3":
                peers = manager.list_peers()
                for peer in peers:
                    print(f"Public Key: {peer['public_key']}")
                    print(f"Allowed IPs: {peer['allowed_ips']}")
                    print(f"Endpoint: {peer['endpoint']}")
                    print("---")

            elif choice == "4":
                manager.start_listening()

            elif choice == "5":
                target_ip = input("Enter target IP (e.g., 10.0.0.1): ")
                manager.start_connection(target_ip)

            elif choice == "6":
                print("Exiting...")
                break

            else:
                print("Invalid choice. Please try again.")

        except KeyboardInterrupt:
            print("\nOperation cancelled. Returning to menu...")
            continue

if __name__ == "__main__":
    main()