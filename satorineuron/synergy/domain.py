from typing import Union
import json
import pandas as pd
import datetime as dt
from satorilib.api.time import isValidTimestamp


class SingleObservation():
    def __init__(
        self,
        time: Union[str, int, float, dt.datetime],
        data: Union[str, int, bytes, float, None],
        hash: Union[str,  None]
    ):
        self.time = time
        self.data = data
        self.hash = hash

    @staticmethod
    def fromMessage(msg: bytes) -> 'SingleObservation':
        return SingleObservation(**json.loads(msg.decode()))

    @property
    def isEmpty(self):
        return self.time is None or self.data is None or self.hash is None

    @property
    def isValid(self):
        return (
            isinstance(self.data, str) and
            isinstance(self.hash, str) and
            isValidTimestamp(self.time))

    def toDataFrame(self) -> pd.DataFrame:
        df = pd.DataFrame({
            'observationTime': [self.time],
            'value': [self.data],
            'hash': [self.hash]
        })
        try:
            df['value'] = pd.to_numeric(df['value'], errors='raise')
        except ValueError:
            pass
        df.set_index('observationTime', inplace=True)
        return df

    def toJson(self):
        return json.dumps({
            'time': self.time,
            'data': self.data,
            'hash': self.hash})


class SynergyMsg():
    def __init__(self, ip: str, data: Union[str, int, bytes, float, None]):
        self.ip = ip
        self.data = data

    @staticmethod
    def fromJson(msg: bytes) -> 'SynergyMsg':
        return SynergyMsg(**json.loads(msg.decode() if isinstance(msg, bytes) else msg))

    def toJson(self):
        return json.dumps({
            'ip': self.ip,
            'data': self.data})
