# WebRTC peer implementation for establishing a connection and data channel

import sys
import os
import asyncio
import websockets
import tracemalloc
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import logging
from twilio.rest import Client

# Enable tracemalloc for detailed memory allocation traceback
tracemalloc.start()
logging.basicConfig(level=logging.DEBUG)

# Twilio credentials for TURN server access
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

def get_turn_credentials():
    """Fetch TURN server credentials from Twilio"""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    token = client.tokens.create()

    ice_servers = []
    for server in token.ice_servers:
        urls = server['url'] if isinstance(server['url'], list) else [server['url']]
        username = server.get('username')
        credential = server.get('credential')
        
        ice_server = RTCIceServer(urls=urls, username=username, credential=credential)
        ice_servers.append(ice_server)
    
    logging.debug(f"ICE Servers: {ice_servers}")
    return ice_servers

async def send_offer(websocket):
    """Create and send a WebRTC offer, then handle the answer"""
    # Get TURN server credentials from Twilio
    ice_servers = get_turn_credentials()
    # Create a WebRTC configuration with STUN and TURN servers
    config = RTCConfiguration(iceServers=ice_servers)

    # Create a WebRTC connection with the configuration
    pc = RTCPeerConnection(configuration=config)

    # Create a data channel
    channel = pc.createDataChannel("chat")
    logging.debug("Data channel created")

    # Define event handlers for the data channel
    @channel.on("open")
    def on_open():
        logging.info("Data channel is open")
        channel.send("Hello World")
        logging.info("Sent: Hello World")

    @channel.on("message")
    def on_message(message):
        print(f"Received message: {message}")
        logging.info(f"Received message: {message}")

    @pc.on("datachannel")
    def on_datachannel(channel):
        logging.info(f"New data channel created: {channel.label}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        logging.info(f"Connection state changed to: {pc.connectionState}")
        if pc.connectionState == "connected":
            logging.info("WebRTC connection established")
        elif pc.connectionState == "failed":
            logging.error("WebRTC connection failed")
            await pc.close()

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        logging.info(f"ICE connection state changed to: {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            logging.error("ICE connection failed")
            await pc.close()

    # Create an SDP offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Send the SDP offer via WebSocket to the signaling server
    await websocket.send(pc.localDescription.sdp)

    # Wait for and process the SDP answer
    answer_sdp = await websocket.recv()
    
    # Ensure the answer SDP contains the correct DTLS setup attribute
    if "a=setup:active" not in answer_sdp and "a=setup:passive" not in answer_sdp:
        answer_sdp = answer_sdp.replace("a=setup:actpass", "a=setup:passive")
    
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

    # Set remote description
    await pc.setRemoteDescription(answer)

    # Wait for the connection to be established
    connection_timeout = 60  # 60 seconds timeout
    start_time = asyncio.get_event_loop().time()
    while pc.connectionState != "connected" and pc.iceConnectionState != "connected":
        if asyncio.get_event_loop().time() - start_time > connection_timeout:
            logging.error("Connection timed out")
            break
        await asyncio.sleep(1)
        logging.debug(f"Waiting for connection... Connection state: {pc.connectionState}, ICE connection state: {pc.iceConnectionState}")

    if pc.connectionState == "connected" or pc.iceConnectionState == "connected":
        logging.info("WebRTC connection established successfully")
        # Keep the connection alive
        while pc.connectionState == "connected" or pc.iceConnectionState == "connected":
            await asyncio.sleep(1)
    else:
        logging.error(f"Failed to establish WebRTC connection. Final states - Connection: {pc.connectionState}, ICE: {pc.iceConnectionState}")

    # Close the peer connection
    await pc.close()
    logging.info("Connection closed")

async def main(uri: str = "ws://localhost:8765"):
    """Main function to establish WebSocket connection and initiate WebRTC process"""
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            async with websockets.connect(uri) as websocket:
                await send_offer(websocket)
                break  # If successful, break out of the retry loop
        except Exception as e:
            logging.error(f"Connection attempt {retry_count + 1} failed: {str(e)}")
            retry_count += 1
            if retry_count < max_retries:
                logging.info(f"Retrying in 5 seconds...")
                await asyncio.sleep(5)
            else:
                logging.error("Max retries reached. Unable to establish connection.")

if __name__ == "__main__":
    asyncio.run(main(
        uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))

# The DTLS handshake failure (DEBUG:aiortc.rtcdtlstransport:RTCDtlsTransport(server) x DTLS handshake failed (connection error))
# can occur due to several reasons:
# 1. Firewall or NAT issues: The DTLS packets might be blocked by a firewall or NAT traversal might fail.
# 2. Incompatible DTLS versions: The peers might be using incompatible DTLS versions.
# 3. Certificate issues: There might be problems with the self-signed certificates used in the DTLS handshake.
# 4. Network issues: Packet loss or high latency could cause the handshake to fail.
# 5. Incorrect DTLS setup attribute: The 'setup' attribute in the SDP might be incorrectly set.

# To troubleshoot:
# 1. Ensure that the necessary ports are open in your firewall.
# 2. Check that both peers are using compatible WebRTC implementations.
# 3. Verify that the TURN server is correctly configured and accessible.
# 4. Monitor network conditions and try the connection in a more stable network environment.
# 5. Double-check the SDP handling, especially the 'setup' attribute (as done in this code).

# If the issue persists, you may need to add more detailed logging to trace the exact point of failure
# in the DTLS handshake process.
