import asyncio
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCConfiguration, RTCIceServer
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

async def send_offer(websocket):
    logging.info("Starting send_offer function")
    # Create a WebRTC configuration with STUN server
    config = RTCConfiguration([
        RTCIceServer(urls='stun:stun.l.google.com:19302')
    ])
    # Create a WebRTC connection with the configuration
    pc = RTCPeerConnection(configuration=config)
    logging.debug("RTCPeerConnection created with STUN server")

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

    # Create an SDP offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    logging.debug("Local description set")

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

    # Handle ICE candidate exchange here if needed (for now, we can skip)
    logging.info("send_offer function completed")
    return pc, channel

async def main(uri = "ws://localhost:8765"):
    logging.info(f"Starting main function with URI: {uri}")
    # Connect to the WebSocket signaling server
    async with websockets.connect(uri) as websocket:
        logging.info("Connected to WebSocket signaling server")
        pc, channel = await send_offer(websocket)
        
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

if __name__ == "__main__":
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"
    logging.info(f"Starting script with URI: {uri}")
    asyncio.run(main(uri))
