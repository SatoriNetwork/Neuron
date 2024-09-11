# webrtc_peer.py
import sys
import asyncio
import websockets
import tracemalloc
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel, RTCIceCandidate, RTCConfiguration, RTCIceServer

# # Enable tracemalloc to get detailed memory allocation traceback
# tracemalloc.start()

# async def send_offer(websocket):
#     # Create a WebRTC connection
#     # pc = RTCPeerConnection()
#      # Create a WebRTC configuration
#     config = RTCConfiguration(
#         iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
#     )

#     # Create a WebRTC connection with the configuration
#     pc = RTCPeerConnection(configuration=config)

#     # pc.addIceCandidate({'urls': ['stun:stun.l.google.com:19302']})
#     # pc.addIceServer('stun:stun.l.google.com:19302')



#     # Create a data channel
#     channel = pc.createDataChannel("chat")

#     # Define the on_open event handler
#     @channel.on("open")
#     def on_open():
#         print("Data channel is open")
#         channel.send("Hello World")

#     @channel.on("message")
#     def on_message(message):
#         print(f"Received message: {message}")

#     # # Sending a message over the data channel
#     # @channel.on("open")
#     # def on_open():
#     #     channel.send("Hello from peer")

#     # Create an SDP offer
#     offer = await pc.createOffer()
#     await pc.setLocalDescription(offer)

#      # Print the SDP offer for debugging
#     # print("SDP Offer:\n", pc.localDescription.sdp)

#     # Send the SDP offer via WebSocket to the signaling server
#     await websocket.send(pc.localDescription.sdp)

#     # Wait for the SDP answer
#     answer_sdp = await websocket.recv()
#     answer_sdp = answer_sdp.replace("a=setup:actpass", "a=setup:active")  # Modify the SDP answer
#     answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

#      # Print the SDP answer for debugging
#     # print("SDP Answer:\n", answer.sdp)

#     # Validate the SDP answer
#     if "a=setup:active" not in answer.sdp and "a=setup:passive" not in answer.sdp:
#         raise ValueError("DTLS setup attribute must be 'active' or 'passive' for an answer")

#     await pc.setRemoteDescription(answer)

#     # Handle ICE candidate exchange here if needed (for now, we can skip)
#     # RTCIceCandidate()
    
   
#     return pc


# async def main(uri: str = "ws://localhost:8765"):
#     # Connect to the WebSocket signaling server
#     async with websockets.connect(uri) as websocket:
#         await send_offer(websocket)

# if __name__ == "__main__":
#     asyncio.run(main(
#         uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))

async def send_offer(websocket):
    # Create a WebRTC configuration
    config = RTCConfiguration(
        iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
    )

    # Create a WebRTC connection with the configuration
    pc = RTCPeerConnection(configuration=config)

    # Create a data channel
    channel = pc.createDataChannel("chat")
    print("Data channel created")

    @channel.on("open")
    def on_open():
        print("Data channel is open")
        channel.send("Hello World")
        print("Sent: Hello World")

    @channel.on("message")
    def on_message(message):
        print(f"Received message: {message}")

    @pc.on("datachannel")
    def on_datachannel(channel):
        print(f"New data channel: {channel.label}")

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        print(f"Connection state is {pc.connectionState}")
        if pc.connectionState == "connected":
            await asyncio.sleep(1)
            if channel.readyState == "open":
                channel.send("Delayed Hello World")
                print("Sent delayed message")

    # Create an SDP offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    # Send the SDP offer via WebSocket to the signaling server
    await websocket.send(pc.localDescription.sdp)
    print("Sent local description")

    # Wait for the SDP answer
    answer_sdp = await websocket.recv()
    print("Received remote description")
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

    await pc.setRemoteDescription(answer)
    print("Set remote description")

    # Keep the connection alive
    while True:
        await asyncio.sleep(1)

async def main(uri: str = "ws://localhost:8765"):
    async with websockets.connect(uri) as websocket:
        await send_offer(websocket)

if __name__ == "__main__":
    asyncio.run(main(
        uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))