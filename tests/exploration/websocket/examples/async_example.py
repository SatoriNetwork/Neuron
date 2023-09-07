import asyncio
import websockets

async def init_sma_ws():
    uri = 'ws://localhost:8000'
    async with websockets.connect(uri) as websocket:
        while True:
            name = input("What's your name? ")
            if name == 'exit':
                break

            await websocket.send(name)
            print('Response:', await websocket.recv())


asyncio.run(init_sma_ws())