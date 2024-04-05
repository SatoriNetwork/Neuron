''' 
we discovered that udp hole punching inside docker containers is not always 
possible because of the way the docker nat works. we thought it was.
this host script is meant to run on the host machine. 
it will establish a sse connection with the flask server running inside
the container. it will handle the UDP hole punching, passing data between the
flask server and the remote peers.

this is an extremely simplified version, using one socket, 24600 to perform all
the communication, what would be ideal is to make this script merely a executor
that will look into the the location on disk where we keep this code and execute
it. that way we don't have to rebuild and redownload the installer each time we
modify the p2p communiction protocol. we'd probably want to check the code's 
hash against the server in order to do that safely.
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
    def __init__(self, ip: str, data: Union[str, int, bytes, float, None]):
        # we can save this in the database on checkin -
        # and provide it for publisher, and have no need for the synergy server
        # whatsoever... well... not so, because we need to connect to each other
        # at nearly the same time... so it does have to be coordinated and on
        # demand.
        self.ip = ip
        self.data = data

    @staticmethod
    def fromJson(msg: bytes) -> 'SynergyMsg':
        return SynergyMsg(**json.loads(msg.decode() if isinstance(msg, bytes) else msg))

    def toJson(self):
        return json.dumps({
            'ip': self.ip,
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
    ''' go-between for the flask server and the remote peers '''

    PORT = 24600

    def __init__(self):
        self.socketListener = None
        self.neuronListener = None
        self.peers: List[str] = []
        # tell the neuron what port we choose.
        # no we only make one so its hard coded.
        self.socket: socket.socket = self.createSocket()
        self.loop = asyncio.get_event_loop()

    @staticmethod
    def satoriUrl(endpoint='') -> str:
        return 'http://localhost:24601/udp' + endpoint

    def speak(
        self,
        remoteIp: str,
        remotePort: int,
        data: bytes
    ):
        greyPrint(f'sending to {remoteIp}:{remotePort} {data}')
        self.socket.sendto(data, (remoteIp, remotePort))

    def createSocket(self) -> Tuple[int, socket.socket]:
        def bind(localPort: int) -> Union[socket.socket, None]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind(('0.0.0.0', localPort))
                sock.setblocking(False)
                return sock
            except Exception as e:
                greyPrint(f'unable to bind to port {localPort}, {e}')
                raise Exception('unable to create socket')

        # this would be helpful if we allowed everyone to use a different port.
        # but in order to do that we'd have to have multiple bindings and
        # we don't want to. we are reducing complexity.
        # for localPort in range(24600, 65535):
        #    if localPort == 24601:  # reserved for the Neuron UI
        #        continue
        #    sock = bind(localPort)
        #    if sock is not None:
        #        return localPort, sock
        # raise Exception('unable to create socket')
        return bind(UDPRelay.PORT)

    def punch(self, remoteIp: str, remotePort: int):
        self.socket.sendto(b'punch', (remoteIp, remotePort))

    def addPeer(self, ip: str):
        self.punch(ip, UDPRelay.PORT)
        self.peers.append(ip)

    async def initSocketListener(self):
        self.socketListener = asyncio.create_task(self.listenTo(self.socket))

    async def listenTo(self, sock: socket.socket):
        while True:
            try:
                self.handlePeerMessage(*(await self.loop.sock_recvfrom(sock, 1024)))
            except Exception as e:
                greyPrint(f'listenTo erorr: {e}')
                break
        # close?

    async def run(self):
        ''' runs forever '''
        self.initNeuronListener()
        self.initSocketListener()

    async def createNeuronListener(self):
        # timeout = aiohttp.ClientTimeout(total=None, sock_read=3600)
        timeout = aiohttp.ClientTimeout(total=None, sock_read=None)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # async with aiohttp.ClientSession() as session:
            try:
                async with session.get(UDPRelay.satoriUrl('/stream')) as response:
                    async for line in response.content:
                        if line.startswith(b'data:'):
                            self.handleNeuronMessage(
                                line.decode('utf-8')[5:].strip())
            except asyncio.TimeoutError:
                greyPrint("SSE connection timed out...")
                raise SseTimeoutFailure()

    def cancelNeuronListener(self):
        self.neuronListener.cancel()

    def initNeuronListener(self):
        if self.neuronListener is not None:
            self.cancelNeuronListener()
        self.neuronListener = asyncio.create_task(self.createNeuronListener())

    def handleNeuronMessage(self, message: str):
        msg = SynergyMsg.fromJson(message)
        if msg.ip not in self.peers:
            self.addPeer(msg.ip)
        self.speak(
            remoteIp=msg.ip,
            remotePort=UDPRelay.PORT,
            data=msg.data.encode() if isinstance(msg.data, str) else msg.data)

    def handlePeerMessage(self, data: bytes, address: Tuple[str, int]):
        greyPrint(f'Received {data} from {address[0]}:{address[1]}')
        if data in [b'punch', b'payload']:
            greyPrint('skipping punch or payload')
            return
        requests.post(
            UDPRelay.satoriUrl('/message'),
            data=data,
            headers={
                'Content-Type': 'application/octet-stream',
                'remoteIp': address[0],
                # not necessary right now:
                # 'remotePort': str(address[1]),
                # 'localPort': str(UDPRelay.PORT)
            })


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

    # maybe we should loop all this once a day or something, after 24 hours?
    await waitForNeuron()
    udpRelay = UDPRelay()
    await udpRelay.run()

asyncio.run(main())
