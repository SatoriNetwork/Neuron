from typing import Union
import json
import pandas as pd
import datetime as dt
from satorilib.api.time import isValidTimestamp


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

    @staticmethod
    def asDict(msg: Union[bytes, str, dict]) -> str:
        if isinstance(msg, bytes):
            msg = msg.decode()
        if isinstance(msg, str):
            msg = json.loads(msg)
        if isinstance(msg, dict):
            return msg
        raise Exception('invalid object')

    @staticmethod
    def getClassNameFor(msg: Union[bytes, str, dict]) -> str:
        return Vesicle.asDict(msg).get('className', '')

    @staticmethod
    def build(msg: Union[bytes, str, dict]) -> 'Vesicle':
        msg = Vesicle.asDict(msg)
        name = Vesicle.getClassNameFor(msg)
        if name == '':
            return Vesicle(**msg)
        if name == 'Ping':
            return Ping(**msg)
        if name == 'SingleObservation':
            return SingleObservation(**msg)
        if name == 'ObservationRequest':
            return ObservationRequest(**msg)
        raise Exception('invalid object')

    def toObject(self) -> 'Vesicle':
        if self.className == '':
            return Vesicle(**self.toDict)
        if self.className == 'Ping':
            return Ping(**self.toDict)
        if self.className == 'SingleObservation':
            return SingleObservation(**self.toDict)
        if self.className == 'ObservationRequest':
            return ObservationRequest(**self.toDict)
        raise Exception('invalid object')

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
    def isPinged(self):
        return self.ping


class SingleObservation(Vesicle):
    def __init__(
        self,
        time: Union[str, int, float, dt.datetime],
        data: Union[str, int, bytes, float, None],
        hash: Union[str,  None],
        isFirst: bool = False,
        isLatest: bool = False,
        **_kwargs
    ):
        super().__init__()
        self.time = time
        self.data = data
        self.hash = hash
        self.isFirst = isFirst
        self.isLatest = isLatest

    @staticmethod
    def empty() -> 'SingleObservation':
        return SingleObservation(time='', data='', hash='')

    @staticmethod
    def fromMessage(msg: bytes) -> 'SingleObservation':
        obj = SingleObservation(
            **json.loads(msg.decode() if isinstance(msg, bytes) else msg))
        if obj.className == SingleObservation.empty().className:
            return obj
        raise Exception('invalid object')

    @property
    def toDict(self):
        ''' override '''
        return {
            'time': self.time,
            'data': self.data,
            'hash': self.hash,
            'isFirst': self.isFirst,
            'isLatest': self.isLatest,
            **super().toDict}

    @property
    def toJson(self):
        return json.dumps(self.toDict)

    @property
    def isEmpty(self):
        return self.time is None or self.data is None or self.hash is None

    @property
    def isValid(self):
        return ((isinstance(self.data, str) or
                isinstance(self.data, float) or
                isinstance(self.data, int)) and
                isinstance(self.hash, str) and
                isinstance(self.isFirst, bool) and
                isinstance(self.isLatest, bool) and
                isValidTimestamp(self.time))

    def toDataFrame(self) -> pd.DataFrame:
        df = pd.DataFrame({
            'observationTime': [self.time],
            'value': [self.data],
            'hash': [self.hash]})
        try:
            df['value'] = pd.to_numeric(df['value'], errors='raise')
        except ValueError:
            pass
        df.set_index('observationTime', inplace=True)
        return df


class ObservationRequest(Vesicle):
    def __init__(
        self,
        time: str,
        first: bool = False,
        latest: bool = False,
        middle: bool = False,
        **_kwargs
    ):
        super().__init__()
        self.time = time
        self.first = first
        self.latest = latest
        self.middle = middle

    @staticmethod
    def empty() -> 'ObservationRequest':
        return ObservationRequest(time='')

    @staticmethod
    def fromMessage(msg: bytes) -> 'ObservationRequest':
        obj = ObservationRequest(
            **json.loads(msg.decode() if isinstance(msg, bytes) else msg))
        if obj.className == ObservationRequest.empty().className:
            return obj
        raise Exception('invalid object')

    @property
    def toDict(self):
        ''' override '''
        return {
            'time': self.time,
            'first': self.first,
            'latest': self.latest,
            'middle': self.middle,
            **super().toDict}

    @property
    def toJson(self):
        return json.dumps(self.toDict)

    @property
    def isEmptyTime(self):
        return self.time is None or self.time == ''

    @property
    def isFirst(self):
        return self.isEmptyTime and self.first

    @property
    def isMiddle(self):
        return self.isEmptyTime and not self.first and not self.latest and self.middle

    @property
    def isLatest(self):
        return self.isEmptyTime and not self.first and self.latest

    @property
    def isValid(self):
        return (
            isValidTimestamp(self.time) or
            self.isFirst or self.isLatest or self.isMiddle)
