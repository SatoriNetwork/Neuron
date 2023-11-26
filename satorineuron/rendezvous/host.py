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
    # incorrect assumption: localPorts have only one remote port.
    # that's not right. localports are by topic.
    # they can have multple ports that they interface with.
    # perhaps I need to reverse this {remotePort: (remoteIp, localport)}?
    # or is a listgood enough: {localPort: [(remoteIp, remotePort)]}
    # I could do that if I don't have to get remote by local.
    def __init__(self, ports: dict[int, list[tuple[str, int]]]):
        # {localport: (remoteIp, remotePort)}
        self.ports: dict[int, list[tuple[str, int]]] = ports
        self.socks: list[socket.socket] = []
        self.listeners = []
        self.loop = asyncio.get_event_loop()

    async def sseListener(self, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                async for line in response.content:
                    if line.startswith(b"data:"):
                        messages = line.decode('utf-8').strip()
                        self.relayToSocket(messages)

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
                    len(msg) == 4
                    and isinstance(msg[0], int)
                    and isinstance(msg[1], str)
                    and isinstance(msg[2], int)
                    and isinstance(msg[3], bytes)):
                return msg[0], msg[1], msg[2], msg[3]
            return None, None, None, None

        # print("SSE messages:", messages)
        for msg in parseMessages():
            localPort, remoteIp, remotePort, data = parseMessage(msg)
            if localPort is None:
                return
            sock = self.getSocketByLocalPort(localPort)
            if sock is None:
                return
            self.speak(sock, remoteIp, remotePort, data)

    def getSocketByLocalPort(self, localPort: int) -> socket.socket:
        for sock in self.socks():
            if self.getLocalPort(sock) == localPort:
                return sock
        return None

    @staticmethod
    def getLocalPort(sock: socket.socket) -> int:
        return sock.getsockname()[1]

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
            # sock.remoteIp = remoteIp
            # sock.remotePort = remotePort
            sock.sendto(b'punch', (remoteIp, remotePort))
            return sock

        def createAllSockets():
            for localPort, remotes in self.ports:
                sock = bind(localPort)
                for remoteIp, remotePort in remotes:
                    self.socks.append(punch(sock, remoteIp, remotePort))

        createAllSockets()

    async def listen(self):
        self.initSseListener(f'{satoriUrl}/stream')
        self.listeners += [
            asyncio.create_task(self.listenTo(sock))
            for sock in self.socks]
        return await asyncio.gather(*self.listeners)

    def speak(
        self,
        sock: socket.socket,
        remoteIp: str,
        remotePort: int,
        data: bytes
    ):
        sock.sendto(data, (remoteIp, remotePort))

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
                'data': data,
                'address': {
                    'remote': {'ip': addr[0], 'port': addr[1]},
                    'local': {'port': UDPRelay.getLocalPort(sock)}}})


async def main():
    def seconds() -> float:
        ''' calculate number of seconds until the start of the next hour'''
        now = dt.datetime.now()
        next_hour = (now + dt.timedelta(hours=1)).replace(
            minute=0,
            second=0,
            microsecond=0)
        return (next_hour - now).total_seconds()

    def getPorts() -> dict[int, list[tuple[str, int]]]:
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
