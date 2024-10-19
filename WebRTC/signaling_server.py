# signaling_server.py
import asyncio
import websockets

connected = set()


async def signaling(websocket, path):
    connected.add(websocket)
    try:
        async for message in websocket:
            # Broadcast the received message to all connected peers
            for conn in connected:
                if conn != websocket:
                    await conn.send(message)
    finally:
        connected.remove(websocket)

start_server = websockets.serve(signaling, "0.0.0.0", 51820)

asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()

