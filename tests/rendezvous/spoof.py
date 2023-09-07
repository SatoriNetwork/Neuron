# this is a test folder, holding a spoof client so that we can test the
# rendezvous server using the pair functionality with requires no special keys.
# todo:
from satorilib.api.udp.rendezvous.base import UDPRendezvousConnectionBase

conn = UDPRendezvousConnectionBase()
conn.show()
conn.rendezvous()
conn.send('hi')
conn.show()
