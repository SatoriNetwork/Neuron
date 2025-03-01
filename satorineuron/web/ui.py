'''
unused - replaced with flask-socketio
this is the websocket connection we use to update the ui for immedate updates
'''

import asyncio
import websockets
import json

connected_clients = set()  # Store all connected frontend clients

async def frontend_handler(websocket, path):
    """Handles WebSocket connections from the frontend."""
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received from frontend: {message}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        connected_clients.remove(websocket)

async def broadcast_update(data):
    """Send updates to all connected frontend clients."""
    if connected_clients:
        message = json.dumps({"value": data})
        await asyncio.gather(*[client.send(message) for client in connected_clients])

async def run_websocket_server():
    """Run the WebSocket server that serves the frontend."""
    server = await websockets.serve(frontend_handler, "0.0.0.0", 8765)
    await server.wait_closed()
