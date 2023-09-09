import json
import time
from satoricentral.utils import Crypt
from satorilib.pubsub import SatoriPubSubConn


def run():
    wait = 20
    conn = Client(
        uid='pubkey-b',
        payload={
            'publisher': ['stream-b'],
            'subscriptions': ['stream-a', 'stream-c', 'stream-d']})
    while True:
        time.sleep(wait)
        conn.publish(topic='stream-b', data='data for stream-b')
        time.sleep(wait)
    conn.disconnect()


run()
