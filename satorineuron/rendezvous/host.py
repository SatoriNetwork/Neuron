''' 
we discovered that udp hole punching inside docker containers is not possible.
we thought it was.
this host script is meant to run on the host machine. 
it will establish a sse connection with the flask server running inside
the container. it will handle the UDP hole punching, passing data between the
flask server and the remote peers.
'''
import socket
import asyncio
import datetime as dt
import aiohttp


class UDPRelay():

    def __init__(self, ports: dict[int, tuple[str, int]]):
        # {localport: (remoteIp, remotePort)}
        self.ports: dict[int, tuple[str, int]] = ports
        self.socks: list[socket.socket] = []
        self.listeners = []
        self.loop = asyncio.get_event_loop()

    async def sseListener(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                async for line in response.content:
                    if line.startswith(b"data:"):
                        message = line.decode('utf-8')[5:].strip()
                        print("SSE message:", message)
                        # Process SSE message here

    def initSseListener(self, url):
        self.listeners.append(asyncio.create_task(self.sseListener(url)))

    # this should be done at higher level
    # async def runForever(self):
        # self.loop.run_until_complete(self.main())
        # asyncio.run(udp_conns.main())

    @staticmethod
    def getLocalPort(sock: socket.socket) -> int:
        return sock.getsockname()[1]

    def getRemotePort(self, sock: socket.socket) -> int:
        if hasattr(sock, 'remotePort'):
            return sock.remotePort
        port = sock.getsockname()[1]
        if port is None:
            return -1
        return self.getRemotePortByPort(port)

    def getRemotePortByPort(self, port: int) -> int:
        return self.getRemoteIpAndPortByPort(port)[1]

    def getRemoteIp(self, sock: socket.socket) -> str:
        if hasattr(sock, 'remoteIp'):
            return sock.remoteIp
        port = sock.getsockname()[1]
        if port is None:
            return ''
        return self.getRemoteIpByPort(port)

    def getRemoteIpByPort(self, port: int) -> str:
        return self.getRemoteIpAndPortByPort(port)[0]

    def getRemoteIpAndPortByPort(self, port: int) -> tuple[str, int]:
        return self.ports.get(port, ('', -1))

    async def listenTo(self, sock: socket.socket):
        while True:
            # recvfrom = udp
            data, addr = await self.loop.sock_recvfrom(sock, 1024)
            self.handle(sock, data, addr)

    async def initSockets(self):
        def bind(localPort: int) -> socket.socket:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind(('0.0.0.0', localPort))
            sock.setblocking(False)
            return sock

        def punch(
            sock: socket.socket,
            remoteIp: str,
            remotePort: int
        ) -> socket.socket:
            sock.remoteIp = remoteIp
            sock.remotePort = remotePort
            sock.sendto(b'punch', (remoteIp, remotePort))
            return sock

        def createAllSockets():
            for k, v in self.ports:
                self.socks.append(punch(bind(k), *v))

        createAllSockets()

    async def listen(self):
        self.initSseListener('http://localhost:24601/stream')
        self.listeners += [
            asyncio.create_task(self.listenTo(sock))
            for sock in self.socks]
        return await asyncio.gather(*self.listeners)

    async def shutdown(self):
        async def cancel():
            ''' cancel all listen_to_socket tasks '''
            for task in self.listeners:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        def close():
            ''' close all sockets '''
            for sock in self.socks:
                sock.close()

        await cancel()
        close()

    def handle(self, sock: socket.socket, data: bytes, addr: tuple[str, int]):
        ''' send to flask server with identifying information '''
        print(
            f"Received data: {data} from {addr} on port {UDPRelay.getLocalPort(sock)}")
        # TODO: send to flask server over http request


async def main():
    def seconds() -> float:
        ''' calculate number of seconds until the start of the next hour'''
        now = dt.datetime.now()
        next_hour = (now + dt.timedelta(hours=1)).replace(
            minute=0,
            second=0,
            microsecond=0)
        return (next_hour - now).total_seconds()

    def getPorts() -> dict[int, tuple[str, int]]:
        ''' gets ports from the flask server '''
        # TODO: get ports from flask server over http request
        return {}

    newPorts = getPorts()
    ports = newPorts
    while True:
        try:
            udp_conns = UDPRelay(ports)
            await udp_conns.initSockets()
            try:
                await asyncio.wait_for(udp_conns.listen(), seconds())
            except asyncio.TimeoutError:
                print('Listen period ended. Proceeding to shutdown.')
            await udp_conns.shutdown()
        except Exception as e:
            print(f"An error occurred: {e}")


asyncio.run(main())


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
