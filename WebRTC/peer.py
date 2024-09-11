# webrtc_peer.py
import sys
import asyncio
import websockets
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCIceCandidate


async def send_offer(websocket):
    # Create a WebRTC connection
    pc = RTCPeerConnection()

    # Create a data channel
    channel = pc.createDataChannel("chat")

    # Define the on_open event handler
    @channel.on("open")
    def on_open():
        print("Data channel is open")
        channel.send("Hello from peer")

    @channel.on("message")
    def on_message(message):
        print(f"Received message: {message}")

    # # Sending a message over the data channel
    # @channel.on("open")
    # def on_open():
    #     channel.send("Hello from peer")

    # Create an SDP offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

     # Print the SDP offer for debugging
    # print("SDP Offer:\n", pc.localDescription.sdp)
    print("SDP Offer:\n",offer.sdp)

    # Send the SDP offer via WebSocket to the signaling server
    await websocket.send(pc.localDescription.sdp)

    # Wait for the SDP answer
    answer_sdp = await websocket.recv()
    answer_sdp = answer_sdp.replace("a=setup:actpass", "a=setup:active")  # Modify the SDP answer
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

     # Print the SDP answer for debugging
    print("SDP Answer:\n", answer.sdp)

    # Validate the SDP answer
    if "a=setup:active" not in answer.sdp and "a=setup:passive" not in answer.sdp:
        raise ValueError("DTLS setup attribute must be 'active' or 'passive' for an answer")

    await pc.setRemoteDescription(answer)

    # Handle ICE candidate exchange here if needed (for now, we can skip)
    ice_candidate = RTCIceCandidate(
        component=1,
        foundation="1",
        ip="172.17.0.2",
        port=52206,
        priority=2130706431,
        protocol="udp",
        type="host",
        sdpMid="0",
        sdpMLineIndex=0,
        candidate="9333c84bcc1b0bf56713df9036e6b4d9 1 udp 2130706431 172.17.0.2 52206 typ host"
    )

    # Add STUN server (Google's public one)
    await pc.addIceCandidate(ice_candidate)  # Await the coroutine

    pc.addIceCandidate({
        'urls': ['stun:stun.l.google.com:19302']
    })

    return pc


async def main(uri: str = "ws://localhost:8765"):
    # Connect to the WebSocket signaling server
    async with websockets.connect(uri) as websocket:
        await send_offer(websocket)

if __name__ == "__main__":
    asyncio.run(main(
        uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))
