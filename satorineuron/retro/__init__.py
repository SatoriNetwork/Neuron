''' connection to retro server '''

# todo create config if no config present, use config if config present
from itertools import product
from functools import partial
import pandas as pd
from satorilib.api import memory
from satorilib.concepts import Observation, Stream, StreamId
from satorilib.retro import SatoriRetroConn
from satoriengine.concepts import HyperParameter
from satoriengine.model import metrics
from satoriengine import ModelManager, Engine, DataManager
from satorineuron import config
from satorineuron import logging
from satorineuron.init.start import StartupDag


class Retro():

    def __init__(self):
        self.conn = self.establishConnection('',  '', None, '')

    def establishConnection(self, pubkey: str, key: str, start: StartupDag, url: str = None):
        ''' establishes a connection to the satori server, returns connection object '''

        def router(response: str):
            '''
            handle messages from retro server 
            (requests on published streams)
            (responses on subscribed streams)
            (failures)
            '''
            if response != 'failure: error, a minimum 10 seconds between publications per topic.':
                pass
                #if response confroms to the response retro protocol:
                    # parse response and either save observations to disk, or compare hashes, etc.
                #if response confroms to the request retro protocol and I publish the indicated stream:
                    # parse response and either supply observations, or hashes, etc.
                
        return SatoriRetroConn(
            uid=pubkey,
            router=router,
            payload=key,
            url=url)
        # payload={
        #    'publisher': ['stream-a'],
        #    'subscriptions': ['stream-b', 'stream-c', 'stream-d']})
