import pandas as pd
import hashlib
import base64
from typing import Union
from satorilib.disk import Cache
from satorilib.concepts import StreamId
from satorineuron import config
Cache.setConfig(config)


def hashRow(priorRowHash: str, ts: str, value: str) -> str:
    return hashIt(priorRowHash + ts + value)


def hashIt(string: str) -> str:
    # return hashlib.sha256(rowStr.encode()).hexdigest() # 74mb
    # return hashlib.md5(rowStr.encode()).hexdigest() # 42mb
    return hashlib.blake2s(
        string.encode(),
        digest_size=8).hexdigest()  # 27mb / million rows


streams = [
    {"source": "satori", "author": "03b4127dd21b6ee0528cb4126dbdcb093e50a04e00c7209f867995265d4d9a5c37",
        "stream": "test", "target": "price"},
]
stream = {"source": "satori", "author": "03b4127dd21b6ee0528cb4126dbdcb093e50a04e00c7209f867995265d4d9a5c37",
          "stream": "test", "target": "price"}

s = StreamId.fromMap(stream)
disk = Cache(id=s)
df = disk.read()
disk.validateAllHashes()

priorRowHash = ''
priorRow = None
for index, row in df.iterrows():
    rowHash = hashIt(priorRowHash + str(index) + str(row['value']))
    print(rowHash, row['hash'])
    # if rowHash != row['hash']:
    #    return False, priorRow.to_frame().T if isinstance(priorRow, pd.Series) else None
    priorRowHash = rowHash
    priorRow = row
