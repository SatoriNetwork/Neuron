# requires that you disable decryption on pubsub first

import json
from satoriserver.web.watcher import SatoriPubSubConn
akey = '{"publisher": [{"source": "SATORI", "author": "a", "stream": "stream1_p", "target": "target"}], "subscriptions": [{"source": "SATORI", "author": "b", "stream": "stream3", "target": "target"}]}'
bkey = '{"publisher": [{"source": "SATORI", "author": "b", "stream": "stream3", "target": "target"}], "subscriptions": [{"source": "SATORI", "author": "a", "stream": "stream1_p", "target": "target"}]}'
a = SatoriPubSubConn(uid='a', payload=akey)
b = SatoriPubSubConn(uid='b', payload=bkey)
a.publish(topic=json.dumps({"source": "SATORI", "author": "a",
          "stream": "stream1_p", "target": "target"}), data='123')
b.publish(topic=json.dumps({"source": "SATORI", "author": "b",
          "stream": "stream3", "target": "target"}), data='456')
