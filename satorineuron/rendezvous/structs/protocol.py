'''
the protocol consists of a request for an observation before a given time. and
a response with the observation. if there is no observation, NONE is returned:

"REQUEST|time"
"RESPONSE|time|data"
"RESPONSE|NONE|NONE"

'''
import datetime as dt
from satorilib.api.time import datetimeToString, datetimeFromString, now

from satorirendezvous.example.peer.structs.protocol import PeerProtocol as Protocol


class PeerProtocol(Protocol):

    hashSub: bytes = b'hash'

    @staticmethod
    def subCommands():
        return [
            PeerProtocol.observationSub,
            # PeerProtocol.countSub,  # unused
            PeerProtocol.hashSub,]

    @staticmethod
    def isValidCommand(cmd: bytes) -> bool:
        return PeerProtocol.toBytes(cmd) in PeerProtocol.prefixes()

    @staticmethod
    def isValidCommand(subcmd: bytes) -> bool:
        return PeerProtocol.toBytes(subcmd) in PeerProtocol.subCommands()
