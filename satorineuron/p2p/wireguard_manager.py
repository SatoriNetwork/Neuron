import subprocess
import json
import threading

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
    return f"Peer {public_key} added successfully."

def remove_peer(interface, public_key):
    """Remove a peer from the WireGuard interface."""
    run_command(f"wg set {interface} peer {public_key} remove")
    save_config(interface)
    return f"Peer {public_key} removed successfully."

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

def send_message(ip, port, message):
    """Send a message to the specified IP and port."""
    try:
        command = f"echo '{message}' | nc -w 5 {ip} {port}"
        output = run_command(command)
        return f"Message sent to {ip}:{port}"
    except Exception as e:
        return f"Failed to send message to {ip}:{port}: {str(e)}"

def start_wireguard_service(interface):
    """Start the WireGuard service for the specified interface."""
    try:
        output = run_command(f"wg-quick up {interface}")
        return f"WireGuard service started for interface {interface}: {output}"
    except Exception as e:
        return f"Failed to start WireGuard service for interface {interface}: {str(e)}"

def receive_messages(port, callback):
    """
    Listen for incoming messages on the specified port.
    The callback function will be called with the received message.
    """
    def listener():
        while True:
            try:
                command = f"nc -l -p {port}"
                message = run_command(command)
                if message:
                    callback(message)
            except Exception as e:
                print(f"Error receiving message: {str(e)}")

    thread = threading.Thread(target=listener)
    thread.daemon = True
    thread.start()
    return thread