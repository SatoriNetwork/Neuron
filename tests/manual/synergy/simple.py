from typing import List, Tuple
import time
import socket
import threading


class UDPRelay:
    ''' go-between for the flask server and the remote peers '''

    PORT = 24600

    def __init__(self):
        self.socketListener = None
        self.peers: List[str] = []
        self.socket: socket.socket = self.createSocket()
        self.running = False

    def createSocket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('0.0.0.0', UDPRelay.PORT))
            return sock
        except Exception as e:
            print(f'unable to bind to port {UDPRelay.PORT}, {e}')
            raise Exception('unable to create socket')

    def speak(self, remoteIp: str, remotePort: int, data: bytes = b'punch'):
        self.socket.sendto(data, (remoteIp, remotePort))

    def maybeAddPeer(self, ip: str):
        if ip not in self.peers:
            self.addPeer(ip)

    def addPeer(self, ip: str):
        self.speak(ip, UDPRelay.PORT)
        self.peers.append(ip)

    def run(self):
        self.running = True
        self.socketListener = threading.Thread(target=self.listenTo)
        self.socketListener.start()

    def listenTo(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                self.handlePeerMessage(data, addr)
            except Exception as e:
                print(f'listenTo error: {e}')
                self.shutdown()
                break

    def handlePeerMessage(self, data: bytes, address: Tuple[str, int]):
        print(f'Received {data} from {address[0]}:{address[1]}')

    def shutdown(self):
        self.running = False
        self.socket.close()
        print('UDPRelay shutdown complete.')


def main():
    udpRelay = UDPRelay()
    udpRelay.run()
    try:
        while True:
            # await asyncio.sleep(3600)
            udpRelay.addPeer('198.44.128.196')
            time.sleep(10)
            udpRelay.addPeer('198.44.128.196')
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print('e:', e)
    finally:
        udpRelay.shutdown()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('Interrupted by user')
