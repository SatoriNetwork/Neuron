'''
the protocol consists of a request for an observation before a given time. and
a response with the observation. if there is no observation, NONE is returned:

"REQUEST|time"
"RESPONSE|time|data|hash"
"RESPONSE|NONE|NONE|NONE"

'''
import datetime as dt
from satorilib.api.time import datetimeToString

from satorilib import logging
from satorirendezvous.example.peer.structs.protocol import PeerProtocol as Protocol


class PeerProtocol(Protocol):

    pingSub: bytes = b'ping'

    @staticmethod
    def respond(time: dt.datetime, data: str, hashId: str, subcmd: bytes = None, msgId: int = -1) -> bytes:
        if isinstance(data, float):
            data = str(data)
        if isinstance(data, int):
            data = str(data)
        if isinstance(data, str):
            data = data.encode()
        if hashId is None:  # counts don't include hashId
            hashId = b'NONE'
        if isinstance(hashId, str):
            hashId = hashId.encode()
        if isinstance(time, dt.datetime):
            time = datetimeToString(time)
        if isinstance(time, str):
            time = time.encode()
        if subcmd is None:
            subcmd = PeerProtocol.observationSub
        if isinstance(subcmd, str):
            subcmd = subcmd.encode()
        if isinstance(msgId, int):
            msgId = str(msgId)
        if isinstance(msgId, str):
            msgId = msgId.encode()
        logging.debug(
            f'PeerProtocol.respond:: time:{time}{type(time)}, data:{data}{type(data)}, hashId:{hashId}{type(hashId)}, subcmd:{subcmd}{type(subcmd)}, msgId:{msgId}{type(msgId)}', print='blue')
        return PeerProtocol.respondPrefix + b'|' + subcmd + b'|' + msgId + b'|' + time + b'|' + data + b'|' + hashId

    @staticmethod
    def respondNone(subcmd: bytes = None) -> bytes:
        return PeerProtocol.respond(subcmd=subcmd, data=b'NONE', time=b'NONE', hashId=b'NONE', msgId=b'-1')

    # not needed because a hash is included in every observation
    # hashSub: bytes = b'hash'

    @staticmethod
    def subCommands():
        return [
            PeerProtocol.observationSub,
            # PeerProtocol.countSub,  # unused
            # PeerProtocol.hashSub,
        ]

    @staticmethod
    def isValidCommand(cmd: bytes) -> bool:
        return PeerProtocol.toBytes(cmd) in PeerProtocol.prefixes()

    @staticmethod
    def isValidCommand(subcmd: bytes) -> bool:
        return PeerProtocol.toBytes(subcmd) in PeerProtocol.subCommands()
