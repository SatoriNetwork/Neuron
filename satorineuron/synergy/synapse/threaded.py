'''
we discovered that udp hole punching inside docker containers is not always
possible because of the way the docker nat works. we thought it was.
this host script is meant to run on the host machine.
it will establish a sse connection with the flask server running inside
the container. it will handle the UDP hole punching, passing data between the
flask server and the remote peers.

this linux version drops the need for asyncio and uses 2 threads instead.
this is because we encountered an error:
"'_UnixSelectorEventLoop' object has no attribute 'sock_recvfrom'"
and it seemed this might be due to a python version issue:
https://docs.python.org/3/library/asyncio-eventloop.html#asyncio.loop.sock_recvfrom
given that we are unwilling to require a more recent version of python than 3.7
we are going to use threads instead of asyncio. we will use this simplified 
version on mac as well. luckily we only need 2 threads: one that listens to the
neuron and relays messages to peers, and one that listens to the socket and
relays messages from peers to the neuron.
'''

import typing as t
import time
import threading
import json
import socket
import urllib.request
import urllib.parse


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


class requests:
    '''
    simple wrapper for urllib to mimic requests.get and requests.post api.
    made so we could remove our dependancy on reuqests library and still use 
    the same api.
    '''
    @staticmethod
    def get(url: str) -> str:
        ''' Using urllib.request to open a URL and read the response '''
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return response.read().decode('utf-8')
        except Exception as _:
            return ''

    @staticmethod
    def post(url: str, data: bytes, headers: dict = None) -> str:
        ''' Using urllib to post with an API similar to requests.post '''
        headers = headers or {}
        # If data is a dictionary, encode it into bytes using urllib.parse.urlencode
        if isinstance(data, dict):
            data = urllib.parse.urlencode(data).encode('utf-8')
        elif isinstance(data, str):
            data = data.encode('utf-8')
        request = urllib.request.Request(
            url, data=data, headers=headers, method='POST')
        with urllib.request.urlopen(request) as response:
            return response.read().decode('utf-8')


class Synapse():
    ''' go-between for the flask server and the remote peers '''

    PORT = 24600

    def __init__(self):
        self.running = False
        self.neuronListener = None
        self.peers: t.List[str] = []
        self.socket: socket.socket = self.createSocket()
        self.run()

    @staticmethod
    def satoriUrl(endpoint='') -> str:
        return 'http://localhost:24601/synapse' + endpoint

    ### INIT ###

    def run(self):
        ''' runs forever '''
        self.running = True
        self.initNeuronListener()

    def initNeuronListener(self):
        self.neuronListener = threading.Thread(target=self.listenToNeuron)
        self.neuronListener.start()

    def initSocketListener(self):
        self.listenToSocket()

    def listenToNeuron(self):
        try:
            request = urllib.request.Request(Synapse.satoriUrl('/stream'))
            with urllib.request.urlopen(request) as response:
                for line in response:
                    if not self.running:
                        break
                    decoded = line.decode('utf-8')
                    if decoded.startswith('data:'):
                        self.handleNeuronMessage(decoded[5:].strip())
        except KeyboardInterrupt:
            pass
        except SseTimeoutFailure:
            pass
        except Exception as e:
            greyPrint(f'neuron listener error: {e}')
        finally:
            self.shutdown()

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
                return sock
            except Exception as e:
                greyPrint(f'unable to bind to port {localPort}, {e}')
                waitBeforeRaise(60)
                raise Exception('unable to create socket')

        return bind(Synapse.PORT)

    def listenToSocket(self):
        while self.running:
            try:
                data, address = self.socket.recvfrom(1024)
                if data != b'':
                    self.handlePeerMessage(data, address)
            except Exception as _:
                break
        self.shutdown()

    ### SPEAK ###

    def speak(self, remoteIp: str, remotePort: int, data: str = ''):
        # greyPrint(f'sending to {remoteIp}:{remotePort} {data}')
        self.socket.sendto(data.encode(), (remoteIp, remotePort))

    def maybeAddPeer(self, ip: str):
        if ip not in self.peers:
            self.addPeer(ip)

    def addPeer(self, ip: str):
        self.speak(ip, Synapse.PORT, data=Ping().toJson)
        self.peers.append(ip)

    ### HANDLERS ###

    def handleNeuronMessage(self, message: str):
        msg = Envelope.fromJson(message)
        self.maybeAddPeer(msg.ip)
        self.speak(
            remoteIp=msg.ip,
            remotePort=Synapse.PORT,
            data=msg.vesicle.toJson)

    def handlePeerMessage(self, data: bytes, address: t.Tuple[str, int]):
        # greyPrint(f'Received {data} from {address[0]}:{address[1]}')
        # # no need to ping back - it has issues anyway
        # ping = None
        # try:
        #    ping = Ping.fromMessage(data)
        # except Exception as e:
        #    greyPrint(f'error parsing message: {e}')
        # if isinstance(ping, Ping):
        #    if not ping.isResponse:
        #        self.maybeAddPeer(address[0])
        #        self.speak(
        #            remoteIp=address[0],
        #            remotePort=Synapse.PORT,
        #            data=Ping(True).toJson)
        #        return
        #    if ping.isResponse:
        #        greyPrint(f'connection to {address[0]} established!')
        #        return
        self.relayToNeuron(data=data, ip=address[0], port=address[1])

    def relayToNeuron(self, data: bytes, ip: str, port: int):
        try:
            response = requests.post(
                Synapse.satoriUrl('/message'),
                data=data,
                headers={
                    'Content-Type': 'application/octet-stream',
                    'remoteIp': ip})
            if response != 'ok':
                raise Exception(response)
        except Exception as e:
            greyPrint(
                'unable to relay message to neuron: error: '
                f'{e}, address: {ip}:{port}, data: {data}')

    ### SHUTDOWN ###

    def shutdown(self):
        self.running = False
        if self.socket:
            greyPrint('closing socket')
            self.socket.close()
            self.socket = None
        if (
            self.neuronListener != None and
            threading.current_thread() != self.neuronListener
        ):
            greyPrint('closing neuron listener')
            self.neuronListener.join()
            self.neuronListener = None


def waitForNeuron():
    notified = False
    while True:
        try:
            r = requests.get(Synapse.satoriUrl('/ping'))
            if r == 'ok':
                if notified:
                    greyPrint(
                        'established connection to Satori Neuron')
                return
        except Exception as _:
            if not notified:
                greyPrint('waiting for Satori Neuron')
                notified = True
        time.sleep(1)


def main():
    while True:
        waitForNeuron()
        try:
            greyPrint("Satori P2P is running. Press Ctrl+C to stop.")
            synapse = Synapse()
            synapse.listenToSocket()
        except KeyboardInterrupt:
            pass
        except SseTimeoutFailure:
            pass
        except Exception as _:
            pass
        finally:
            greyPrint('Satori P2P is shutting down')
            synapse.shutdown()
            time.sleep(5)


def runSynapse():
    try:
        greyPrint('Synapse started')
        main()
    except KeyboardInterrupt:
        greyPrint('Synapse exited by user')


if __name__ == '__main__':
    runSynapse()
