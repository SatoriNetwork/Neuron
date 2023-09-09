# todo create config if no config present, use config if config present
import json
import time
import threading
import satorineuron
from satorilib.concepts.structs import StreamId, Stream
from satorilib.api import disk
from satorilib.api.wallet import Wallet
from satorilib.api.ipfs import Ipfs
from satorilib.server import SatoriServerClient
from satorilib.pubsub import SatoriPubSubConn
from satorilib.api.udp.rendezvous import UDPRendezvousConnection
from satorineuron import logging
from satorineuron import config
from satorineuron.relay import RawStreamRelayEngine, ValidateRelayStream


class StartupDag(object):
    ''' a DAG of startup tasks. '''

    def __init__(self, urlServer: str = None, urlPubsub: str = None, *args):
        super(StartupDag, self).__init__(*args)
        self.full = True
        self.urlServer = urlServer
        self.urlPubsub = urlPubsub
        self.paused = False
        self.pauseThread = None
        self.wallet = None
        self.details = None
        self.key = None
        self.idKey = None
        self.subscriptionKeys = None
        self.publicationKeys = None
        self.ipfs: Ipfs = None
        self.relayValidation: ValidateRelayStream = None
        self.server: SatoriServerClient = None
        self.pubsub: SatoriPubSubConn = None
        self.rendezvous: UDPRendezvousConnection = None
        self.relay: RawStreamRelayEngine = None
        self.engine: satorineuron.engine.Engine = None
        self.publications: list[Stream] = []
        self.subscriptions: list[Stream] = []

    def start(self):
        ''' start the satori engine. '''
        if self.full:
            self.createRelayValidation()
            self.ipfsCli()
            self.openWallet()
            self.checkin()
            self.buildEngine()
            self.connect()
            self.rendezvousConnect()
            self.startRelay()
            self.downloadDatasets()

    def createRelayValidation(self):
        self.relayValidation = ValidateRelayStream(start=self)

    def ipfsCli(self):
        self.ipfs = Ipfs()

    def openWallet(self):
        self.wallet = Wallet(config.walletPath('wallet.yaml'))()

    def checkin(self):
        self.server = SatoriServerClient(self.wallet, url=self.urlServer)
        self.details = self.server.checkin()
        self.key = self.details.get('key')
        self.idKey = self.details.get('idKey')
        self.subscriptionKeys = self.details.get('subscriptionKeys')
        self.publicationKeys = self.details.get('publicationKeys')
        self.publications = [
            Stream.fromMap(x)
            for x in json.loads(self.details.get('publications'))]
        logging.debug("publications:", self.publications)
        self.subscriptions = [
            Stream.fromMap(x)
            for x in json.loads(self.details.get('subscriptions'))]

    def buildEngine(self):
        ''' start the engine, it will run w/ what it has til ipfs is synced '''
        def predictionStreams(streams: list[Stream]):
            ''' filter down to prediciton publications '''
            return [s for s in streams if s.predicting is not None]

        self.engine = satorineuron.init.getEngine(
            subscriptions=self.subscriptions,
            publications=predictionStreams(self.publications),
            start=self)
        self.engine.run()

    def connect(self):
        ''' establish a pubsub connection. '''
        if self.pubsub is not None:
            self.pubsub.disconnect()
            self.pubsub = None
        if self.key:
            signature = self.wallet.sign(self.key)
            self.pubsub = satorineuron.init.establishConnection(
                url=self.urlPubsub,
                pubkey=self.wallet.publicKey,
                key=signature + '|' + self.key,
                start=self)
        else:
            raise Exception('no key provided by satori server')

    def rendezvousConnect(self):
        ''' establish a rendezvous connection. '''
        if self.idKey:
            signature = self.wallet.sign(self.idKey)
            self.rendezvous = UDPRendezvousConnection(
                signature=signature,
                key=self.idKey,
                messageCallback=None,)  # todo: replace with function
        else:
            raise Exception('no key provided by satori server')

    def startRelay(self):
        def append(streams: list[Stream]):
            relays = satorineuron.config.get('relay')
            rawStreams = []
            for x in streams:
                topic = x.streamId.topic(asJson=True)
                if topic in relays.keys():
                    x.uri = relays.get(topic).get('uri')
                    x.headers = relays.get(topic).get('headers')
                    x.payload = relays.get(topic).get('payload')
                    x.hook = relays.get(topic).get('hook')
                    x.history = relays.get(topic).get('history')
                    rawStreams.append(x)
            return rawStreams

        if self.relay is not None:
            logging.debug('killing!')
            self.relay.kill()
            logging.debug('done killing!')
        self.relay = RawStreamRelayEngine(
            start=self, streams=append(self.publications))
        self.relay.run()

    def downloadDatasets(self):
        ''' download pins (by ipfs address) received from satori server. '''
        def threadedDownload(ipfsAddress, ipfsStream, ipfsPeer, diskApi):
            # TODO:
            # if this fails ask the server for all the pins of this stream.
            # the other pins will be reported by the subscribers. download
            # them at random. or latest updated or oldest stream? idk.

            # go get the ipfs history and merge it in to the dataset.
            # logging.debug('diskApi.readBoth()')
            # logging.debug(diskApi.readBoth(temp=True))
            # logging.debug('ipfs.get')
            logging.debug('IPFSSTREAM', ipfsStream)
            logging.debug(self.ipfs.connectIfMissing(peer=ipfsPeer))
            logging.debug(self.ipfs.get(
                hash=ipfsAddress,
                abspath=diskApi.path(aggregate=None, temp=True)))
            logging.debug('merging...')
            diskApi.compress(includeTemp=True)
            # logging.debug('ipfs.get2')
            # logging.debug(ipfs.get(
            #    hash=ipfs,
            #    abspath=diskApi.path(aggregate=None, temp=True)))
            # tell models that use this dataset to go get all their data.
            for model in self.engine.models:
                if model.variable == ipfsStream:
                    model.inputsUpdated.on_next(True)
                else:
                    for target in model.targets:
                        if target == ipfsStream:
                            model.inputsUpdated.on_next(True)

        # we should make the download run in parellel so using async functions
        # here. but in the meantime, we'll do them sequentially.
        threads = {}
        pins = self.details.get('pins')
        if isinstance(pins, str):
            pins = json.loads(pins)
        logging.debug('pins', pins)
        for pin in [p for p in pins if p.get('pin_author') == p.get('stream_author')]:
            ipfsAddress = pin.get('ipfs')
            ipfsPeer = pin.get('peer')
            ipfsStream = StreamId(
                source=pin.get('stream_source'),
                author=pin.get('stream_author'),
                stream=pin.get('stream_stream'),
                target=pin.get('stream_target'))
            diskApi = disk.Disk(id=ipfsStream)
            if (
                ipfsAddress is not None and
                ipfsAddress != self.ipfs.hashOfDirectory(
                    abspath=diskApi.path(aggregate=None, temp=False))
            ):
                threads[ipfsAddress] = threading.Thread(
                    target=threadedDownload,
                    args=[ipfsAddress, ipfsStream, ipfsPeer, diskApi],
                    daemon=True)
                threads[ipfsAddress].start()

    def pause(self, timeout: int = 60):
        ''' pause the engine. '''
        def pauseEngineFor():
            # self.engine.pause()
            self.paused = True
            time.sleep(timeout)
            # self.engine.unpause()
            self.paused = False
            self.pauseThread = None

        thread = threading.Thread(target=pauseEngineFor, daemon=True)
        thread.start()
        self.pauseThread = thread

    def unpause(self):
        ''' pause the engine. '''
        # self.engine.unpause()
        self.paused = False
        self.pauseThread = None
