'''
raw stream relay is a process, like a mini-engine, that checks a list of real
world apis for new data, and then relays that data to the satori pubsub network.
note: we don't need to save it locally (and pin it) or notify the models because
if we subscribe to this we'll do that automatically. if we don't subscribe to it
maybe someone else will, and they'll pin it. if nobody subscribes to it we don't
need it's history. maybe we should subscribe to our own relay streams by defult.
'''
from typing import Union
import threading
import time
import json
import requests
from functools import partial
from satorilib.concepts.structs import Stream, StreamId
from satorilib.api.disk import Cached
from satorilib.api.disk.cache import CachedResult
from satorilib import logging


def postRequestHookForNone(r: requests.Response):
    # logging.info('postRequestHook default method')
    return r.text


def postRequestHook(r: requests.Response):
    # logging.info('postRequestHook default method')
    return r.text


class RawStreamRelayEngine(Cached):
    def __init__(
        self,
        streams: list[Stream] = None,
    ):
        self.streams: list[Stream] = streams or []
        self.thread = None
        self.killed = False
        self.latest = {}
        self.active = 0  # the thread that should be active

    def status(self):
        if self.killed:
            return 'stopping'
        if self.thread == None:
            return 'stopped'
        if self.thread.is_alive():
            return 'running'
        # should we restart the thread if it dies? we shouldn't see this:
        return 'unknown'

    def late(self, streamId: StreamId, mostRecentTSinSeconds: float) -> bool:
        ''' 
        returns false if the mostRecentTSinSeconds falls within the recent 
        past according to the cadence and true if it's older than the cadence
        should allow
        '''
        stream = self._getStreamFor(streamId)
        if stream is not None:
            # return mostRecentTSinSeconds < (int(time.time()) - self._cadence(stream)) # more intuitive I think
            return int(time.time()) > (mostRecentTSinSeconds + self._cadence(stream) + self._offset(stream))
        return True

    @staticmethod
    def call(stream: Stream) -> Union[requests.Response, None]:
        ''' calls API and relays data to pubsub '''

        def is_valid_json(x):
            try:
                json.loads(x)
                return True
            except Exception as _:
                return False

        if stream.uri is None or stream.uri.strip() == '':
            r = requests.Response()
            r.status_code = 200
            return r
        if stream.payload is None:
            method = partial(requests.get)
        else:
            if is_valid_json(stream.payload):
                method = partial(requests.post, json=stream.payload)
            else:
                method = partial(requests.post, data=stream.payload)
        if stream.headers not in ['', None]:
            if is_valid_json(stream.headers):
                r = method(
                    stream.uri,
                    headers=json.loads(stream.headers),)
            elif (
                not is_valid_json(stream.headers) and
                "'" in stream.headers and
                '"' not in stream.headers
            ):
                stream.headers = stream.headers.replace("'", '"')
                r = method(
                    stream.uri,
                    headers=json.loads(stream.headers))
            else:
                r = method(stream.uri, headers=stream.headers)
        else:
            r = method(stream.uri)
        if r.status_code == 200:
            return r
        return None

    @staticmethod
    def callHook(stream: Stream, r: requests.Response):
        hookFunction = postRequestHookForNone
        if stream.hook is not None or (isinstance(stream.hook, str) and stream.hook.strip() == ''):
            try:
                exec(stream.hook, globals())
                hookFunction = postRequestHook
            except Exception as e:
                logging.error('HOOK CREATION ERROR 1:', e)
                return None
        try:
            text = hookFunction(r)
        except Exception as e:
            logging.error('HOOK EXECUTION ERROR 2:', e)
            return None
        if text in ['', None] or (isinstance(text, str) and len(text) > 1000):
            return None  # ret could return boolean, so return None if failure
        return text

    def relay(
        self,
        stream: Stream, data: str = None,
        timestamp: str = None, observationHash: str = None
    ):
        ''' relays data to pubsub '''
        from satorineuron.init.start import getStart
        logging.info(
            'outgoing message:',
            f'{stream.streamId.source}.{stream.streamId.stream}.{stream.streamId.target}',
            data, timestamp, print=True)
        getStart().publish(
            topic=stream.streamId.topic(),
            data=data,
            observationTime=timestamp,
            observationHash=observationHash)
        getStart().server.publish(
            topic=stream.streamId.topic(),
            data=data,
            observationTime=timestamp,
            observationHash=observationHash,
            isPrediction=False)

    def save(self, stream: Stream, data: str = None) -> CachedResult:
        self.latest[stream.streamId.topic()] = data
        self.streamId = stream.streamId  # required by Cache
        return self.disk.appendByAttributes(value=data, hashThis=True)

    def callRelay(self, streams: list[Stream]) -> bool:
        '''
        calls API and relays data to pubsub
        the list of streams should all have the same URI and cadence and headers
        and payload. Then we can only make 1 call and parse it out according to
        the details of each stream.
        '''
        result = RawStreamRelayEngine.call(streams[0])
        successes = []
        if result is not None:
            for stream in streams:
                hookResult = RawStreamRelayEngine.callHook(stream, result)
                if hookResult is not None:
                    cachedResult = self.save(stream, data=hookResult)
                    if cachedResult.success:
                        self.relay(
                            stream,
                            data=hookResult,
                            timestamp=cachedResult.time,
                            observationHash=cachedResult.hash)
                        successes.append(True)
                    else:
                        # log or flash message or something...
                        successes.append(False)
                        logging.error(
                            'Unable to save data for stream: ',
                            f'{stream.streamId.stream}.{stream.streamId.target}',
                            print=True)
                else:
                    # log or flash message or something...
                    logging.error(
                        'Unable to interpret information for stream: ',
                        f'{stream.streamId.stream}.{stream.streamId.target}',
                        print=True)
        else:
            # log or flash message or something...
            logging.error(
                'Call for stream failed, API is down? ',
                f'{streams[0].streamId.stream}.{streams[0].streamId.target}',
                print=True)

        if len(successes) > 0 and all(successes):
            return True
        return False

    def _getStreamFor(self, streamId: StreamId) -> Union[Stream, None]:
        for stream in self.streams:
            if stream.streamId == streamId:
                return stream
        return None

    def triggerManually(self, streamId: StreamId) -> bool:
        ''' called from UI '''
        stream = self._getStreamFor(streamId)
        if stream is not None:
            return self.callRelay([stream])
        return False

    def _cadence(self, stream: Stream) -> int:
        ''' returns cadence in seconds, engine does not allow < 60 '''
        return int(max(stream.cadence or Stream.minimumCadence, Stream.minimumCadence))

    def _offset(self, stream: Stream) -> int:
        ''' returns cadence in seconds, engine does not allow < 60 '''
        return int(stream.offset or 0)

    def runForever(self, active: int):
        # though I would like to use the asyncThread for this, as it would be
        # simpler to reason about, I'm not sure how I would reduce the number
        # of api calls as we are doing here (see uri logic) for streams that all
        # call the same api. so we're leaving it as is.

        while self.active == active:
            now = int(time.time())
            streams: list[Stream] = []
            for stream in self.streams:
                if (now + self._offset(stream)) % self._cadence(stream) == 0:
                    streams.append(stream)
            if len(streams) > 0:
                segmentedStreams: dict[str, list[Stream]] = {}
                for stream in streams:
                    uri = (stream.uri + str(stream.headers) +
                           str(stream.payload))
                    if uri not in segmentedStreams.keys():
                        segmentedStreams[uri] = []
                    segmentedStreams[uri].append(stream)
                for _, ss in segmentedStreams.items():
                    threading.Thread(
                        target=self.callRelay,
                        args=(ss,)).start()
            newNow = time.time()
            if int(newNow) == now:
                try:
                    # wait till the next stream
                    seconds = min([
                        self._cadence(stream) - ((int(newNow) + self._offset(stream)) %
                                                 self._cadence(stream))
                        for stream in self.streams])
                except Exception as e:
                    logging.error(
                        '\n err ',
                        e, color='red')
                    # wait till the next second
                    seconds = (int(newNow)+1)-newNow
                time.sleep(seconds)

    def run(self):
        if len(self.streams) > 0:
            self.thread = threading.Thread(
                target=self.runForever,
                args=(self.active,),
                daemon=True)
            self.thread.start()
        else:
            logging.info('no streams to relay')

    def kill(self):
        self.active += 1
        self.killed = True
        time.sleep(3)
        self.thread = None
        self.killed = False


# test
# a = Stream(name='A', cadence=5)
# b = Stream(name='B', cadence=6)
# c = Stream(name='C', cadence=7)
# x = RawStreamRelayEngine(streams=[a, b, c])
# x.runForever()
