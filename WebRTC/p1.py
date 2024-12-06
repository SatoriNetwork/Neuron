import asyncio
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCConfiguration, RTCIceServer
import sys
import logging
import os
from twilio.rest import Client
import socket
import time

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

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
    logging.info("Starting send_offer function")
    # Get TURN server credentials from Twilio
    ice_servers = get_turn_credentials()
    # Create a WebRTC configuration with STUN and TURN servers
    config = RTCConfiguration(iceServers=ice_servers)
    # Create a WebRTC connection with the configuration
    pc = RTCPeerConnection(configuration=config)
    logging.debug("RTCPeerConnection created with STUN and TURN servers")

    # Create a data channel
    channel = pc.createDataChannel("chat")
    logging.debug("Data channel created")

    @channel.on("open")
    def on_open():
        logging.info("Data channel is open")
        channel.send("Hello from the sender!")
        logging.debug("Sent: Hello from the sender!")

    @channel.on("message")
    def on_message(message):
        logging.info(f"Received message: {message}")

    @channel.on("close")
    def on_close():
        logging.info("Data channel is closed")

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        logging.info(f"ICE connection state changed to: {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            logging.error("ICE connection failed")
            await pc.close()

    @pc.on("icegatheringstatechange")
    def on_icegatheringstatechange():
        logging.info(f"ICE gathering state changed to: {pc.iceGatheringState}")

    @pc.on("dtlsstatechange")
    def on_dtls_state_change():
        state = pc.dtlsTransport.state
        print(f"DTLS state changed: {state}")
        if state == "failed":
            print("DTLS handshake failed.")

    # Create an SDP offer with retry logic
    retries = 5
    backoff = 1
    for attempt in range(retries):
        try:
            offer = await pc.createOffer()
            await pc.setLocalDescription(offer)
            logging.debug("Local description set")
            break
        except Exception as e:
            logging.error(f"DTLS handshake failed: {e}. Retrying in {backoff} seconds...")
            await asyncio.sleep(backoff)
            backoff *= 2  # Exponential backoff
        if attempt == retries - 1:
            logging.error("Failed to create offer after multiple attempts")
            return None, None

    # Log ICE candidates as they are gathered
    @pc.on("icecandidate")
    def on_icecandidate(event):
        if event.candidate:
            logging.debug(f"New ICE candidate: {event.candidate.sdp}")
            logging.debug(f"ICE candidate type: {event.candidate.type}")
            logging.debug(f"ICE candidate protocol: {event.candidate.protocol}")
            print(f"Local ICE Candidate: {event.candidate}")

    # Wait for ICE gathering to complete or timeout
    ice_gathering_complete = asyncio.Event()
    @pc.on("icegatheringstatechange")
    def on_icegatheringstatechange():
        if pc.iceGatheringState == "complete":
            ice_gathering_complete.set()

    try:
        await asyncio.wait_for(ice_gathering_complete.wait(), timeout=60)  # Increased timeout to 60 seconds
    except asyncio.TimeoutError:
        logging.warning("ICE gathering timed out, proceeding with available candidates")

    # Send the SDP offer via WebSocket to the signaling server
    await websocket.send(pc.localDescription.sdp)
    logging.debug("SDP offer sent to signaling server")

    # Wait for the SDP answer
    answer_sdp = await websocket.recv()
    logging.debug("Received SDP answer from signaling server")
    
    # Ensure the answer SDP contains the correct DTLS setup attribute
    if "a=setup:active" not in answer_sdp and "a=setup:passive" not in answer_sdp:
        answer_sdp = answer_sdp.replace("a=setup:actpass", "a=setup:passive")
    
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer")
    await pc.setRemoteDescription(answer)
    logging.debug("Remote description set")

    # Wait for connection to be established or fail
    connection_complete = asyncio.Event()
    @pc.on("connectionstatechange")
    def on_connectionstatechange():
        logging.info(f"Connection state changed to: {pc.connectionState}")
        if pc.connectionState in ["connected", "failed"]:
            connection_complete.set()

    try:
        await asyncio.wait_for(connection_complete.wait(), timeout=120)  # Increased timeout to 120 seconds
    except asyncio.TimeoutError:
        logging.error("Connection establishment timed out")
        await pc.close()
        return None, None

    if pc.connectionState == "connected":
        logging.info("WebRTC connection established successfully")
    else:
        logging.error(f"Failed to establish WebRTC connection. Final state: {pc.connectionState}")
        await pc.close()
        return None, None

    logging.info("send_offer function completed")
    return pc, channel

async def main(uri = "ws://localhost:8765"):
    logging.info(f"Starting main function with URI: {uri}")
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        try:
            async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as websocket:
                logging.info("Connected to WebSocket signaling server")
                pc, channel = await send_offer(websocket)
                
                if pc is None or channel is None:
                    logging.error("Failed to establish connection")
                    retry_count += 1
                    continue

                # Keep the connection alive
                ping_count = 0
                while True:
                    await asyncio.sleep(1)
                    if channel.readyState == "open":
                        channel.send("Ping")
                        ping_count += 1
                        logging.debug(f"Sent Ping {ping_count}")
                    else:
                        logging.info("Channel no longer open, breaking loop")
                        break

                # Close the peer connection
                await pc.close()
                logging.info("Peer connection closed")
                break  # Exit the retry loop if successful
        except websockets.exceptions.ConnectionClosed as e:
            logging.error(f"WebSocket connection closed: {str(e)}")
        except socket.gaierror as e:
            logging.error(f"Network error: {str(e)}. Check your network connection and DNS settings.")
        except Exception as e:
            logging.error(f"Connection attempt {retry_count + 1} failed: {str(e)}")
        
        retry_count += 1
        if retry_count < max_retries:
            logging.info(f"Retrying in 5 seconds...")
            await asyncio.sleep(5)
        else:
            logging.error("Max retries reached. Unable to establish connection.")
            logging.info("Please check your network and firewall settings:")
            logging.info("- Ensure UDP traffic is allowed, especially on ports 1024-65535")
            logging.info("- If possible, test on a network without a firewall")
            logging.info("- Consider implementing a fallback to TCP if UDP is blocked")

if __name__ == "__main__":
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"
    logging.info(f"Starting script with URI: {uri}")
    asyncio.run(main(uri))
