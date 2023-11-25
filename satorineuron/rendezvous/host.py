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


localUrl = 'http://localhost'
satoriPort = 24601
satoriUrl = f'{localUrl}:{satoriPort}/udp'


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
                        messages = line.decode('utf-8')[5:].strip()
                        self.relayToSocket(messages)

    def initSseListener(self, url):
        self.listeners.append(asyncio.create_task(self.sseListener(url)))

    def relayToSocket(self, messages: str):
        # def parseMessages() -> list[tuple[tuple[str, int], object]]: # we might not need to include ip...
        # we might not need to include ip...
        def parseMessages() -> list[tuple[int, bytes]]:
            ''' 
            parse messages into a 
            list of [tuples of (tuples of local port, and data)]
            '''
            literal: list[tuple[int, bytes]] = ast.literal_eval(messages)
            if (
                not isinstance(literal, list)
                or len(literal) == 0
                or not isinstance(literal[0], tuple)
                or not isinstance(literal[0][0], tuple)
                or not isinstance(literal[0][0][0], int)
                or not isinstance(literal[0][0][1], bytes)
            ):
                return []
            return literal

        def parseMessage(msg) -> tuple[int, bytes]:
            return msg[0], msg[1]

        # print("SSE messages:", messages)
        for msg in parseMessages():
            localPort, data = parseMessage(msg)
            if localPort is None:
                return
            sock = self.getSocketByLocalPort(localPort)
            if sock is None:
                return
            self.speak(sock=sock, data=data)

    def getSocketByLocalPort(self, localPort: int) -> socket.socket:
        for sock in self.socks():
            if self.getLocalPort(sock) == localPort:
                return sock
        return None

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
        self.initSseListener(f'{satoriUrl}/stream')
        self.listeners += [
            asyncio.create_task(self.listenTo(sock))
            for sock in self.socks]
        return await asyncio.gather(*self.listeners)

    def speak(self, sock: socket.socket, data: bytes):
        sock.sendto(data, (self.getRemoteIp(sock), self.getRemotePort(sock)))

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
        # print(f"Received {data} from {addr} on {UDPRelay.getLocalPort(sock)}")
        requests.post(
            f'{satoriUrl}/message',
            json={
                'data': data.decode(),
                'address': {
                    'listen': {'ip': addr[0], 'port': addr[1]},
                    'speak': {'port': UDPRelay.getLocalPort(sock)}}})


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
        r = requests.get(f'{satoriUrl}/ports')
        if r.status_code == 200:
            try:
                ports_data: dict = r.json()
                validated_ports = {}
                for key, value in ports_data.items():
                    if isinstance(key, int) and isinstance(value, list) and len(value) == 2:
                        validated_ports[key] = tuple(value)
                return validated_ports
            except (ValueError, TypeError):
                print("Invalid format of received data")
                return {}
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
