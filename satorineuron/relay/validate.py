import re
import requests
import json
import pandas as pd
import datetime as dt
from functools import partial
from satorilib.api.disk import Disk
from satorilib.api import system
from satorilib.api.wallet import Wallet
from satorilib.concepts.structs import Observation, StreamId
from satorilib.api import hash
from satorineuron import config
from satorineuron import logging
from satorineuron.relay.history import GetHistory


def postRequestHookForNone(r: requests.Response):
    logging.debug('postRequestHook default method')
    return r.text


def postRequestHook(r: requests.Response):
    logging.debug('postRequestHook default method')
    return r.text


class ValidateRelayStream(object):
    def __init__(self, start: 'StartupDag', *args):
        super(ValidateRelayStream, self).__init__(*args)
        self.start = start
        self.claimed = set()
        self.regexURL = (
            # r"^https?://"
            # don't allow websockets as an additional check instead of here - will allow ipfs, etc
            r"^[a-z]+://"
            r"(?P<host>[^\/\?:]+)"
            r"(?P<port>:[0-9]+)?"
            r"(?P<path>\/.*?)?"
            r"(?P<query>\?.*)?$")

    def stream_claimed(self, name: str, source: str = 'satori', target: str = None):
        streamId = StreamId(
            source=source,
            author=self.start.wallet.publicKey,
            stream=name,
            target=target)
        if streamId in self.claimed:
            return True
        if name is None:
            return {}
        r = self.start.server.getStreams(stream={
            'source': source,
            'pubkey': self.start.wallet.publicKey,
            'stream': name,
            **({'target': target} if target is not None else {})})
        if r.text == 'no streams found':
            return False
        self.claimed.add(streamId)
        return True

    def register_stream(self, data: dict):
        streamId = StreamId(
            source=data.get('source', 'satori'),
            author=self.start.wallet.publicKey,
            stream=data.get('name'),
            target=data.get('target'))
        if streamId in self.claimed:
            return True
        # this potentially avoid a redundant call to the server after satori restart...
        # if streamId.topic(asJson=True) in config.get('relay').keys():
        #    # heuristic, there's a possibility, if something went wrong,
        #    # that the stream is saved locally but not registered on server...
        #    return True
        logging.debug('REGISTER STREAM')
        logging.debug({
            'source': data.get('source', 'satori'),
            'pubkey': self.start.wallet.publicKey,
            'stream': data.get('name'),
            'target': data.get('target', ''),
            'cadence': data.get('cadence'),
            'offset': data.get('offset'),
            'datatype': data.get('datatype'),
            'url': data.get('url'),
            'tags': data.get('tags'),
            'description': data.get('description'),
        })
        r = self.start.server.registerStream(stream={
            'source': data.get('source', 'satori'),
            'pubkey': self.start.wallet.publicKey,
            'stream': data.get('name'),
            'target': data.get('target', ''),
            'cadence': data.get('cadence'),
            'offset': data.get('offset'),
            'datatype': data.get('datatype'),
            'url': data.get('url'),
            'tags': data.get('tags'),
            'description': data.get('description'),
        })
        if (r.status_code == 200 and r.text not in ['', None]):
            self.claimed.add(streamId)
            return r.text
        return False

    def subscribe_to_stream(self, data: dict):
        '''
        the reasoning behind this is: if we want to provide the ipfs pins for
        this datastream automatically we ought to just subscribe to it and save
        it on each observation like normal instead of making a second path of
        data management for relay streams only. so, we typically subscribe to
        our own datastream, specifying, explicitly no other stream as the reason
        '''
        r = self.start.server.registerSubscription(subscription={
            'author': {'pubkey': self.start.wallet.publicKey, },
            'stream': {
                'source': data.get('source', 'satori'),
                'pubkey': self.start.wallet.publicKey,
                'stream': data.get('name'),
                'target': data.get('target', ''),
                'cadence': data.get('cadence'),
                'offset': data.get('offset'),
                'datatype': data.get('datatype'),
                'url': data.get('url'),
                'tags': data.get('tags'),
                'description': data.get('description'),
            },
            'reason': {},
        })
        logging.debug(f'trying to subscribe to my own datastream: {r.text}')
        if (r.status_code == 200 and r.text not in ['', None]):
            return r.text
        return False

    def save_local(self, data: dict):
        streamId = StreamId(
            source=data.get('source', 'satori'),
            author=self.start.wallet.publicKey,
            stream=data.get('name'),
            target=data.get('target'))
        config.put(
            'relay',
            data={
                **config.get('relay'),
                **{streamId.topic(asJson=True): {
                    'uri': data.get('uri'),
                    'headers': data.get('headers'),
                    'payload': data.get('payload'),
                    'hook': data.get('hook'),
                    'history': data.get('history'),
                }}})

    def valid_relay(self, data: dict):
        return (
            data.get('source', 'satori') == 'satori' and
            isinstance(data.get('name'), str) and
            0 < len(data.get('name')) < 255 and
            isinstance(data.get('target'), str) and
            0 < len(data.get('target')) < 255 and
            isinstance(data.get('data'), (str, int, float, dict, list)))

    def invalid_url(self, url):
        return (
            (url.startswith('ipfs') or url.startswith('http')) and
            re.compile(self.regexURL).match(url) is None)

    def test_call(self, data: dict):
        def is_valid_json(x):
            try:
                json.loads(x)
                return True
            except Exception as _:
                return False

        if data.get('payload') is None:
            method = partial(requests.get)
        else:
            if is_valid_json(data.get('payload')):
                method = partial(requests.post, json=data.get('payload'))
            else:
                method = partial(requests.post, data=data.get('payload'))
        if data.get('headers') not in ['', None]:
            if is_valid_json(data.get('headers')):
                r = method(
                    data.get('uri'),
                    headers=json.loads(data.get('headers')),)
            elif (
                not is_valid_json(data.get('headers')) and
                "'" in data.get('headers') and
                '"' not in data.get('headers')
            ):
                data['headers'] = data.get('headers').replace("'", '"')
                r = method(
                    data.get('uri'),
                    headers=json.loads(data.get('headers')))
            else:
                r = method(data.get('uri'), headers=data.get('headers'))
        else:
            r = method(data.get('uri'))
        if r.status_code == 200:
            return r
        return False

    def invalid_hook(self, hook: str):
        return not (hook or 'def postRequestHook(').startswith('def postRequestHook(')

    def test_hook(self, data: dict, text: requests.Response):
        hookFunction = postRequestHookForNone
        if data.get('hook') is not None:
            try:
                exec(data.get('hook'), globals())
                hookFunction = postRequestHook
            except Exception as e:
                logging.debug('HOOK CREATION ERROR:', e)
                return None
        try:
            ret = hookFunction(text)
        except Exception as e:
            logging.debug('HOOK EXECUTION ERROR:', e)
            return None
        if ret in ['', None] or (isinstance(ret, str) and len(ret) > 1000):
            return None  # ret could return boolean, so return None if failure
        return ret

    def test_history(self, data: dict):
        historyInstance = None
        if data.get('history') is not None:
            try:
                exec(data.get('history'), globals())
                historyInstance = GetHistory()
            except Exception as e:
                logging.debug('HISTORY CREATION ERROR:', e)
                return False
            if historyInstance is not None:
                try:
                    if not historyInstance.isDone():
                        nextValue = historyInstance.getNext()
                except Exception as e:
                    logging.debug('HISTORY EXECUTION ERROR:', e)
                    return False
                return True  # return nextValue? no, just tell is no err.
        return None

    def save_history(self, data: dict):
        '''
        unlike testing, here we actually get all the history and save it to disk
        but only if there is no data on disk for this stream already.
        this is called only once, during the save new relay stream process.
        pass errors up so we can tell user if they want to try again.
        '''
        def saveOnce():

            def generator():
                while not historyInstance.isDone():
                    yield historyInstance.getNext()

            try:
                saver.saveAll([i for i in generator()])
                return True
            except Exception as e:
                logging.debug(e)
                return False

        def saveIncrementally():
            itts = 0
            while not historyInstance.isDone():
                # save to disk
                saver.saveIncremental(historyInstance.getNext())
                itts += 1
                if itts > 10000:
                    saver.compress()
                    itts = 0
            saver.compress()

        historyInstance = None
        if data.get('history') is not None:
            exec(data.get('history'), globals())
            historyInstance = GetHistory()
            saver = RelayStreamHistorySaver(
                self.start,
                id=StreamId(
                    source=data.get('source', 'satori'),
                    author=self.start.wallet.publicKey,
                    stream=data.get('name'),
                    target=data.get('target')))
            values = historyInstance.getAll()
            success = False
            if (isinstance(values, list) or isinstance(values, pd.DataFrame)) and len(values) > 0:
                success = saver.saveAll(values)
            if not success and not saveOnce():
                saveIncrementally()
            path = saver.pathForDataset()
            saver.report(path, pinAddress=saver.pin(path))
            return True
        return None

# example:
# name: "WeatherBerlin"
# target: "temperature"
# cadence: 3600
# url: "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true"
# uri: "https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true"
# hook: "def postRequestHook(r: str): return json.loads(r).get('current_weather', {}).get('temperature')"


class RelayStreamHistorySaver(object):
    ''' history save to disk '''

    def __init__(self, start: 'StartupDag', id: StreamId, *args):
        super(RelayStreamHistorySaver, self).__init__(*args)
        self.start = start
        self.id: StreamId = id
        self.disk = Disk(id=id)

    def saveAll(self, values: list):
        ''' save this observation to the right parquet file on disk '''
        index = []
        columns = []
        logging.debug('saveAll', values)
        if isinstance(values, list) and len(values) > 0:
            if all([isinstance(v, str) for v in values]):
                index = [str(dt.datetime.utcnow()) for _ in values]
                columns = [self.id.target or '']
            elif all([isinstance(v, list) and len(v) == 2 for v in values]):
                index = [v[0] for v in values]
                columns = [self.id.target or '']
        if isinstance(values, pd.DataFrame) and len(values) > 0:
            index = values.index
            columns = values.columns
            values = values.values
        if len(index) > 0 and len(columns) > 0:
            if len(columns) == 1 and self.id.target is not None:
                df = pd.DataFrame(
                    data=values,
                    index=index,
                    columns=pd.MultiIndex.from_product([
                        [self.id.source],
                        [self.id.author],
                        [self.id.stream],
                        [self.id.target]]))
            else:
                df = pd.DataFrame(
                    data=values,
                    index=index,
                    columns=pd.MultiIndex.from_product([
                        [self.id.source],
                        [self.id.author],
                        [self.id.stream],
                        columns]))
            logging.debug('saveAll df', df)
            self.disk.write(df.sort_index())
            return True
        return False

    def saveIncremental(self, value):
        ''' save this observation to the right parquet file on disk '''
        self.disk.append(Observation({
            'topic': self.id.topic(),
            'data': value
        }).df.copy())

    def compress(self):
        ''' compress incrementals to permanent on disk '''
        try:
            self.disk.compress()
        except Exception as e:
            logging.debug('ERROR: unable to compress:', e)

    def pin(self, path: str = None):
        ''' pins the data to ipfs, returns pin address '''
        return self.start.ipfs.addAndPinDirectory(
            path,
            name=hash.generatePathId(streamId=self.id))

    def report(self, path, pinAddress: str):
        '''
        report's the ipfs address to the satori server.
        ran once, when isDone is True
        '''
        peer = self.start.ipfs.address()
        payload = {
            'author': {'pubkey': self.start.wallet.publicKey},
            'stream': self.id.topic(asJson=False, authorAsPubkey=True),
            'ipfs': pinAddress,
            'disk': system.directorySize(path),
            **({'peer': peer} if peer is not None else {}),
            # 'ipns': not using ipns at the moment.
            # 'count':  count of observations in this pin, we'd have to
            #           go get the values by load the dataset, not worth
            #           it at this time.
        }
        self.start.server.registerPin(pin=payload)
        logging.debug('validation registerPin:', payload)

    def pathForDataset(self):
        return self.disk.path(aggregate=None)
