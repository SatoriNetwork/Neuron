from typing import Union
import json
import pandas as pd
import datetime as dt
from satorilib.api.time.time import timestampToDatetime


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
        def tryTimeConvert():
            try:
                timestampToDatetime(self.time)
                return True
            except Exception as e:
                return False

        return (
            isinstance(self.time, str) and 18 < len(self.time) < 27 and
            tryTimeConvert() and isinstance(self.data, str) and
            isinstance(self.hash, str))

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
            'hash': self.hash
        })
