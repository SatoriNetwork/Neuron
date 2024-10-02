import subprocess
import json

def run_command(command):
    """Run a shell command and return its output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed: {result.stderr}")
    return result.stdout.strip()

def add_peer(interface, public_key, allowed_ips, endpoint=None):
    """Add a new peer to the WireGuard interface."""
    command = f"wg set {interface} peer {public_key} allowed-ips {allowed_ips}"
    if endpoint:
        command += f" endpoint {endpoint}"
    run_command(command)
    save_config(interface)
    print(f"Peer {public_key} added successfully.")

def remove_peer(interface, public_key):
    """Remove a peer from the WireGuard interface."""
    run_command(f"wg set {interface} peer {public_key} remove")
    save_config(interface)
    print(f"Peer {public_key} removed successfully.")

def list_peers(interface):
    """List all peers connected to the WireGuard interface."""
    output = run_command(f"wg show {interface} dump")
    lines = output.split('\n')[1:]  # Skip the first line (interface info)
    peers = []
    for line in lines:
        parts = line.split('\t')
        if len(parts) >= 3:
            peers.append({
                'public_key': parts[0],
                'allowed_ips': parts[3],
                'endpoint': parts[2] if parts[2] != '(none)' else None
            })
    return peers

def save_config(interface):
    """Save the current WireGuard configuration."""
    run_command(f"wg-quick save {interface}")

def print_peers(peers):
    """Print peers in a formatted way."""
    for peer in peers:
        print(f"Public Key: {peer['public_key']}")
        print(f"Allowed IPs: {peer['allowed_ips']}")
        print(f"Endpoint: {peer['endpoint']}")
        print("---")

# Example usage
if __name__ == "__main__":
    interface = "wg0"  # Change this if your interface name is different

    while True:
        print("\nWireGuard Peer Management")
        print("1. Add Peer")
        print("2. Remove Peer")
        print("3. List Peers")
        print("4. Exit")
        choice = input("Enter your choice (1-4): ")

        if choice == "1":
            public_key = input("Enter peer's public key: ")
            allowed_ips = input("Enter allowed IPs (e.g., 10.0.0.2/32): ")
            endpoint = input("Enter endpoint (optional, press Enter to skip): ")
            add_peer(interface, public_key, allowed_ips, endpoint if endpoint else None)

        elif choice == "2":
            public_key = input("Enter peer's public key to remove: ")
            remove_peer(interface, public_key)

        elif choice == "3":
            peers = list_peers(interface)
            print_peers(peers)

        elif choice == "4":
            print("Exiting...")
            break

        else:
            print("Invalid choice. Please try again.")