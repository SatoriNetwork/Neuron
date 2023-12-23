''' this script describes a single connection between two nodes over UDP '''

import socket
import threading
from typing import Union
from satorilib import logging
from satorilib.api.time import now
from satorineuron.rendezvous.structs.protocol import PeerProtocol
from satorineuron.rendezvous.structs.message import PeerMessage


class Connection:
    ''' raw connection functionality '''

    def __init__(
        self,
        topicSocket: socket.socket,
        port: int,
        peerPort: int,
        peerIp: str,
        onMessage=None,
    ):
        self.port = port
        self.peerIp = peerIp
        self.peerPort = peerPort
        self.topicSocket = topicSocket
        self.onMessage = onMessage or self.display

    def display(self, msg, addr=None, **kwargs):
        logging.info(f'from: {addr}, {msg}')

    def show(self):
        logging.info(f'peer ip:  {self.peerIp}')
        logging.info(f'peer port: {self.peerPort}')
        logging.info(f'my port: {self.port}')

    def establish(self):

        def punchAHole():
            # logging.debug('---actaully punching a hole---',
            #              self.peerIp, self.peerPort, print='magenta')
            self.topicSocket.sendto(b'0', (self.peerIp, self.peerPort))

        def listen():
            while True:
                data, addr = self.topicSocket.recvfrom(1024)
                # logging.debug('---channel message recieved---',
                #              data, addr, print='magenta')
                self.onMessage(PeerMessage.fromJson(data.decode(), sent=False))

        # logging.debug('establishing connection', print='magenta')
        punchAHole()
        # self.topicSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # self.topicSocket.bind(('0.0.0.0', self.peerPort))
        listener = threading.Thread(target=listen, daemon=True)
        listener.start()
        # logging.debug('ready to exchange messages\n', print='magenta')
        # todo:  add a heart beat ping if needed

    def makePayload(self, cmd: str, msgs: list[str] = None) -> Union[bytes, None]:
        # logging.debug('make payload cmd', cmd, print='red')
        if not PeerProtocol.isValidCommand(cmd):
            logging.error('command not valid', cmd, print=True)
            return None
        try:
            return PeerProtocol.compile([
                x for x in [cmd, *(msgs or [])]
                if isinstance(x, int) or (x is not None and len(x) > 0)])
        except Exception as e:
            logging.warning('err w/ payload', e, cmd, msgs)

    def send(self, cmd: str, msg: PeerMessage = None):
        # TODO: make this take a PeerMessage object and do that everywhere
        payload = cmd
        # shouldn't this be peerPort, not localport??
        self.topicSocket.sendto(payload, (self.peerIp, self.port))
        self.topicSocket.sendto(
            msg.asJsonStr.decode(),
            (self.peerIp, self.port))
        # payload = self.makePayload(cmd, msgs)
        # if payload is None:
        #    return False
        # self.topicSocket.sendto(payload, (self.peerIp, self.port))
        self.onMessage(msg, sent=True, time=now())
        return True
