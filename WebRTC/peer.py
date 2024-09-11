# # webrtc_peer.py
# import sys
# import asyncio
# import websockets
# import tracemalloc
# from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
# # import logging

# # Enable tracemalloc to get detailed memory allocation traceback
# tracemalloc.start()
# # logging.basicConfig(level=logging.DEBUG)

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
    
#     # @channel.on("close")
#     # def on_close():
#     #     logging.info("Data channel is closed")

#     # @channel.on("error")
#     # def on_error(error):
#     #     logging.error(f"Data channel error: {error}")

#     @channel.on("message")
#     def on_message(message):
#         print(f"Received message: {message}")

#     # @pc.on("connectionstatechange")
#     # async def on_connectionstatechange():
#     #     logging.info(f"Connection state is {pc.connectionState}")
#     #     if pc.connectionState == "failed":
#     #         await pc.close()
#     #         logging.error("Connection failed, closing peer connection")


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
    
   
#     # return pc
#     while True:
#         await asyncio.sleep(1)


# async def main(uri: str = "ws://localhost:8765"):
#     # Connect to the WebSocket signaling server
#     async with websockets.connect(uri) as websocket:
#         pc = await send_offer(websocket)
#         try:
#             # Keep the main coroutine running
#             await asyncio.Future()
#         finally:
#             # Close the peer connection when the program exits
#             await pc.close()

# if __name__ == "__main__":
#     asyncio.run(main(
#         uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))
import sys
import asyncio
import websockets
import tracemalloc
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, RTCConfiguration, RTCIceServer

# Enable tracemalloc to get detailed memory allocation traceback
tracemalloc.start()

async def send_offer(websocket):
    # WebRTC configuration with STUN server
    config = RTCConfiguration(iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])])
    pc = RTCPeerConnection(configuration=config)

    # Create a data channel
    channel = pc.createDataChannel("chat")

    # Define the on_open event handler
    @channel.on("open")
    def on_open():
        print("Data channel is open")
        channel.send("Hello World")

    # Define the on_message event handler
    @channel.on("message")
    def on_message(message):
        print(f"Received message: {message}")

    # Log ICE connection state changes
    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        print(f"ICE connection state is {pc.iceConnectionState}")
        if pc.iceConnectionState == "failed":
            await pc.close()
            print("Connection failed, peer connection closed.")

    # Create an SDP offer
    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)
    print("SDP Offer created and sent to signaling server")

    # Send the SDP offer via WebSocket to the signaling server
    await websocket.send(pc.localDescription.sdp)

    # Wait for the SDP answer
    print("Waiting for SDP answer from signaling server...")
    answer_sdp = await websocket.recv()

    # Optional: Modify SDP answer (based on your original code)
    answer_sdp = answer_sdp.replace("a=setup:actpass", "a=setup:active")
    print(f"Received SDP Answer:\n{answer_sdp}")
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer")

    # Validate the SDP answer
    if "a=setup:active" not in answer.sdp and "a=setup:passive" not in answer.sdp:
        raise ValueError("DTLS setup attribute must be 'active' or 'passive' for an answer")

    await pc.setRemoteDescription(answer)

    # Handle ICE candidate exchange (this was previously skipped)
    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            print(f"New ICE candidate found: {candidate}")
            await websocket.send(candidate.to_sdp())

    return pc

async def main(uri: str = "ws://localhost:8765"):
    # Connect to the WebSocket signaling server
    async with websockets.connect(uri) as websocket:
        print("Connected to signaling server")
        pc =await send_offer(websocket)
        try:
            # Keep the main coroutine running
            await asyncio.Future()
        finally:
            # Close the peer connection when the program exits
            await pc.close()

if __name__ == "__main__":
    asyncio.run(main(uri=sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"))
