import subprocess
import signal
import os
import random
import sys

# Global variables to store process IDs
nc_process = None
nc_connect_process = None


def run_command(command) -> str:
    """Run a shell command and return its output."""
    result = subprocess.run(command, shell=True,
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Command failed: {result.stderr}")
    return result.stdout.strip()


def add_peer(interface, public_key, allowed_ips, endpoint=None) -> str:
    """Add a new peer to the WireGuard interface."""
    command = f"wg set {interface} peer {public_key} allowed-ips {allowed_ips}"
    if endpoint:
        command += f" endpoint {endpoint}"
    run_command(command)
    save_config(interface)
    return f"Peer {public_key} added successfully."


def remove_peer(interface, public_key) -> str:
    """Remove a peer from the WireGuard interface."""
    run_command(f"wg set {interface} peer {public_key} remove")
    save_config(interface)
    return f"Peer {public_key} removed successfully."


def list_peers(interface) -> list:
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

def set_wireguard_ip(interface, ip_address) -> str:
    """Set a unique IP address with a /16 subnet in the WireGuard configuration."""
    config_file_path = f"/etc/wireguard/{interface}.conf"
    try:
        with open(config_file_path, 'r') as file:
            config_data = file.readlines()
        
        # Update the IP address in the configuration file with a /16 mask
        config_data = [
            line if not line.startswith("Address") else f"Address = {ip_address}/16\n"
            for line in config_data
        ]

        with open(config_file_path, 'w') as file:
            file.writelines(config_data)
        
        return f"IP address {ip_address}/16 set for {interface}."
    except FileNotFoundError:
        return f"Configuration file for {interface} not found."
    except Exception as e:
        return f"Failed to set IP address for {interface}: {str(e)}"

def start_wireguard_service(interface,unique_ip) -> str:
    """Set up a unique address with /16 subnet and start the WireGuard service for the specified interface."""
    setup_result = set_wireguard_ip(interface, unique_ip)
    
    if "Failed" in setup_result:
        return setup_result
    
    try:
        output = run_command(f"wg-quick up {interface}")
        return f"WireGuard service started for {interface} with IP {unique_ip}/16: {output}"
    except Exception as e:
        return f"Failed to start WireGuard service for {interface}: {str(e)}"

def start_port_listening(port):
    """Start listening on the specified port using netcat."""
    global nc_process
    try:
        # Clear the screen for better visibility
        os.system('clear' if os.name == 'posix' else 'cls')

        print(f"Listening on port {port}...")
        print("Press Ctrl+C to stop listening and return to menu")
        print("-" * 50)

        # Start netcat in verbose mode with line buffering
        nc_process = subprocess.Popen(
            ['nc', '-l', '-v', '-p', str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True
        )

        # Monitor the output in real-time
        while True:
            if nc_process.poll() is not None:
                break

            output = nc_process.stdout.readline()
            if output:
                print(output.strip())

            error = nc_process.stderr.readline()
            if error:
                print(f"Error: {error.strip()}")

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
    finally:
        stop_port_listening()


def stop_port_listening():
    """Stop the netcat listening process if it's running."""
    global nc_process
    if nc_process:
        try:
            nc_process.terminate()
            nc_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            nc_process.kill()
        finally:
            nc_process = None


def start_port_connection(target_ip, port):
    """Start connection to target IP and port using netcat."""
    global nc_connect_process
    try:
        # Clear the screen for better visibility
        os.system('clear' if os.name == 'posix' else 'cls')

        print(f"Connecting to {target_ip}:{port}...")
        print("Press Ctrl+C to stop connection and return to menu")
        print("-" * 50)

        # Start netcat connection in verbose mode with line buffering
        nc_connect_process = subprocess.Popen(
            ['nc', '-v', target_ip, str(port)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True
        )

        # Monitor the output in real-time
        while True:
            if nc_connect_process.poll() is not None:
                break

            output = nc_connect_process.stdout.readline()
            if output:
                print(output.strip())

            error = nc_connect_process.stderr.readline()
            if error:
                print(f"Error: {error.strip()}")

    except KeyboardInterrupt:
        raise
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
    finally:
        stop_port_connection()


def stop_port_connection():
    """Stop the netcat connection process if it's running."""
    global nc_connect_process
    if nc_connect_process:
        try:
            nc_connect_process.terminate()
            nc_connect_process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            nc_connect_process.kill()
        finally:
            nc_connect_process = None
