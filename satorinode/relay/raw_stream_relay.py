'''
raw stream relay is a process, like a mini-engine, that checks a list of real
world apis for new data, and then relays that data to the satori pubsub network.
note: we don't need to save it locally (and pin it) or notify the models because
if we subscribe to this we'll do that automatically. if we don't subscribe to it
maybe someone else will, and they'll pin it. if nobody subscribes to it we don't
need it's history. maybe we should subscribe to our own relay streams by defult.
'''
import threading
import time
import json
import requests
from functools import partial

from satorilib.concepts.structs import Stream
from satorilib import logging


def postRequestHookForNone(r: requests.Response):
    logging.debug('postRequestHook default method')
    return r.text


def postRequestHook(r: requests.Response):
    logging.debug('postRequestHook default method')
    return r.text


class RawStreamRelayEngine:
    def __init__(
        self,
        start=None,
        streams: list[Stream] = None,
    ):
        self.start = start
        self.streams: list[Stream] = streams or []
        self.thread = None
        self.killed = False
        self.latest = {}

    def status(self):
        if self.killed:
            return 'stopping'
        if self.thread == None:
            return 'stopped'
        if self.thread.is_alive():
            return 'running'
        # should we restart the thread if it dies? we shouldn't see this:
        return 'unknown'

    @staticmethod
    def call(stream: Stream):
        ''' calls API and relays data to pubsub '''

        def is_valid_json(x):
            try:
                json.loads(x)
                return True
            except Exception as _:
                return False

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
            hookFunction = postRequestHookForNone
            if stream.hook is not None or (isinstance(stream.hook, str) and stream.hook.strip() == ''):
                try:
                    exec(stream.hook, globals())
                    hookFunction = postRequestHook
                except Exception as e:
                    logging.debug('HOOK CREATION ERROR 1:', e)
                    return None
            try:
                text = hookFunction(r)
            except Exception as e:
                logging.debug('HOOK EXECUTION ERROR 2:', e)
                return None
            if text in ['', None] or (isinstance(text, str) and len(text) > 1000):
                return None  # ret could return boolean, so return None if failure
            logging.debug('called!', text)
            return text
        return None

    def relay(self, stream: Stream, data: str = None):
        ''' relays data to pubsub '''
        # if stream.streamId.source == 'satori':
        #    self.start.pubsub.publish(topic: stream.streamId.target, data: data)
        # else:
        #    send to streamr or something
        self.latest[stream.streamId.topic()] = data
        self.start.pubsub.publish(topic=stream.streamId.topic(), data=data)

    def callRelay(self, stream: Stream):
        ''' calls API and relays data to pubsub '''
        result = RawStreamRelayEngine.call(stream)
        if (result is not None):
            self.relay(stream, data=result)
        else:
            # log or flash message or something...
            logging.debug(
                'result is None, something is wrong, maybe the API is down?')

    def runForever(self):
        def cadence(stream: Stream):
            ''' returns cadence in seconds, engine does not allow < 60 '''
            return max(stream.cadence or 60, 60)

        start = int(time.time())
        while not self.killed:
            now = int(time.time())
            for stream in self.streams:
                if (now - start) % cadence(stream) == 0:
                    threading.Thread(
                        target=self.callRelay,
                        args=[stream]).start()
            time.sleep(.99999)

    def run(self):
        self.thread = threading.Thread(target=self.runForever, daemon=True)
        self.thread.start()

    def kill(self):
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
