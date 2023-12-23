import json
import pandas as pd
import datetime as dt
from typing import Union
from satorilib import logging
from satorilib.api.time import now
from satorineuron.rendezvous.structs.protocol import PeerProtocol
from satorirendezvous.lib.lock import LockableList
from satorirendezvous.server.structs.rest import ToClientRestProtocol as Protocol
from satorirendezvous.example.peer.structs.message import PeerMessage as Message


class PeerMessage(Message):

    def __init__(
        self, sent: bool, raw: bytes, time: dt.datetime = None,
        prefix: Union[str, None] = None,
        subCommand: Union[str, None] = None,
        observationTime: Union[str, None] = None,
        data: Union[str, None] = None,
        msgId: Union[str, None] = None,
        hash: Union[str, None] = None,
    ):
        self.msgId: Union[str, None] = msgId
        self.hash: Union[str, None] = hash
        self.raw: bytes = raw
        self.sent: bool = sent
        self.time: dt.datetime = time or now()
        self.prefix: Union[str, None] = prefix
        self.subCommand: Union[str, None] = subCommand
        self.observationTime: Union[str, None] = observationTime
        self.data: Union[str, None] = data
        self.initiateInterpret()

    @staticmethod
    def none(msgId: int = -1) -> 'PeerMessage':
        return PeerMessage(
            sent=False,
            raw=b'',
            time=now(), msgId=str(msgId))

    @staticmethod
    def fromJson(data: str, sent: bool = False) -> Union['PeerMessage', None]:
        if isinstance(data, dict):
            msg = PeerMessage(**data)
        if isinstance(data, str):
            try:
                msg = PeerMessage(**json.loads(data))
            except Exception as e:
                logging.error('FromServerMessage.fromJson error: ',
                              e, data, print=True)
                msg = PeerMessage(raw=data)
        if isinstance(msg, PeerMessage):
            msg.sent = sent
            msg.time = msg.time or now()
            return msg
        return None

    @property
    def asDataFrame(self) -> pd.DataFrame:
        df = pd.DataFrame({
            'observationTime': [self.observationTime],
            'data': [self.data],
            'hash': [self.hash]
        })
        df.set_index('observationTime', inplace=True)
        return df

    @property
    def asJsonStr(self) -> str:
        return json.dumps(self.asJson)

    @property
    def asJson(self) -> dict:
        return {
            'sent': self.sent,
            'raw': self.raw,
            'time': self.time,
            'prefix': self.prefix,
            'subCommand': self.subCommand,
            'observationTime': self.observationTime,
            'data': self.data,
            'msgId': self.msgId,
            'hash': self.hash,
        }

    def __str__(self):
        return (
            f'PeerMessage(\n'
            f'\tsent={self.sent},\n'
            f'\traw={self.raw},\n'
            f'\ttime={self.time},\n'
            f'\tprefix={self.prefix},\n'
            f'\tsubCommand={self.subCommand},\n'
            f'\tobservationTime={self.observationTime},\n'
            f'\tdata={self.data},\n'
            f'\tmsgId={self.msgId},\n'
            f'\thash={self.hash},\n'
            ')')

    def initiateInterpret(self):
        if (
            self.prefix is None and
            self.subCommand is None and
            self.msgId is None and
            self.observationTime is None and
            self.data is None and
            self.hash is None
        ):
            self.interpret()

    def interpret(self):
        try:
            parts = self.messageAsString.split('|')
            if self.isPing():
                self.prefix = parts[0]
            elif self.isRequest():
                self.prefix = parts[0]
                self.subCommand = parts[1]
                self.msgId = parts[2]
                self.observationTime = parts[3]
            elif self.isResponse():
                self.prefix = parts[0]
                self.subCommand = parts[1]
                self.msgId = parts[2]
                self.observationTime = parts[3]
                self.data = parts[4]
                self.hash = parts[5]
        except Exception as e:
            logging.error(e, print=True)

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
                    data=parts[4],
                    hash=parts[5])
        except Exception as e:
            logging.error(e, print=True)

    def __eq__(self, __value: object) -> bool:
        return self.raw == __value.raw

    @staticmethod
    def _asString(raw: bytes) -> str:
        return raw.decode()

    @staticmethod
    def _isPing(raw: bytes) -> bool:
        return raw.startswith(PeerProtocol.pingPrefix)

    @staticmethod
    def _isRequest(raw: bytes, subcmd: bytes = None) -> bool:
        return raw.startswith(PeerProtocol.requestPrefix + b'|' + (subcmd if subcmd is not None else b''))

    @staticmethod
    def _isResponse(raw: bytes, subcmd: bytes = None) -> bool:
        return raw.startswith(PeerProtocol.respondPrefix + b'|' + (subcmd if subcmd is not None else b''))

    @staticmethod
    def _isNoneResponse(raw: bytes, subcmd: bytes = None) -> bool:
        return raw.endswith(b'NONE|NONE') and PeerMessage._isResponse(subcmd=subcmd)

    @property
    def subCommandAsBytes(self) -> str:
        if self.subCommand is None:
            return b''
        if isinstance(self.subCommand, str):
            return self.subCommand.encode()
        if isinstance(self.subCommand, bytes):
            return self.subCommand
        return str(self.subCommand).encode()

    @property
    def messageAsString(self) -> str:
        return self.raw.decode()

    @property
    def isPingSubCommand(self):
        return self.subCommand == PeerProtocol.pingSub

    def isPing(self) -> bool:
        return PeerMessage._isPing(self.raw)

    def isRequest(self, subcmd: bytes = None) -> bool:
        return PeerMessage._isRequest(self.raw, subcmd=subcmd or self.subCommandAsBytes)

    def isResponse(self, subcmd: bytes = None) -> bool:
        return PeerMessage._isResponse(self.raw, subcmd=subcmd or self.subCommandAsBytes)

    def isNoneResponse(self, subcmd: bytes = None) -> bool:
        return PeerMessage._isNoneResponse(self.raw, subcmd=subcmd or self.subCommandAsBytes)


class PeerMessages(LockableList[PeerMessage]):
    '''
    iterating over this list within a context manager is thread safe, example: 
        with messages:
            for message in messages:
                message.read()
    '''

    def msgsToDataframe(self) -> pd.DataFrame:
        df = pd.DataFrame({
            'observationTime': [message.observationTime for message in self],
            'data': [message.data for message in self],
            'hash': [message.hash for message in self]
        })
        df.set_index('observationTime', inplace=True)
        return df

    def latestMessageTime(self) -> Union[str, None]:
        sorted_messages = sorted(self, key=lambda message: message.time)
        return sorted_messages[-1].time if sorted_messages else None

    @property
    def hashes(self) -> list[str]:
        return [message.hash for message in self]


class FromServerMessage():
    ''' a strcuture describing a message from the server '''

    def __init__(
        self,
        command: Union[str, None] = None,
        msgId: Union[int, None] = None,
        messages: Union[list, None] = None,
        raw: Union[str, None] = None,
    ):
        self.command = command
        self.msgId = msgId
        self.messages = messages
        self.raw = raw

    @staticmethod
    def none(msgId: int = -1):
        return FromServerMessage(
            command=Protocol.responseCommand,
            msgId=msgId,
            messages=[],
            raw=None)

    @staticmethod
    def fromJson(data: str):
        if isinstance(data, dict):
            return FromServerMessage(**data)
        if isinstance(data, str):
            try:
                return FromServerMessage(**json.loads(data))
            except Exception as e:
                logging.error('FromServerMessage.fromJson error: ',
                              e, data, print=True)
                return FromServerMessage(raw=data)

    @property
    def isResponse(self) -> bool:
        return self.command == Protocol.responseCommand

    @property
    def isConnect(self) -> bool:
        return self.command == Protocol.connectCommand

    @property
    def asResponse(self) -> str:
        return json.dumps({'response': self.asJson})

    @property
    def asJsonStr(self) -> str:
        return json.dumps(self.asJson)

    @property
    def asJson(self) -> dict:
        return {
            'command': self.command,
            'msgId': self.msgId,
            'messages': self.messages,
            'raw': self.raw}

    def __str__(self):
        return (
            f'FromServerMessage(\n'
            f'\tcommand={self.command},\n'
            f'\tmsgId={self.msgId},\n'
            f'\tmessages={self.messages},\n'
            f'\traw={self.raw})')
