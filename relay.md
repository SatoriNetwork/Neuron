## 1. Install WireGuard

You need to install WireGuard on both machines. On most Linux distributions, WireGuard is available in the default package manager:

Ubuntu/Debian:

    `sudo apt install wireguard`

CentOS/Fedora:

    `sudo dnf install wireguard-tools`

Windows/Mac: You can download WireGuard clients from the official WireGuard website.

## 2. Create a Docker Network

First, create a Docker network for your WireGuard containers to use. This network isolates the VPN traffic:

    `docker network create wireguard-net`

## 3. Create and Run the Docker Container

choose a configuration path (make a folder such as /path/to/config), copy the path.

If you want to run the container directly without Docker Compose, use:
```
    docker run -d --name=wireguard --cap-add=NET_ADMIN --cap-add=SYS_MODULE -e PUID=1000 -e PGID=1000 -e TZ=Etc/UTC -v c:\repos\satori\Neuron\config:/config  -p 51820:51820/udp --sysctl="net.ipv4.conf.all.src_valid_mark=1" --network=wireguard-net linuxserver/wireguard

```
Be sure to replace /path/to/config with the path where you want to store WireGuard configuration files.

If you prefer to manage your WireGuard containers using Docker Compose, create a docker-compose.yml file:
```
    version: '3'
    services:
    wireguard:
        image: linuxserver/wireguard
        container_name: wireguard
        cap_add:
        - NET_ADMIN
        - SYS_MODULE
        environment:
        - PUID=1000
        - PGID=1000
        - TZ=Etc/UTC
        volumes:
        - ./path/to/config:/config
        - /lib/modules:/lib/modules
        ports:
        - 51820:51820/udp
        sysctls:
        - net.ipv4.conf.all.src_valid_mark=1
        networks:
        - wireguard-net
    networks:
    wireguard-net:
        external: true
```

Start the WireGuard container:

    `docker-compose up -d`

## 4. Generate Key Pairs

Each machine will need to generate a public-private key pair for encryption.

Exec into the running WireGuard container to generate key pairs:

    `docker exec -it wireguard /bin/bash`

Go into the config folder :

    cd config

On each machine, run the following commands to generate the keys:

    `wg genkey | tee privatekey | wg pubkey > publickey`

This generates:

privatekey: The private key for the machine.

publickey: The public key to share with the other machine.

Example:

![alt text](<images/Screenshot 2024-09-16 165011.png>)

## 5. Create WireGuard Configuration File:

On each machine, create a configuration file for WireGuard, name it as wg0.conf. For example, on machine A:

On Machine A, create the configuration file:
```
    [Interface]
    PrivateKey = <Machine A's private key>
    Address = 10.0.0.1/24  # Internal IP address for the VPN
    ListenPort = 51820

    [Peer]
    PublicKey = <Machine B's public key>
    AllowedIPs = 10.0.0.2/32, 10.0.0.3/32  # IP address for Machine B inside the VPN
    Endpoint = <Machine B's public IP>:51820  # Machine B's public IP and WireGuard port
    PersistentKeepalive = 25  # Keeps the connection alive
```

On Machine B, create a similar configuration but with all the peers as it can be set as the hub:
```
    [Interface]
    PrivateKey = <Machine B's private key>
    Address = 10.0.0.2/24  # Internal IP address for the VPN
    ListenPort = 51820

    [Peer]
    PublicKey = <Machine A's public key>
    AllowedIPs = 10.0.0.1/32  # IP address for Machine A inside the VPN
    Endpoint = <Machine A's public IP>:51820  # Machine A's public IP and WireGuard port
    PersistentKeepalive = 25  # Keeps the connection alive

    [Peer]
    PublicKey = <Machine C's public key>
    AllowedIPs = 10.0.0.3/32  # IP address for Machine A inside the VPN
    Endpoint = <Machine C's public IP>:51820  # Machine A's public IP and WireGuard port
    PersistentKeepalive = 25  # Keeps the connection alive
```
On Machine C, create the configuration file:
```
    [Interface]
    PrivateKey = <Machine C's private key>
    Address = 10.0.0.3/24  # Internal IP address for the VPN
    ListenPort = 51820

    [Peer]
    PublicKey = <Machine B's public key>
    AllowedIPs = 10.0.0.2/32, 10.0.0.1/32  # IP address for Machine B inside the VPN
    Endpoint = <Machine B's public IP>:51820  # Machine B's public IP and WireGuard port
    PersistentKeepalive = 25  # Keeps the connection alive
```

Important:

Replace <Machine A's/B's/C's private key> with the actual private key for each machine.

Replace <Machine A's/B's/C's public key> with the public key for the other machine.

Set the Endpoint to the actual public IP addresses of each machine. You can use a DNS name if the machine has one.

The internal IP addresses (10.0.0.1, 10.0.0.2) are the virtual addresses used inside the VPN tunnel.

The ListenPort is the port number on which WireGuard will listen for incoming connections.

The PersistentKeepalive value ensures that the connection stays alive even if there is no traffic.

## 6. Start the WireGuard Service

Inside the container, start the WireGuard service:
```
    wg-quick up wg0     # It will look in the location /etc/wireguard/wg0.conf , On each machine, so create a file at /etc/wireguard/wg0.conf.

            or

    wg-quick up /path/to/wg0.conf
```

This starts the WireGuard service and connects the two machines.

(Optional)You can also activate or deactivate wg0.conf within the wireguard app, But first we need to add the config file there:

![alt text](<images/Screenshot (2).png>)
```
   `wg-quick down wg0`

            or

    `wg-quick down /path/to/wg0.conf`

```
This ends the WireGuard service.

## 7. Verify the Connection is Active

You can verify the connection by checking the WireGuard status:

    `wg`

This will show the current status of the WireGuard connection and the peers connected to the VPN.

Example:

![alt text](<images/Screenshot 2024-09-16 163946.png>)

## 8. Verify the VPN Connection

To ensure that the VPN is working, you can ping the other machine's internal VPN IP address (e.g., 10.0.0.2 from Machine A and 10.0.0.1 from Machine B).

    `ping 10.0.0.2`  # From Machine A & C

    `ping 10.0.0.1`  # From Machine B & C

    `ping 10.0.0.3`  # From Machine A & B
    

If the ping is successful, the two machines are now connected over the VPN.