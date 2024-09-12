# webrtc_peer.py
import sys
import os
import asyncio
import websockets
import tracemalloc
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import logging
from twilio.rest import Client

# Enable tracemalloc to get detailed memory allocation traceback
tracemalloc.start()
logging.basicConfig(level=logging.DEBUG)
# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

def get_turn_credentials():
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
    # Create a WebRTC connection
    # pc = RTCPeerConnection()
    # Get TURN server credentials from Twilio
    ice_servers = get_turn_credentials()
     # Create a WebRTC configuration with STUN and TURN servers
    config = RTCConfiguration(iceServers=ice_servers)


    # Create a WebRTC connection with the configuration
    pc = RTCPeerConnection(configuration=config)

    # pc.addIceCandidate({'urls': ['stun:stun.l.google.com:19302']})



    # Create a data channel
    channel = pc.createDataChannel("chat")
    logging.debug("Data channel created")
    # Define the on_open event handler
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


    # Create an SDP offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Send the SDP offer via WebSocket to the signaling server
    await websocket.send(pc.localDescription.sdp)

    # Wait for the SDP answer
    answer_sdp = await websocket.recv()
    answer_sdp = answer_sdp.replace("a=setup:actpass", "a=setup:active")  # Modify the SDP answer
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

     # Print the SDP answer for debugging

    # Validate the SDP answer
    if "a=setup:active" not in answer.sdp and "a=setup:passive" not in answer.sdp:
        raise ValueError("DTLS setup attribute must be 'active' or 'passive' for an answer")

    await pc.setRemoteDescription(answer)

    # Handle ICE candidate exchange here if needed (for now, we can skip)
    # RTCIceCandidate()
    
   
    # return pc
    # Wait for the connection to be established
    connection_timeout = 30  # seconds
    start_time = asyncio.get_event_loop().time()
    while pc.connectionState != "connected":
        if asyncio.get_event_loop().time() - start_time > connection_timeout:
            logging.error("Connection timed out")
            break
        await asyncio.sleep(1)
        logging.debug(f"Waiting for connection... Current state: {pc.connectionState}")

    if pc.connectionState == "connected":
        logging.info("WebRTC connection established successfully")
        # Keep the connection alive
        while pc.connectionState == "connected":
            await asyncio.sleep(1)
    else:
        logging.error("Failed to establish WebRTC connection")

    # Close the peer connection
    await pc.close()
    logging.info("Connection closed")

async def main(uri: str = "ws://localhost:8765"):
    # Connect to the WebSocket signaling server
    async with websockets.connect(uri) as websocket:
        await send_offer(websocket)

if __name__ == "__main__":
    asyncio.run(main(
        uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))
