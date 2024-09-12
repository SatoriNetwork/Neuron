# peer.py (formerly webrtc_peer.py)
import sys
import asyncio
import websockets
import tracemalloc
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
import logging
from twilio.rest import Client
import os

# Enable tracemalloc to get detailed memory allocation traceback
tracemalloc.start()
logging.basicConfig(level=logging.DEBUG)

# Twilio credentials
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

def get_turn_credentials():
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    token = client.tokens.create()
    return token.ice_servers

async def send_offer(websocket):
    # Get TURN server credentials from Twilio
    ice_servers = get_turn_credentials()

    # Create a WebRTC configuration with STUN and TURN servers
    config = RTCConfiguration(
        iceServers=[RTCIceServer(**{k: v for k, v in server.items() if k != 'url'}) for server in ice_servers]

    )

    # Create a WebRTC connection with the configuration
    pc = RTCPeerConnection(configuration=config)

    # Create a data channel
    channel = pc.createDataChannel("chat")
    logging.debug("Data channel created")

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
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

    # Validate the SDP answer
    if "a=setup:active" not in answer.sdp and "a=setup:passive" not in answer.sdp:
        raise ValueError("DTLS setup attribute must be 'active' or 'passive' for an answer")

    await pc.setRemoteDescription(answer)

    # Wait for the connection to be established
    while pc.connectionState != "connected":
        await asyncio.sleep(1)
        logging.debug(f"Waiting for connection... Current state: {pc.connectionState}")

    # Keep the connection alive
    while pc.connectionState == "connected":
        await asyncio.sleep(1)

    logging.info("Connection closed or failed")

async def main(uri: str = "ws://localhost:8765"):
    # Connect to the WebSocket signaling server
    async with websockets.connect(uri) as websocket:
        await send_offer(websocket)

if __name__ == "__main__":
    asyncio.run(main(
        uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))