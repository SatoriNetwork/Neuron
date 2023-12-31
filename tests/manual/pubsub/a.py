import json
import time
from satoricentral.utils import Crypt
from satoricentral.pubsub.client.client import Client


def run():
    wait = 30
    conn = Client(
        uid='pubkey-a',
        payload={
            'publisher': ['stream-a'],
            'subscriptions': ['stream-b', 'stream-c', 'stream-d']})
    while True:
        time.sleep(wait)
        conn.publish(topic='stream-a', data='data for stream-a')
        time.sleep(wait)
    conn.disconnect()


run()
