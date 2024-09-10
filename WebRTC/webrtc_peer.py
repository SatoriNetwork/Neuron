import asyncio 
import websockets 
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCDataChannel 

async def send_offer(websocket): 
    # Create a WebRTC connection
    pc = RTCPeerConnection() 

    # Add STUN server (Google's public one)
    pc.addIceServer({'urls': 'stun:stun.l.google.com:19302'})

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

    # Create an SDP offer 
    offer = await pc.createOffer() 
    await pc.setLocalDescription(offer) 

    # Send the SDP offer via WebSocket to the signaling server 
    await websocket.send(pc.localDescription.sdp)

     # Wait for the SDP
    answer_sdp = await websocket.recv() 
    answer = RTCSessionDescription(sdp=answer_sdp, type="answer") 
    await pc.setRemoteDescription(answer)

     # Handle ICE candidate exchange here if needed (for now,we can skip) 
    return pc 

async def main():    
    # Connect to the WebSocket signaling server 
    uri= "ws://localhost:8765" 
    async with websockets.connect(uri) as websocket: 
        await send_offer(websocket)

#Run the main function
asyncio.run(main())
    