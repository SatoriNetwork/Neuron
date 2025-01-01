import asyncio
import json
import websockets

connected = set()

async def signaling(websocket, path):
    connected.add(websocket)
    print(f"New client connected. Total clients: {len(connected)}")
    
    try:
        async for message in websocket:
            try:
                # Parse the message and broadcast to other peers
                message_data = json.loads(message)
                print(f"Received message type: {message_data.get('type', 'unknown')}")
                
                # Broadcast the message to all other connected clients
                for conn in connected:
                    if conn != websocket:
                        await conn.send(message)
                        
            except json.JSONDecodeError:
                print("Error: Invalid JSON message received")
            except Exception as e:
                print(f"Error handling message: {str(e)}")
                
    except websockets.exceptions.ConnectionClosed:
        print("Client connection closed unexpectedly")
    finally:
        connected.remove(websocket)
        print(f"Client disconnected. Remaining clients: {len(connected)}")

start_server = websockets.serve(signaling, "0.0.0.0", 51820)

print("Starting signaling server on port 51820...")
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
