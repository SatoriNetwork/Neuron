''' 
we discovered that udp hole punching inside docker containers is not always 
possible. we thought it was.
this host script is meant to run on the host machine. 
it will establish a sse connection with the flask server running inside
the container. it will handle the UDP hole punching, passing data between the
flask server and the remote peers.
'''
import ast
import socket
import asyncio
import datetime as dt
import aiohttp
import requests


class UDPRelay():
    def __init__(self, ports: dict[int, list[tuple[str, int]]]):
        ''' {localport: [(remoteIp, remotePort)]} '''
        self.ports: dict[int, list[tuple[str, int]]] = ports
        self.socks: list[socket.socket] = []
        self.listeners = []
        self.loop = asyncio.get_event_loop()

    @staticmethod
    def satoriUrl(endpoint='') -> str:
        return 'http://localhost:24601/udp' + endpoint

    async def sseListener(self, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                async for line in response.content:
                    # print('line:', line)
                    if line.startswith(b'data:'):
                        self.relayToSocket(line.decode('utf-8')[5:].strip())

    def initSseListener(self, url: str):
        self.listeners.append(asyncio.create_task(self.sseListener(url)))

    def relayToSocket(self, messages: str):
        def parseMessages() -> list[tuple[int, str, int, bytes]]:
            ''' 
            parse messages into a 
            list of [tuples of (tuples of local port, and data)]
            '''
            try:
                literal: list[tuple[int, str, int, bytes]] = (
                    ast.literal_eval(messages))
                if isinstance(literal, list) and len(literal) > 0:
                    return literal
            except Exception as e:
                print(f'unable to parse messages: {messages}, error: {e}')
            return []

        def parseMessage(msg) -> tuple[int, str, int, bytes]:
            ''' localPort, remoteIp, remotePort, data '''
            if (
                isinstance(msg, tuple) and
                len(msg) == 4 and
                isinstance(msg[0], int) and
                isinstance(msg[1], str) and
                isinstance(msg[2], int) and
                isinstance(msg[3], bytes)
            ):
                return msg[0], msg[1], msg[2], msg[3]
            return None, None, None, None

        # print("SSE messages:", messages)
        for msg in parseMessages():
            localPort, remoteIp, remotePort, data = parseMessage(msg)
            if localPort is None:
                return
            # print('parsed:',
            #      'localPort:', localPort, 'remoteIp:', remoteIp,
            #      'remotePort', remotePort, 'data', data)
            sock = self.getSocketByLocalPort(localPort)
            # print('socket found:', sock, sock.getsockname())
            if sock is None:
                return
            UDPRelay.speak(sock, remoteIp, remotePort, data)

    def getSocketByLocalPort(self, localPort: int) -> socket.socket:
        for sock in self.socks:
            if UDPRelay.getLocalPort(sock) == localPort:
                return sock
        return None

    @staticmethod
    def getLocalPort(sock: socket.socket) -> int:
        return sock.getsockname()[1]

    async def listenTo(self, sock: socket.socket):
        while True:
            try:
                data, addr = await self.loop.sock_recvfrom(sock, 1024)
                self.handle(sock, data, addr)
            except Exception as e:
                print('listenTo erorr:', e)
                break
        # close?

    async def initSockets(self):
        def bind(localPort: int) -> socket.socket | None:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind(('0.0.0.0', localPort))
                sock.setblocking(False)
                return sock
            except Exception as e:
                print('unable to bind to port', localPort, e)
            return None

        def punch(sock: socket.socket, remoteIp: str, remotePort: int):
            sock.sendto(b'punch', (remoteIp, remotePort))

        def createAllSockets():
            self.socks = []
            for localPort, remotes in self.ports.items():
                # print('creating socket for port', localPort)
                sock = bind(localPort)
                if sock is not None:
                    self.socks.append(sock)
                    for remoteIp, remotePort in remotes:
                        punch(sock, remoteIp, remotePort)

        createAllSockets()

    async def listen(self):
        self.initSseListener(UDPRelay.satoriUrl('/stream'))
        self.listeners += [
            asyncio.create_task(self.listenTo(sock))
            for sock in self.socks]
        return await asyncio.gather(*self.listeners)

    @staticmethod
    def speak(
        sock: socket.socket,
        remoteIp: str,
        remotePort: int,
        data: bytes
    ):
        # print('speaking to', remoteIp, remotePort, data)
        sock.sendto(data, (remoteIp, remotePort))

    async def cancel(self):
        ''' cancel all listen_to_socket tasks '''
        for task in self.listeners:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def shutdown(self):

        def close():
            ''' close all sockets '''
            for sock in self.socks:
                sock.close()

        await self.cancel()
        close()

    def handle(self, sock: socket.socket, data: bytes, addr: tuple[str, int]):
        ''' send to flask server with identifying information '''
        # print(f"Received {data} from {addr} on {UDPRelay.getLocalPort(sock)}")
        requests.post(
            UDPRelay.satoriUrl('/message'),
            json={
                'data': data,
                'address': {
                    'remote': {'ip': addr[0], 'port': addr[1]},
                    'local': {'port': UDPRelay.getLocalPort(sock)}}})


async def main():
    def seconds() -> float:
        ''' calculate number of seconds until the start of the next hour'''
        now = dt.datetime.now()
        nextHour = (now + dt.timedelta(hours=1)).replace(
            minute=0,
            second=0,
            microsecond=0)
        return (nextHour - now).total_seconds()

    def getPorts() -> dict[int, list[tuple[str, int]]]:
        ''' gets ports from the flask server '''
        r = requests.get(UDPRelay.satoriUrl('/ports'))
        # print(r.status_code)
        # print(r.text)
        if r.status_code == 200:
            try:
                ports: dict = ast.literal_eval(r.text)
                validatedPorts = {}
                # print(ports)
                # print('---')
                for localPort, remotes in ports.items():
                    # print(localPort, remotes)
                    if (
                        isinstance(localPort, int) and
                        isinstance(remotes, list)
                    ):
                        # print('valid')
                        validatedPorts[localPort] = []
                        # print(validatedPorts)
                        for remote in remotes:
                            # print('remote', remote)
                            if (
                                isinstance(remote, tuple) and
                                len(remote) == 2 and
                                isinstance(remote[0], str) and
                                isinstance(remote[1], int)
                            ):
                                # print('valid---')
                                validatedPorts[localPort].append(remote)
                return validatedPorts
            except (ValueError, TypeError):
                print("Invalid format of received data")
                return {}
        return {}

    while True:
        try:
            udpRelay = UDPRelay(getPorts())
            await udpRelay.initSockets()
            try:
                await asyncio.wait_for(udpRelay.listen(), seconds())
            except asyncio.TimeoutError:
                print('udpRelay cycling')
            await udpRelay.shutdown()
        except Exception as e:
            await udpRelay.shutdown()
            print(f"An error occurred: {e}")


asyncio.run(main())
