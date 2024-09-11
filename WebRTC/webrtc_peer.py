import asyncio
import json
from aiortc import RTCPeerConnection, RTCSessionDescription

class ManualSignalingPeer:
    def __init__(self):
        self.pc = RTCPeerConnection()
        self.pc.add_ice_server('stun:stun.l.google.com:19302')  # Updated method name
        self.dc = self.pc.createDataChannel("chat")
        
        @self.dc.on("open")
        def on_open():
            print("Data channel is open")
        
        @self.dc.on("message")
        def on_message(message):
            print(f"Received: {message}")

    async def create_offer(self):
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        return self.pc.localDescription.sdp

    async def set_remote_description(self, sdp):
        await self.pc.setRemoteDescription(RTCSessionDescription(sdp=sdp, type="answer"))

    async def create_answer(self, offer_sdp):
        offer = RTCSessionDescription(sdp=offer_sdp, type="offer")
        await self.pc.setRemoteDescription(offer)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        return self.pc.localDescription.sdp

    def send_message(self, message):
        self.dc.send(message)

async def main():
    peer = ManualSignalingPeer()
    
    # For the offering peer
    offer = await peer.create_offer()
    print("Offer SDP:")
    print(json.dumps(offer))
    
    # For the answering peer (on another machine)
    # Paste the offer SDP here
    remote_offer = input("Enter the remote offer SDP: ")
    answer = await peer.create_answer(remote_offer)
    print("Answer SDP:")
    print(json.dumps(answer))
    
    # Back on the offering peer
    # Paste the answer SDP here
    remote_answer = input("Enter the remote answer SDP: ")
    await peer.set_remote_description(remote_answer)
    
    # Now the connection should be established
    while True:
        message = input("Enter a message to send (or 'quit' to exit): ")
        if message.lower() == 'quit':
            break
        peer.send_message(message)
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())