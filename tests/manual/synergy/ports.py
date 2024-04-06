from typing import List, Tuple
import socket
import asyncio


class UDPRelay:
    ''' go-between for the flask server and the remote peers '''

    PORT = 24600

    def __init__(self):
        self.socketListener = None
        self.peers: List[str] = []
        self.socket: socket.socket = self.createSocket()
        self.loop = asyncio.get_event_loop()
        self.running = False

    def createSocket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('0.0.0.0', UDPRelay.PORT))
            sock.setblocking(False)
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

    async def run(self):
        self.running = True
        self.socketListener = asyncio.create_task(self.listenTo(self.socket))

    async def listenTo(self, sock: socket.socket):
        while self.running:
            try:
                data, addr = await self.loop.sock_recvfrom(sock, 1024)
                self.handlePeerMessage(data, addr)
            except asyncio.CancelledError:
                print('listenTo task cancelled')
                break
            except Exception as e:
                print(f'listenTo error: {e}')
                # Optionally, break or continue based on error type

    def handlePeerMessage(self, data: bytes, address: Tuple[str, int]):
        print(f'Received {data} from {address[0]}:{address[1]}')

    async def shutdown(self):
        self.running = False
        if self.socketListener:
            self.socketListener.cancel()
            try:
                await self.socketListener
            except asyncio.CancelledError:
                print('Socket listener task cancelled successfully.')
        self.socket.close()
        print('UDPRelay shutdown complete.')


async def main():
    udpRelay = UDPRelay()
    await udpRelay.run()
    print("Satori P2P Relay is running. Press Ctrl+C to stop.")
    try:
        while True:
            # await asyncio.sleep(3600)
            udpRelay.addPeer('192.168.0.1')
            await asyncio.sleep(60)
            udpRelay.addPeer('192.168.0.2')
    except KeyboardInterrupt:
        pass
    finally:
        await udpRelay.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Interrupted by user')
