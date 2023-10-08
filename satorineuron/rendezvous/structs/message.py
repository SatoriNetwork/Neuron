import datetime as dt
from typing import Union
from satorirendezvous.lib.lock import LockableList
from satorirendezvous.example.peer.structs.message import PeerMessage as Message


class PeerMessage(Message):

    def __init__(
        self, sent: bool, raw: bytes, time: dt.datetime = None,
        prefix: Union[str, None] = None,
        subCommand: Union[str, None] = None,
        observationTime: Union[str, None] = None,
        data: Union[str, None] = None,
        msgId: Union[str, None] = None,
    ):
        self.msgId: Union[str, None] = msgId
        super().__init__(
            sent=sent, raw=raw, time=time,
            prefix=prefix,
            subCommand=subCommand,
            observationTime=observationTime,
            data=data)

    def initiateInterpret(self):
        if (
            self.prefix is None and
            self.subCommand is None and
            self.msgId is None and
            self.observationTime is None and
            self.data is None
        ):
            self.interpret()

    def interpret(self):
        try:
            parts = self.messageAsString.split('|')
            if self.isRequest:
                self.prefix = parts[0]
                self.subCommand = parts[1]
                self.msgId = parts[2]
                self.observationTime = parts[3]
            elif self.isResponse:
                self.prefix = parts[0]
                self.subCommand = parts[1]
                self.msgId = parts[2]
                self.observationTime = parts[3]
                self.data = parts[4]
        except Exception as e:
            print(e)

    @staticmethod
    def parse(raw: Union[str, bytes], sent: bool, time: dt.datetime = None) -> 'PeerMessage':
        if isinstance(raw, str):
            strRaw = raw
        elif isinstance(raw, bytes):
            strRaw = PeerMessage._asString(raw)
        else:
            strRaw = str(raw)
        try:
            parts = strRaw.split('|')
            if PeerMessage._isRequest(raw):
                PeerMessage(
                    raw=raw, sent=sent, time=time,
                    prefix=parts[0],
                    subCommand=parts[1],
                    msgId=parts[2],
                    observationTime=parts[3])
            elif PeerMessage._isResponse(raw):
                PeerMessage(
                    raw=raw, sent=sent, time=time,
                    prefix=parts[0],
                    subCommand=parts[1],
                    msgId=parts[2],
                    observationTime=parts[3],
                    data=parts[4])
        except Exception as e:
            print(e)


class PeerMessages(LockableList[PeerMessage]):
    '''
    iterating over this list within a context manager is thread safe, example: 
        with messages:
            for message in messages:
                message.read()
    '''
