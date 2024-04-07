from typing import Union
import datetime as dt
from satorilib.concepts import StreamId


class PubSubStreamId(StreamId):
    ''' 
    unique identifier for a stream, with indicators for being a publisher and
    subscriber
    '''

    def __init__(
        self,
        source: str,
        author: str,
        stream: str,
        target: str = '',
        publish: bool = False,
        subscribe: bool = False,
    ):
        super().__init__(source, author, stream, target)
        self.publish = publish
        self.subscribe = subscribe

    @staticmethod
    def fromStreamId(
        streamId: StreamId,
        publish: bool = None,
        subscribe: bool = None,
    ):
        return PubSubStreamId(
            source=streamId.source,
            author=streamId.author,
            stream=streamId.stream,
            target=streamId.target,
            publish=publish,
            subscribe=subscribe)

    def new(
        self,
        source: str = None,
        author: str = None,
        stream: str = None,
        target: str = None,
        publish: bool = None,
        subscribe: bool = None,
    ):
        if publish is None:
            if hasattr(self, 'publish'):
                publish = self.publish
            else:
                publish = False
        if subscribe is None:
            if hasattr(self, 'subscribe'):
                subscribe = self.subscribe
            else:
                subscribe = False
        return PubSubStreamId(
            source=source or self.source,
            author=author or self.author,
            stream=stream or self.stream,
            target=target or self.target,
            publish=publish,
            subscribe=subscribe)


class SignedStreamId(PubSubStreamId):
    ''' unique identifier for a stream '''

    def __init__(
        self,
        source: str,
        author: str,
        stream: str,
        target: str = '',
        publish: bool = False,
        subscribe: bool = False,
        signature: str = None,
        signed: str = None,
    ):
        super().__init__(source, author, stream, target, publish, subscribe)
        if signature is None or signed is None:
            raise TypeError('sig and msg must be strings')
        self.signature = signature
        self.signed = signed

    def sign(self):
        ''' signs the signature given by the server '''
        self.signed = 'sign(signature)'

    @property
    def streamId(self):
        return StreamId(
            source=self.source,
            author=self.author,
            stream=self.stream,
            target=self.target)

    @staticmethod
    def fromStreamId(
        streamId: StreamId,
        publish: bool = None,
        subscribe: bool = None,
        signature: str = None,
        signed: str = None,
    ):
        return SignedStreamId(
            source=streamId.source,
            author=streamId.author,
            stream=streamId.stream,
            target=streamId.target,
            publish=publish,
            subscribe=subscribe,
            signature=signature,
            signed=signed)

    def new(
        self,
        source: str = None,
        author: str = None,
        stream: str = None,
        target: str = None,
        publish: bool = None,
        subscribe: bool = None,
        signature: str = None,
        signed: str = None,
    ):
        if publish is None:
            if hasattr(self, 'publish'):
                publish = self.publish
            else:
                publish = False
        if subscribe is None:
            if hasattr(self, 'subscribe'):
                subscribe = self.subscribe
            else:
                subscribe = False
        if signature is None:
            if hasattr(self, 'signature'):
                signature = self.signature
            else:
                signature = None
        if signed is None:
            if hasattr(self, 'signed'):
                signed = self.signed
            else:
                signed = None
        return SignedStreamId(
            source=source or self.source,
            author=author or self.author,
            stream=stream or self.stream,
            target=target or self.target,
            publish=publish,
            subscribe=subscribe,
            signature=signature,
            signed=signed)
