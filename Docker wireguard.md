## 1. Build a docker image 
```
\Satori> docker build --no-cache -f "Neuron/Dockerfile" -t satorinet/satorineuron:latest .

```
## 2. Create a Docker Network

First, create a Docker network for your WireGuard containers to use. This network isolates the VPN traffic:

    `docker network create wireguard-net`

## 3. Run the container
```
docker run --rm -it --name satorineuron -p 24601:24601 -p 51820:51820/udp -v c:\repos\satori\Neuron\config:/config -v c:\repos\Satori\Neuron:/Satori/Neuron --cap-add=NET_ADMIN --cap-add=SYS_MODULE --sysctl="net.ipv4.conf.all.src_valid_mark=1" --network=wireguard-net --env ENV=prod satorinet/satorineuron:latest bash
```
## 4. Generate Key Pairs

If previously generated before running the container no need of this step .

On each machine, run the following commands to generate the keys:

    `wg genkey | tee privatekey | wg pubkey > publickey`

This generates:

privatekey: The private key for the machine.

publickey: The public key to share with the other machine.

## 5. Create WireGuard Configuration File:

If previously generated befor running the container no need of this step, just skip it. The existing wg0.conf will be copied to etc/wireguard/ . 

On each machine, create a configuration file for WireGuard, name it as wg0.conf. For example, on machine A:

On Machine A, create the configuration file:
```
    [Interface]
    PrivateKey = <Machine A's private key>
    Address = 10.0.0.1/24  # Internal IP address for the VPN
    ListenPort = 51820

    [Peer]
    PublicKey = <Machine B's public key>
    AllowedIPs = 10.0.0.2/32  # IP address for Machine B inside the VPN
    Endpoint = <Machine B's public IP>:51820  # Machine B's public IP and WireGuard port
    PersistentKeepalive = 25  # Keeps the connection alive
```
On Machine B, create a similar configuration:
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
```

Important:

Replace <Machine A's/B's private key> with the actual private key for each machine.

Replace <Machine A's/B's public key> with the public key for the other machine.

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

    `ping 10.0.0.2`  # From Machine A & B

    `ping 10.0.0.1`  # From Machine A & B

If the ping is successful, the two machines are now connected over the VPN.

Example:

![alt text](<images/Screenshot 2024-09-16 162150.png>)

## 9. Listen to Port


        `nc -l -v -p 51820` # Use it in Machine A or Machine B to listen to the given port.

## 10. Send Message


        `nc 10.0.0.1 51820`     # If MAchine A is listening, run it on Machine B

                                or

        `nc 10.0.0.2 51820`     # If MAchine B is listening, run it on MAchine A
                       

