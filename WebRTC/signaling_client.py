import asyncio
import websockets

async def websocket_client():
       uri = "ws://localhost:8000"  # Replace with your WebSocket server address

       async with websockets.connect(uri) as websocket:
           # Send a message to the server
           await websocket.send("Hello from client!")
           print("Message sent to server!")

           # Wait for a response from the server
           response = await websocket.recv()
           print(f"Received from server: {response}")

   # Run the WebSocket client
asyncio.get_event_loop().run_until_complete(websocket_client())
