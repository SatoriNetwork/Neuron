import json
import time
import threading
from collections import deque
from wireguard_manager import add_peer, remove_peer, list_peers, send_message, start_wireguard_service, receive_messages

class PeerManager:
    def __init__(self, interface="wg0", config_file="peers.json", port=51820):
        self.interface = interface
        self.config_file = config_file
        self.port = port
        self.peers = self.load_peers()
        self.running = False
        self.messages = deque(maxlen=100)  # Store last 100 messages
        
        # Start the WireGuard service
        print(start_wireguard_service(self.interface))

        # Start listening for messages
        self.receive_thread = receive_messages(self.port, self.handle_received_message)

    def handle_received_message(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        formatted_message = f"[{timestamp}] Received: {message}"
        print("\n" + formatted_message)
        self.messages.append(formatted_message)
        print("Enter your choice (1-7): ", end="", flush=True)

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

    def send_messages(self):
        while self.running:
            for peer in self.peers:
                ip = peer['allowed_ips'].split('/')[0]  # Assuming the first IP in allowed_ips is the target
                try:
                    message = f"Hello from {self.interface}"
                    print(send_message(ip, self.port, message))
                    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                    self.messages.append(f"[{timestamp}] Sent to {ip}: {message}")
                except Exception as e:
                    print(f"Failed to send message to {ip}: {str(e)}")
            time.sleep(30)

    def start(self):
        self.running = True
        self.message_thread = threading.Thread(target=self.send_messages)
        self.message_thread.start()
        print("Peer manager started. Sending messages every 30 seconds.")

    def stop(self):
        self.running = False
        if hasattr(self, 'message_thread'):
            self.message_thread.join()
        print("Peer manager stopped.")

    def view_messages(self):
        if not self.messages:
            print("No messages to display.")
        else:
            print("\nLast 100 messages:")
            for message in self.messages:
                print(message)

def main():
    manager = PeerManager()

    while True:
        print("\nWireGuard Peer Management")
        print("1. Add Peer")
        print("2. Remove Peer")
        print("3. List Peers")
        print("4. Start Sending Messages")
        print("5. Stop Sending Messages")
        print("6. View Messages")
        print("7. Exit")
        choice = input("Enter your choice (1-7): ")

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
            manager.start()

        elif choice == "5":
            manager.stop()

        elif choice == "6":
            manager.view_messages()

        elif choice == "7":
            if manager.running:
                manager.stop()
            print("Exiting...")
            break

        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()