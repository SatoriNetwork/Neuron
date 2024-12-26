'''
we probably wont use this. commenting out.
import os
import subprocess
import json
import fcntl
from flask import Flask, render_template, jsonify

app = Flask(__name__)

# Function to get the last assigned IP from a file
def get_last_ip(filename="last_ip.txt"):
    if os.path.exists(filename):
        with open(filename, "r") as file:
            last_ip = file.read().strip()
        return last_ip
    return "10.0.0.8"  # Default starting IP

# Function to save the last assigned IP to a file
def save_last_ip(ip, filename="last_ip.txt"):
    # Open the file with exclusive lock to avoid race conditions
    with open(filename, "w") as file:
        fcntl.flock(file, fcntl.LOCK_EX)  # Locking for atomic file writes
        file.write(ip)
        fcntl.flock(file, fcntl.LOCK_UN)  # Unlocking after writing

# Function to generate the next IP address in the sequence
def generate_next_ip():
    last_ip = get_last_ip()
    base_ip = last_ip.split('.')
    major_subnet = int(base_ip[1])
    subnet = int(base_ip[2])
    host = int(base_ip[3])

    host += 1
    if host == 255:
        host = 1
        subnet += 1
    if subnet == 255:
        subnet = 0
        major_subnet += 1
    if major_subnet == 255:
        major_subnet = 0

    next_ip = f"10.{major_subnet}.{subnet}.{host}"
    save_last_ip(next_ip)
    return next_ip

# Function to generate client public and private keys
def generate_client_key_pair():
    private_key = subprocess.check_output(['wg', 'genkey']).strip().decode()
    public_key = subprocess.check_output(['wg', 'pubkey'], input=private_key.encode()).strip().decode()
    return private_key, public_key

# Function to update the WireGuard server config
def update_server_config(client_public_key, client_ip):
    server_config_path = '/etc/wireguard/wg0.conf'
    with open(server_config_path, 'a') as f:
        f.write(f"\n[Peer]\n")
        f.write(f"PublicKey = {client_public_key}\n")
        f.write(f"AllowedIPs = {client_ip}/32\n")

    subprocess.run(['wg', 'set', 'wg0', 'peer', client_public_key, 'allowed-ips', f'{client_ip}/32'])
    subprocess.run(['systemctl', 'restart', 'wg-quick@wg0'])

# Function to send the config to the client
def send_config_to_client(client_ip, client_private_key, client_public_key):
    config = {
        'PrivateKey': client_private_key,
        'PublicKey': client_public_key,
        'Address': client_ip,
        'Endpoint': '23.239.18.72:51820',
        'AllowedIPs': '10.0.0.0/24',
        'PersistentKeepalive': '25',
    }
    return config  # Return the config as JSON

@app.route('/')
def index():
    return render_template('index.html')  # This is a template for the button

@app.route('/add_client', methods=['POST'])
def add_client():
    # Step 1: Generate a new public/private key pair for the client
    client_private_key, client_public_key = generate_client_key_pair()

    # Step 2: Generate the next available IP for the client
    client_ip = generate_next_ip()

    # Step 3: Update the WireGuard server configuration with the new client
    update_server_config(client_public_key, client_ip)

    # Step 4: Generate the configuration to send back to the client
    client_config = send_config_to_client(client_ip, client_private_key, client_public_key)

    # Return the configuration as JSON
    return jsonify(client_config)

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=5000)
'''
