# Starting Satori Neuron Docker Container with WireGuard Private Network

## Overview
WireGuard is a fast, modern, and secure VPN (Virtual Private Network) protocol. To connect a client to the WireGuard server, users need to:
1. Add their public keys to the WireGuard server.
2. Download the generated configuration file from the server.
3. Import this configuration into their WireGuard client to establish the connection.

To automate the user addition and configuration file generation process, we’ve built a Flask-based web application that:
- Adds users to the WireGuard server.
- Generates a configuration file that the user can use to connect to the VPN network.
- Provides an easy-to-use web interface for users to download the configuration file.

## System Architecture
1. **WireGuard Server**: This is the central server running WireGuard, which handles the VPN connections.
2. **Flask Web Application**: The Flask application runs on a web server `http://23.239.18.72` which allows users to register, and automatically adds them to the WireGuard server.
3. **WireGuard Client**: Users install the WireGuard client on their device, which they use to connect to the private network using the configuration file provided.

## Key Steps for the User

### 1. Access the Flask Application:
- Open your browser and go to `http://23.239.18.72`.

### 2. Download the Configuration File:
- After registration, download the configuration file.

### 3. Install and Import into WireGuard Client:
- Install the WireGuard client.
- Upload the configuration file to `/etc/wireguard/`.

### 4. Start the WireGuard Client:
- Activate the VPN connection using:
    ```bash
    wg-quick up wg0
    ```

## Post-VPN Setup: Creating a Docker Network and Running the Satori Containers
After successfully connecting to the WireGuard VPN client, follow the steps below to set up the container:

## 1. Create Necessary Directories:
Navigate to the root directory and create a directory for the Satori project:

cd /
mkdir Satori
cd Satori

## 2. Clone the Required Repositories

Run the following commands to clone the necessary repositories:

cd /Satori && git clone -b main https://github.com/SatoriNetwork/Synapse.git && \
cd /Satori && git clone -b main https://github.com/SatoriNetwork/Lib.git && \
cd /Satori && git clone -b main https://github.com/SatoriNetwork/Wallet.git && \
cd /Satori && git clone -b main https://github.com/SatoriNetwork/Engine.git && \
cd /Satori && git clone -b main https://github.com/SatoriNetwork/Neuron.git && \
mkdir /Satori/Neuron/models && \
mkdir /Satori/Neuron/models/huggingface

##3. Start the Docker Container

Now, run the following Docker command to start the container, replacing there-ip with the desired IP address for the container:

docker run --rm -it --name satorineuron --net=host \
  -v /Satori/Neuron:/Satori/Neuron \
  -v /Satori/Synapse:/Satori/Synapse \
  -v /Satori/Lib:/Satori/Lib \
  -v /Satori/Wallet:/Satori/Wallet \
  -v /Satori/Engine:/Satori/Engine \
  --env ENV=prod \
  --env RUNMODE=normal \
  satorinet/satorineuron:latest bash

##4. Run the Python Script in the Container

Inside the running container, execute the following command to run the Satori Python script:

```bash
python satori.py

This will initialize the Satori services within the Docker container. You are now set up and running!
