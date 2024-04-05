''' 
we discovered that udp hole punching inside docker containers is not always 
possible because of the way the docker nat works. we thought it was.
this host script is meant to run on the host machine. 
it will establish a sse connection with the flask server running inside
the container. it will handle the UDP hole punching, passing data between the
flask server and the remote peers.
'''

# list to the flask server
# every message will have local port, remote ip, remote port, data
# if you don't have a connection then set one up, listen to it and send the data
# if you do have a connection then send the data
# as you're listening to all the connections, relay their info to flask.

from typing import Union, Dict, List, Tuple  # Python3.7 compatible
import ast
import socket
import asyncio
import datetime as dt
import aiohttp
import requests
import traceback
import json
# from requests_toolbelt.multipart.encoder import MultipartEncoder


def greyPrint(msg: str):
    return print(
        "\033[90m"  # grey
        + msg +
        "\033[0m"  # reset
    )


class SynergyMsg():
    def __init__(
        self,
        localPort: int,
        remotePort: int,
        remoteIp: str,
        data: Union[str, int, bytes, float, None],
    ):
        self.localPort = localPort
        self.remotePort = remotePort
        self.remoteIp = remoteIp
        self.data = data

    @staticmethod
    def fromJson(msg: bytes) -> 'SynergyMsg':
        return SynergyMsg(**json.loads(msg.decode() if isinstance(msg, bytes) else msg))

    def toJson(self):
        return json.dumps({
            'localPort': self.localPort,
            'remotePort': self.remotePort,
            'remoteIp': self.remoteIp,
            'data': self.data})


class SseTimeoutFailure(Exception):
    '''
    sometimes we the connection to the neuron fails and we want to identify 
    that failure easily with this custom exception so we can handle reconnect.
    '''

    def __init__(self, message='Sse timeout failure', extra_data=None):
        super().__init__(message)
        self.extra_data = extra_data

    def __str__(self):
        return f"{self.__class__.__name__}: {self.args[0]} (Extra Data: {self.extra_data})"


class UDPRelay():
    def __init__(self, ports: Dict[int, List[Tuple[str, int]]]):
        ''' {localport: [(remoteIp, remotePort)]} '''
        self.ports: Dict[int, List[Tuple[str, int]]] = ports
        self.socks: List[socket.socket] = []
        self.peerListeners = []
        self.neuronListeners = []
        self.loop = asyncio.get_event_loop()

    @staticmethod
    def satoriUrl(endpoint='') -> str:
        return 'http://localhost:24601/udp' + endpoint

    @property
    def listeners(self) -> list:
        return self.peerListeners + self.neuronListeners

    async def run(self):
        ''' runs forever '''
        self.initNeuronListener(UDPRelay.satoriUrl('/stream'))

        # call self.listen()? when first initialized I only need ot listen to
        # the 'neuron' which is the flask server. then it will tell me about
        # the peer connections I need to setup and listen to... so I want to
        # add udp connections and listen to them incremementally. so some
        # things about this script might have to change...
        # old code snippet
        # await self.initSockets()
        # try:
        #    secs = seconds()
        #    await asyncio.wait_for(udpRelay.listen(), secs)
        # except asyncio.TimeoutError:
        #    greyPrint('udpRelay cycling')
        # except SseTimeoutFailure:
        #    greyPrint("...attempting to reconnect to neuron...")
        # except Exception as e:
        #    greyPrint(f'An error occurred: {e}')
        #    traceback.print_exc()

    async def neuronListener(self, url: str):
        # timeout = aiohttp.ClientTimeout(total=None, sock_read=3600)
        timeout = aiohttp.ClientTimeout(total=None, sock_read=None)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    async for line in response.content:
                        if line.startswith(b'data:'):
                            self.relayToPeer(line.decode('utf-8')[5:].strip())
            except asyncio.TimeoutError:
                greyPrint("SSE connection timed out...")
                raise SseTimeoutFailure()

    def cancelNeuronListener(self):
        for listener in self.neuronListeners:
            listener.cancel()
        self.neuronListeners = []

    def initNeuronListener(self, url: str):
        if (len(self.neuronListeners) > 0):
            self.cancelNeuronListener()
        self.neuronListeners = [asyncio.create_task(self.neuronListener(url))]

    def relayToPeer(self, messages: str):
        def parseMessages() -> List[Tuple[int, str, int, bytes]]:
            ''' 
            parse messages into a 
            list of [tuples of (tuples of local port, and data)]
            '''
            try:
                literal: List[Tuple[int, str, int, bytes]] = (
                    ast.literal_eval(messages))
                if isinstance(literal, list) and len(literal) > 0:
                    return literal
            except Exception as e:
                greyPrint(f'unable to parse messages: {messages}, error: {e}')
            return []

        def parseMessage(msg) -> Tuple[int, str, int, bytes]:
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

        for msg in parseMessages():
            localPort, remoteIp, remotePort, data = parseMessage(msg)
            if localPort is None:
                return
            # greyPrint('parsed:',
            #      'localPort:', localPort, 'remoteIp:', remoteIp,
            #      'remotePort', remotePort, 'data', data)
            sock = self.getSocketByLocalPort(localPort)
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
                greyPrint(f'listenTo erorr: {e}')
                break
        # close?

    async def listenToConnection(self, sock: socket.socket):
        ''' this should be called from the flask server listener '''
        # Create a new listening task for the given socket
        new_listener_task = asyncio.create_task(self.listenTo(sock))

        # Add this new task to the list of peer listeners
        self.peerListeners.append(new_listener_task)

    # now I don't want to init all at once, I want to do it incrementally,
    # so maybe this has to change?
    async def initSockets(self):
        def bind(localPort: int) -> Union[socket.socket, None]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind(('0.0.0.0', localPort))
                sock.setblocking(False)
                return sock
            except Exception as e:
                greyPrint(f'unable to bind to port {localPort}, {e}')
            return None

        def punch(sock: socket.socket, remoteIp: str, remotePort: int):
            sock.sendto(b'punch', (remoteIp, remotePort))

        def createAllSockets():
            self.socks = []
            for localPort, remotes in self.ports.items():
                sock = bind(localPort)
                if sock is not None:
                    self.socks.append(sock)
                    for remoteIp, remotePort in remotes:
                        punch(sock, remoteIp, remotePort)

        createAllSockets()

    async def listen(self):
        self.initNeuronListener(UDPRelay.satoriUrl('/stream'))
        self.peerListeners += [
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
        greyPrint(f'sending to {remoteIp}:{remotePort} {data}')
        sock.sendto(data, (remoteIp, remotePort))

    async def cancel(self):
        ''' cancel all listen_to_socket tasks '''
        for task in self.peerListeners:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self.peerListeners = []

    async def shutdown(self):

        def close():
            ''' close all sockets '''
            for sock in self.socks:
                sock.close()

        await self.cancel()
        close()
        self.socks = []

    def handle(self, sock: socket.socket, data: bytes, addr: Tuple[str, int]):
        ''' send to flask server with identifying information '''
        greyPrint(
            f"Received {data} from {addr} on {UDPRelay.getLocalPort(sock)}")
        # # this isn't ideal because it converts data to a string automatically
        # r = requests.post(
        #    UDPRelay.satoriUrl('/message'),
        #    json={
        #        'data': data,
        #        'address': {
        #            'remote': {'ip': addr[0], 'port': addr[1]},
        #            'local': {'port': UDPRelay.getLocalPort(sock)}}})

        # # this is probably proper but requires an additional package
        # # and we want this to be as light as possible
        # multipart_data = MultipartEncoder(
        #    fields={
        #        # JSON part
        #        'json_data': ('json_data', '{"address": {"remote": {"ip": "' + addr[0] + '", "port": ' + str(addr[1]) + '}, "local": {"port": ' + UDPRelay.getLocalPort(sock) + '}}}', 'application/json'),
        #        # Byte data part
        #        'byte_data': ('filename', data, 'application/octet-stream')
        #    }
        # )
        # r = requests.post(
        #    UDPRelay.satoriUrl('/message'),
        #    data=multipart_data,
        #    headers={'Content-Type': multipart_data.content_type})
        if data in [b'punch', b'payload']:
            greyPrint('skipping punch or payload')
            return
        requests.post(
            UDPRelay.satoriUrl('/message'),
            data=data,
            headers={
                'Content-Type': 'application/octet-stream',
                'remoteIp': addr[0],
                'remotePort': str(addr[1]),
                'localPort': str(UDPRelay.getLocalPort(sock))})


async def main():

    async def waitForNeuron():
        notified = False
        while True:
            try:
                r = requests.get(UDPRelay.satoriUrl('/ping'))
                if r.status_code == 200:
                    if notified:
                        greyPrint('established connection to Satori Neuron')
                    return
            except Exception as _:
                if not notified:
                    greyPrint('waiting for Satori Neuron to start')
                    notified = True
            await asyncio.sleep(1)

    await waitForNeuron()
    udpRelay = UDPRelay()
    await udpRelay.run()

asyncio.run(main())
