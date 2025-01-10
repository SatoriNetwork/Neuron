# Windows container (client)
import websockets
import asyncio

async def connect_to_putty():
    async with websockets.connect('ws://localhost:8765') as websocket:
        # Send message
        await websocket.send("Hello from Windows")
        # Receive response
        response = await websocket.recv()
        print(f"Received from Putty: {response}")

if __name__ == "__main__":
    asyncio.run(connect_to_putty())