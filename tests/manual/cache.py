
import os
import sys
from satorilib.concepts import StreamId
from satorineuron.init.start import StartupDag
from satorineuron import config
s = StreamId(author='author', source='satori', stream='stream')
ENV = config.get().get('env', os.environ.get(
    'ENV', os.environ.get('SATORI_RUN_MODE', 'dev')))
start = StartupDag(
    env=ENV,
    urlServer={
        # TODO: local endpoint should be in a config file.
        'local': 'http://192.168.0.10:5002',
        'dev': 'http://localhost:5002',
        'test': 'https://test.satorinet.io',
        'testprod': 'https://stage.satorinet.io',
        'prod': 'https://stage.satorinet.io'}[ENV],
    urlMundo={
        'local': 'http://192.168.0.10:5002',
        'dev': 'http://localhost:5002',
        'test': 'https://test.satorinet.io',
        'testprod': 'https://mundo.satorinet.io:24607',
        'prod': 'https://mundo.satorinet.io:24607'}[ENV],
    urlPubsubs={
        'local': ['ws://192.168.0.10:24603'],
        'dev': ['ws://localhost:24603'],
        'test': ['ws://test.satorinet.io:24603'],
        'testprod': ['ws://pubsub1.satorinet.io:24603'],
        'prod': ['ws://pubsub1.satorinet.io:24603']}[ENV],
    isDebug=sys.argv[1] if len(sys.argv) > 1 else False)
