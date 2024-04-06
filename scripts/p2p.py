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

from typing import Union, List, Tuple  # Python3.7 compatible
import socket
import asyncio
import aiohttp
import requests
import json


def greyPrint(msg: str):
    return print(
        "\033[90m"  # grey
        + msg +
        "\033[0m"  # reset
    )


class SynergyMsg():
    def __init__(self, ip: str, data: Union[str, int, bytes, float, None]):
        self.ip = ip
        self.data = data

    @staticmethod
    def fromJson(msg: bytes) -> 'SynergyMsg':
        return SynergyMsg(**json.loads(msg.decode() if isinstance(msg, bytes) else msg))

    def toJson(self):
        return json.dumps({'ip': self.ip, 'data': self.data})


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
        self.session = aiohttp.ClientSession()
        self.socket: socket.socket = self.createSocket()
        self.loop = asyncio.get_event_loop()
        self.running = False

    @staticmethod
    def satoriUrl(endpoint='') -> str:
        return 'http://localhost:24601/udp' + endpoint

    ### INIT ###

    async def run(self):
        ''' runs forever '''
        self.running = True
        await self.initNeuronListener()
        await self.initSocketListener()

    async def initNeuronListener(self):
        await self.cancelNeuronListener()
        self.neuronListener = asyncio.create_task(self.createNeuronListener())

    async def initSocketListener(self):
        await self.cancelSocketListener()
        self.socketListener = asyncio.create_task(self.listenTo(self.socket))

    async def createNeuronListener(self):
        timeout = aiohttp.ClientTimeout(total=None, sock_read=None)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            try:
                async with session.get(UDPRelay.satoriUrl('/stream')) as response:
                    async for line in response.content:
                        if line.startswith(b'data:'):
                            asyncio.create_task(
                                self.handleNeuronMessage(
                                    line.decode('utf-8')[5:].strip()))
            except asyncio.TimeoutError:
                greyPrint("SSE connection timed out...")
                await self.shutdown()
                raise SseTimeoutFailure()
            except aiohttp.ClientConnectionError:
                await self.shutdown()
            except aiohttp.ClientError:
                await self.shutdown()

    def createSocket(self) -> socket.socket:
        def bind(localPort: int) -> Union[socket.socket, None]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind(('0.0.0.0', localPort))
                sock.setblocking(False)
                return sock
            except Exception as e:
                greyPrint(f'unable to bind to port {localPort}, {e}')
                raise Exception('unable to create socket')

        return bind(UDPRelay.PORT)

    async def listenTo(self, sock: socket.socket):
        while self.running:
            try:
                data, address = await self.loop.sock_recvfrom(sock, 1024)
                # Ensure we await the async handlePeerMessage method:
                await self.handlePeerMessage(data, address)
            except asyncio.CancelledError:
                print('listenTo task cancelled')
                break
            except Exception as e:
                print(f'listenTo error: {e}')
                break

    ### SPEAK ###

    async def speak(self, remoteIp: str, remotePort: int, data: bytes = b'punch'):
        greyPrint(f'sending to {remoteIp}:{remotePort} {data}')
        await self.loop.sock_sendto(data, (remoteIp, remotePort))

    async def maybeAddPeer(self, ip: str):
        if ip not in self.peers:
            await self.addPeer(ip)

    async def addPeer(self, ip: str):
        await self.speak(ip, UDPRelay.PORT)
        self.peers.append(ip)

    ### HANDLERS ###

    async def handleNeuronMessage(self, message: str):
        msg = SynergyMsg.fromJson(message)
        await self.maybeAddPeer(msg.ip)
        await self.speak(
            remoteIp=msg.ip,
            remotePort=UDPRelay.PORT,
            data=msg.data.encode() if isinstance(msg.data, str) else msg.data)

    async def handlePeerMessage(self, data: bytes, address: Tuple[str, int]):
        greyPrint(f'Received {data} from {address[0]}:{address[1]}')
        if data in [b'punch', b'payload']:
            greyPrint('skipping punch or payload')
            return
        await self.relayToNeuron(data=data, ip=address[0], port=address[1])

    async def relayToNeuron(self, data: bytes, ip: str, port: int):
        try:
            async with self.session.post(
                    UDPRelay.satoriUrl('/message'),
                    data=data,
                    headers={
                        'Content-Type': 'application/octet-stream',
                        'remoteIp': ip
                    }) as response:
                if response.status != 200:
                    greyPrint(
                        f'POST request to {ip} failed with status {response.status}')
        except aiohttp.ClientError as e:
            # Handle client-side errors (e.g., connection problems).
            greyPrint(f'ClientError occurred: {e}')
        except asyncio.TimeoutError:
            # Handle timeout errors specifically.
            greyPrint('Request timed out')
        except Exception as e:
            # A catch-all for other exceptions - useful for debugging.
            greyPrint(f'Unexpected error occurred: {e}')

    ### SHUTDOWN ###

    async def cancelSocketListener(self):
        if self.socketListener:
            self.socketListener.cancel()
            try:
                await self.socketListener
            except asyncio.CancelledError:
                print('Socket listener task cancelled successfully.')

    async def cancelNeuronListener(self):
        if self.neuronListener:
            self.neuronListener.cancel()
            try:
                await self.neuronListener
            except asyncio.CancelledError:
                print('Neuron listener task cancelled successfully.')

    async def shutdown(self):
        self.running = False
        await self.session.close()
        await self.cancelSocketListener()
        await self.cancelNeuronListener()
        self.socket.close()
        print('UDPRelay shutdown complete.')


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
    print("Satori P2P Relay is running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(3600)
            # testing
            # udpRelay.addPeer('192.168.0.1')
            # await asyncio.sleep(60)
            # udpRelay.addPeer('192.168.0.2')
    except KeyboardInterrupt:
        pass
    finally:
        await udpRelay.shutdown()

try:
    asyncio.run(main())
except KeyboardInterrupt:
    print('Interrupted by user')
