'''
we discovered that udp hole punching inside docker containers is not always
possible because of the way the docker nat works. we thought it was.
this host script is meant to run on the host machine.
it will establish a sse connection with the flask server running inside
the container. it will handle the UDP hole punching, passing data between the
flask server and the remote peers.

NOTE: if you modify this file at all you have to rehash it and update the hash
on the server. this can be done with this code snippet:
```
import os
import hashlib
def generateHash(inputStr: str) -> str:
    return hashlib.sha256(inputStr.encode('utf-8')).hexdigest()

with open('c:\\repos\\Satori\\Neuron\\scripts\\p2p.py', "r") as file:
    print(generateHash(file.read()))

print('save that has to the list returned from the Central Server /verify/scripthash endpoint')
```
'''

import time
import typing as t
import socket
import asyncio
import json
import requests  # ==2.31.0
import aiohttp  # ==3.8.4


### CLASSES (coped from satorineuron.synergy.domain) ###

# don't forget to use t.Dict in place of dict and t.Union inplace of Union
# don't forget to comment out the references to Vesicle objects other than Ping

class Vesicle():
    '''
    any object sent over the wire to a peer must inhereit from this so it's
    guaranteed to be convertable to dict so we can have nested dictionaries
    then convert them all to json once at the end (rather than nested json).

    in the future we could use this as a place to hold various kinds of context
    to support advanced protocol features.
    '''

    def __init__(self, className: str = None, **kwargs):
        self.className = className or self.__class__.__name__
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def toDict(self):
        return {
            'className': self.className,
            **{
                key: value
                for key, value in self.__dict__.items()
                if key != 'className'}}

    @property
    def toJson(self):
        return json.dumps(self.toDict)


class Ping(Vesicle):
    ''' initial ping is False, response ping is True '''

    def __init__(self, ping: bool = False, **_kwargs):
        super().__init__()
        self.ping = ping

    @staticmethod
    def empty() -> 'Ping':
        return Ping()

    @staticmethod
    def fromMessage(msg: bytes) -> 'Ping':
        obj = Ping(**json.loads(msg.decode()
                                if isinstance(msg, bytes) else msg))
        if obj.className == Ping.empty().className:
            return obj
        raise Exception('invalid object')

    @property
    def toDict(self):
        return {'ping': self.ping, **super().toDict}

    @property
    def toJson(self):
        return json.dumps(self.toDict)

    @property
    def isValid(self):
        return isinstance(self.ping, bool)

    @property
    def isResponse(self):
        return self.ping


class Envelope():
    ''' messages sent between neuron and synapse '''

    def __init__(self, ip: str, vesicle: Vesicle):
        self.ip = ip
        self.vesicle = vesicle

    @staticmethod
    def fromJson(msg: bytes) -> 'Envelope':
        structure: t.Dict = json.loads(
            msg.decode() if isinstance(msg, bytes) else msg)
        return Envelope(
            ip=structure.get('ip', ''),
            vesicle=Vesicle(**structure.get('vesicle', {'content': '', 'context': {}})))

    @property
    def toDict(self):
        return {
            'ip': self.ip,
            'vesicle': (
                self.vesicle.toDict
                if isinstance(self.vesicle, Vesicle)
                else self.vesicle)}

    @property
    def toJson(self):
        return json.dumps(self.toDict)


### p2p functionality ###


def greyPrint(msg: str):
    return print(
        "\033[90m"  # grey
        + msg +
        "\033[0m"  # reset
    )


class SseTimeoutFailure(Exception):
    '''
    sometimes we the connection to the neuron fails and we want to identify
    that failure easily with this custom exception so we can handle reconnect.
    '''

    def __init__(self, message='Sse timeout failure', extraData=None):
        super().__init__(message)
        self.extraData = extraData

    def __str__(self):
        return f"{self.__class__.__name__}: {self.args[0]} (Extra Data: {self.extraData})"

# # written in an attempt to remove the aiohttp and requests dependencies:
# class NeuronWatcher:
#
#    @staticmethod
#    async def createNeuronListener(self):
#        import asyncio
#        import http.client
#        from urllib.parse import urlparse
#        url = UDPRelay.satoriUrl('/stream')
#        parsed_url = urlparse(url)
#        host = parsed_url.hostname
#        port = parsed_url.port or (443 if parsed_url.scheme == 'https' else 80)
#        path = parsed_url.path
#
#        reader, writer = await asyncio.open_connection(host, port, ssl=(parsed_url.scheme == 'https'))
#        request_header = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
#        writer.write(request_header.encode('utf-8'))
#
#        try:
#            while True:  # You might want to implement a proper breaking condition
#                line = await reader.readline()
#                if line.startswith(b'data:'):
#                    asyncio.create_task(self.handleNeuronMessage(
#                        line.decode('utf-8')[5:].strip()))
#
#        except asyncio.TimeoutError:
#            print("SSE connection timed out...")
#            await self.shutdown()
#            raise
#        except Exception as e:
#            print(f"An error occurred: {e}")
#            await self.shutdown()
#        finally:
#            writer.close()
#            await writer.wait_closed()
#
# class requests:
#    ''' works: this could allow us to avoid using 3rd party package requests '''
#    @staticmethod
#    def get(url: str) -> t.Any:
#        import urllib.request
#        ''' Using urllib.request to open a URL and read the response '''
#        try:
#            with urllib.request.urlopen(url) as response:
#                content = response.read()
#            # Decoding the content to a string, assuming it's encoded in UTF-8
#            content_as_string = content.decode('utf-8')
#            return content_as_string
#        except Exception as e:
#            # print(f'unable to read {url}: {e}')
#            pass


class UDPRelay():
    ''' go-between for the flask server and the remote peers '''

    PORT = 24600

    def __init__(self):
        self.socketListener = None
        self.neuronListener = None
        self.peers: t.List[str] = []
        self.session = aiohttp.ClientSession()
        self.socket: socket.socket = self.createSocket()
        self.loop = asyncio.get_event_loop()
        self.broke = asyncio.Event()

    @staticmethod
    def satoriUrl(endpoint='') -> str:
        return 'http://localhost:24601/synapse' + endpoint

    ### INIT ###

    async def run(self):
        ''' runs forever '''
        await self.initNeuronListener()
        await self.initSocketListener()

    async def initNeuronListener(self):
        await self.cancelNeuronListener()
        self.neuronListener = asyncio.create_task(self.createNeuronListener())

    async def initSocketListener(self):
        await self.cancelSocketListener()
        self.socketListener = asyncio.create_task(self.listenToSocket())

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
                greyPrint('Neuron connection timed out...')
            except aiohttp.ClientConnectionError as e:
                greyPrint(f'Neuron connection error... {e}')
            except aiohttp.ClientError:
                greyPrint('Neuron error...')
            self.broke.set()

    def createSocket(self) -> socket.socket:
        def waitBeforeRaise(seconds: int):
            '''
            if this errors, but the neuron is reachable, it will immediately 
            try again, and mostlikely fail for the same reason, such as perhaps
            the port is bound elsewhere. So in order to avoid continual 
            attempts and printouts we'll wait here before raising
            '''
            time.sleep(seconds)

        def bind(localPort: int) -> t.Union[socket.socket, None]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                sock.bind(('0.0.0.0', localPort))
                sock.setblocking(False)
                return sock
            except Exception as e:
                greyPrint(f'unable to bind to port {localPort}, {e}')
                waitBeforeRaise(60)
                raise Exception('unable to create socket')

        return bind(UDPRelay.PORT)

    async def listenToSocket(self):
        while not self.broke.is_set():
            try:
                data, address = await self.loop.sock_recvfrom(self.socket, 1024)
                if data != b'':
                    await self.handlePeerMessage(data, address)
            except asyncio.CancelledError:
                greyPrint('listen task cancelled')
                break
            except Exception as e:
                greyPrint(f'listenToSocket error: {e}')
                break
        self.broke.set()

    ### SPEAK ###

    async def speak(self, remoteIp: str, remotePort: int, data: str = ''):
        # greyPrint(f'sending to {remoteIp}:{remotePort} {data}')
        await self.loop.sock_sendto(self.socket, data.encode(), (remoteIp, remotePort))

    async def maybeAddPeer(self, ip: str):
        if ip not in self.peers:
            await self.addPeer(ip)

    async def addPeer(self, ip: str):
        await self.speak(ip, UDPRelay.PORT, data=Ping().toJson)
        self.peers.append(ip)

    ### HANDLERS ###

    async def handleNeuronMessage(self, message: str):
        msg = Envelope.fromJson(message)
        await self.maybeAddPeer(msg.ip)
        await self.speak(
            remoteIp=msg.ip,
            remotePort=UDPRelay.PORT,
            data=msg.vesicle.toJson)

    async def handlePeerMessage(self, data: bytes, address: t.Tuple[str, int]):
        # greyPrint(f'Received {data} from {address[0]}:{address[1]}')
        # # no need to ping back - it has issues anyway
        # ping = None
        # try:
        #    ping = Ping.fromMessage(data)
        # except Exception as e:
        #    greyPrint(f'error parsing message: {e}')
        # if isinstance(ping, Ping):
        #    if not ping.isResponse:
        #        await self.maybeAddPeer(address[0])
        #        await self.speak(
        #            remoteIp=address[0],
        #            remotePort=UDPRelay.PORT,
        #            data=Ping(True).toJson)
        #        return
        #    if ping.isResponse:
        #        greyPrint(f'connection to {address[0]} established!')
        #        return
        await self.relayToNeuron(data=data, ip=address[0], port=address[1])

    async def relayToNeuron(self, data: bytes, ip: str, port: int):
        try:
            async with self.session.post(
                    UDPRelay.satoriUrl('/message'),
                    data=data,
                    headers={
                        'Content-Type': 'application/octet-stream',
                        'remoteIp': ip
                    },
            ) as response:
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
                greyPrint('Socket listener task cancelled successfully.')

    async def cancelNeuronListener(self):
        if self.neuronListener:
            self.neuronListener.cancel()
            try:
                await self.neuronListener
            except asyncio.CancelledError:
                greyPrint('Neuron listener task cancelled successfully.')

    async def shutdown(self):
        await self.session.close()
        await self.cancelSocketListener()
        await self.cancelNeuronListener()
        self.socket.close()
        greyPrint('UDPRelay shutdown complete.')


def silentlyWaitForNeuron():
    while True:
        try:
            r = requests.get(UDPRelay.satoriUrl('/ping'))
            if r.status_code == 200:
                return
        except Exception as _:
            pass
        time.sleep(1)


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

    while True:
        await waitForNeuron()
        udpRelay = UDPRelay()
        await udpRelay.run()
        greyPrint("Satori P2P Relay is running. Press Ctrl+C to stop.")
        try:
            await udpRelay.broke.wait()
            raise Exception('udpRelay not running')
        except KeyboardInterrupt:
            pass
        except SseTimeoutFailure:
            pass
        except Exception as _:
            pass
        finally:
            await udpRelay.shutdown()


def runSynapse():
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted by user')


if __name__ == '__main__':
    runSynapse()
