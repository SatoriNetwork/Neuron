# Putty container (server)
import websockets
import asyncio

async def handle_connection(websocket):
    # Receive message
    message = await websocket.recv()
    print(f"Received from Windows: {message}")
    # Send response back
    await websocket.send("Hello back from Putty")

async def start_server():
    async with websockets.serve(handle_connection, "0.0.0.0", 8765):
        await asyncio.Future()  # run forever

if __name__ == "__main__":
    asyncio.run(start_server())