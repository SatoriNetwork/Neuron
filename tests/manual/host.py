

# # just testing
# import asyncio
# import aiohttp


# class UDPRelay():

#     def __init__(self):
#         self.listeners = []
#         self.loop = asyncio.get_event_loop()

#     async def sseListener(self, url):
#         async with aiohttp.ClientSession() as session:
#             async with session.get(url) as response:
#                 async for line in response.content:
#                     if line.startswith(b"data:"):
#                         message = line.decode('utf-8')[5:].strip()
#                         print("SSE message:", message)
#                         # Process SSE message here

#     def initSseListener(self, url):
#         self.listeners.append(asyncio.create_task(self.sseListener(url)))

#     async def testListener(self):
#         for x in range(100):
#             await asyncio.sleep(1)
#             print("x:", x)

#     def initTestListener(self):
#         self.listeners.append(asyncio.create_task(self.testListener()))

#     async def listen(self):
#         self.initSseListener('http://localhost:24604/stream')
#         self.initTestListener()
#         return await asyncio.gather(*self.listeners)

#     async def shutdown(self):
#         ''' cancel all listen_to_socket tasks '''
#         print('shutting down')
#         for task in self.listeners:
#             task.cancel()
#             try:
#                 await task
#             except asyncio.CancelledError:
#                 pass

# async def main():
#     while True:
#         try:
#             udp_conns = UDPRelay()
#             try:
#                 await asyncio.wait_for(udp_conns.listen(), 60)
#             except asyncio.TimeoutError:
#                 print('Listen period ended. Proceeding to shutdown.')
#             print('cancelling')
#             await udp_conns.shutdown()
#             await asyncio.sleep(10)
#             # try:
#             #     await udp_conns.listen()
#             #     await asyncio.sleep(60)
#             # finally:
#             #     await udp_conns.shutdown()
#             #     await asyncio.sleep(10)
#         except Exception as e:
#             print(f"An error occurred: {e}")

# asyncio.run(main())

# ## server for testing
# from flask import Flask, Response, stream_with_context
# import time

# app = Flask(__name__)


# def event_stream():
#     count = 0
#     while True:
#         time.sleep(1)
#         count += 1
#         yield f"data: {count}\n\n"


# @app.route('/stream')
# def stream():
#     return Response(
#         stream_with_context(event_stream()),
#         content_type='text/event-stream')


# if __name__ == '__main__':
#     app.run('0.0.0.0', port=24604, debug=True)
