import asyncio
import websockets
 
async def test():
    async with websockets.connect('ws://localhost:8000') as websocket:
        await websocket.send("hello")
        response = await websocket.recv()
        print(response)

async def test1():
    async for websocket in websockets.connect('ws://localhost:8000'):
        try:
            await websocket.send("hello")
            response = await websocket.recv()
            print(response)
        except websockets.ConnectionClosed:
            print('done');
            continue

async def test2():
    async with websockets.connect('ws://localhost:8000') as websocket:
        try:
            await websocket.send("hello")
            response = await websocket.recv()
            print(response)
        except websockets.ConnectionClosed:
            print('done');

#asyncio.get_event_loop().run_until_complete(test2())
#asyncio.get_event_loop().run_forever()

def test3():
    import websocket
    ws = websocket.WebSocket()
    ws.connect('ws://localhost:8000')
    print(ws.connected)
    ws.send('hello')
    print(ws.connected)
    response = ws.recv()
    print(response)
    import time
    time.sleep(10)
    ws.recv()
    print(ws.connected)
    ws.close()
 
test3()
