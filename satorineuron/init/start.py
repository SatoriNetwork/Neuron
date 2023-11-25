# todo create config if no config present, use config if config present
from typing import Union
import json
import time
import threading

from satorilib.utils import colored
import satorineuron
import satoriengine
from satorilib.concepts.structs import StreamId, Stream
from satorilib.api import disk
from satorilib.api.wallet import Wallet
from satorilib.api.ipfs import Ipfs
from satorilib.server import SatoriServerClient
from satorilib.server.api import CheckinDetails
from satorilib.pubsub import SatoriPubSubConn
from satorineuron import logging
from satorineuron import config
from satorineuron.relay import RawStreamRelayEngine, ValidateRelayStream
# from satorilib.api.udp.rendezvous import UDPRendezvousConnection # todo: remove from lib
# from satorineuron.rendezvous import rendezvous
from satorineuron.retro import Retro
from satorineuron.rendezvous.structs.domain import SignedStreamId


class StartupDag(object):
    ''' a DAG of startup tasks. '''

    def __init__(self, urlServer: str = None, urlPubsub: str = None, *args):
        super(StartupDag, self).__init__(*args)
        self.urlServer: str = urlServer
        self.urlPubsub: str = urlPubsub
        self.paused: bool = False
        self.pauseThread: Union[threading.Thread, None] = None
        self.wallet: Wallet
        self.details: dict
        self.key: str
        self.idKey: str
        self.subscriptionKeys: str
        self.publicationKeys: str
        self.ipfs: Ipfs = Ipfs()
        self.signedStreamIds: list[SignedStreamId]
        self.relayValidation: ValidateRelayStream
        self.server: SatoriServerClient
        self.pubsub: SatoriPubSubConn = None
        # self.peer: rendezvous.RendezvousEngine
        self.retro: Retro = None
        self.relay: RawStreamRelayEngine = None
        self.engine: satoriengine.Engine
        self.publications: list[Stream] = []
        self.subscriptions: list[Stream] = []

    def start(self):
        ''' start the satori engine. '''
        self.createRelayValidation()
        self.openWallet()
        self.checkin()
        self.buildEngine()
        self.pubsubConnect()
        self.startRelay()
        # TODO NEXT: get authentication working and everything else
        # self.rendezvousConnect()
        self.retroConnect()
        # self.downloadDatasets()

    def createRelayValidation(self):
        self.relayValidation = ValidateRelayStream(start=self)

    def openWallet(self):
        self.wallet = Wallet(config.walletPath('wallet.yaml'))()

    def checkin(self):
        self.server = SatoriServerClient(self.wallet, url=self.urlServer)
        self.details = CheckinDetails(self.server.checkin())
        self.key = self.details.key
        self.idKey = self.details.idKey
        self.subscriptionKeys = self.details.subscriptionKeys
        self.publicationKeys = self.details.publicationKeys
        self.subscriptions = [
            Stream.fromMap(x)
            for x in json.loads(self.details.subscriptions)]
        self.publications = [
            Stream.fromMap(x)
            for x in json.loads(self.details.publications)]
        self.signedStreamIds = [
            SignedStreamId(
                source=s.id.source,
                author=s.id.author,
                stream=s.id.stream,
                target=s.id.target,
                publish=False,
                subscribe=True,
                signature=sig,  # doesn't the server need my pubkey?
                signed=self.wallet.sign(sig)) for s, sig in zip(
                    self.subscriptions,
                    self.subscriptionKeys)
        ] + [
            SignedStreamId(
                source=p.id.source,
                author=p.id.author,
                stream=p.id.stream,
                target=p.id.target,
                publish=False,
                subscribe=True,
                signature=sig,  # doesn't the server need my pubkey?
                signed=self.wallet.sign(sig)) for p, sig in zip(
                    self.publications,
                    self.publicationKeys)]

    def buildEngine(self):
        ''' start the engine, it will run w/ what it has til ipfs is synced '''
        def predictionStreams(streams: list[Stream]):
            ''' filter down to prediciton publications '''
            return [s for s in streams if s.predicting is not None]

        self.engine: satoriengine.Engine = satorineuron.init.getEngine(
            subscriptions=self.subscriptions,
            publications=predictionStreams(self.publications),
            start=self)
        self.engine.run()

    def pubsubConnect(self):
        ''' establish a pubsub connection. '''
        if self.pubsub is not None:
            self.pubsub.disconnect()
            self.pubsub = None
        if self.key:
            signature = self.wallet.sign(self.key)
            self.pubsub = satorineuron.init.establishConnection(
                url=self.urlPubsub,
                pubkey=self.wallet.publicKey,
                key=signature.decode() + '|' + self.key,
                start=self)
        else:
            raise Exception('no key provided by satori server')

    def rendezvousConnect(self):
        ''' establish a rendezvous connection. '''
        # if self.idKkey: # rendezvous has changed, instead of sending just our
        # ID key, we need to send our signed stream ids in a subscription msg.
        if self.key:
            self.peer = rendezvous.RendezvousEngine(
                peer=rendezvous.generatePeer(
                    signature=self.wallet.sign(self.key),
                    signed=self.key,
                    signedStreamIds=self.signedStreamIds),
                start=self)
        else:
            raise Exception('no key provided by satori server')

    def retroConnect(
        self,
        subscriptions: Union[list, None] = None,
        extraSubscriptions: Union[list, None] = None,
    ):
        '''
        establish a retro connection. we can subscribe to anything in retro 
        so allow override or additional subscriptions here.
        '''
        if self.retro is not None:
            self.retro.disconnect()
            self.retro = None
        if self.key:
            signature = self.wallet.sign(self.key)
            self.retro = satorineuron.init.establishConnection(
                url=self.urlPubsub,
                pubkey=self.wallet.publicKey,
                key=signature.decode() + '|' + self.key,
                subscriptions=subscriptions or (
                    self.subscriptions + (extraSubscriptions or [])),
                start=self)
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
            self.relay.kill()
        self.relay = RawStreamRelayEngine(
            start=self, streams=append(self.publications))
        self.relay.run()

    def downloadDatasets(self):
        '''
        download pins (by ipfs address) received from satori server:
        look at each pin, if not up to date, download it to temporary disk,
        merge on disk, tell models to pull data again.
        '''
        def threadedDownload(
            ipfsAddress: str,
            ipfsStream: StreamId,
            ipfsPeer: str,
            diskApi: disk.Disk,
        ):
            # TODO:
            # if this fails ask the server for all the pins of this stream.
            # the other pins will be reported by the subscribers. download
            # them at random. or latest updated or oldest stream? idk.

            # go get the ipfs history and merge it in to the dataset.
            self.ipfs.connectIfMissing(peer=ipfsPeer)
            self.ipfs.get(
                hash=ipfsAddress,
                abspath=diskApi.path(aggregate=None, temp=True))
            diskApi.compress(includeTemp=True)
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
        pins = self.details.pins
        if isinstance(pins, str):
            pins = json.loads(pins)
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

    def incrementallyDownloadDatasets(self):
        '''
        download pins incrementally by using our p2p rendezvous network:
        (pins must be signed by self and server for rendezvous to authenticate)
        for each pin, within it's own thread trigger a download process,
        during that process send every observation to the Data Manager via 
        rx streams. the data manager will merge them in memory and write to disk
        if necessary. beautiful.
        '''
        # todo: is a pin already signed, etc?
        # we don't really need a pin do we? we need a signed stream. which we
        # should have already received from the server and parsed into objects.
        # we should make the peer prior to this elsewhere, like this:
        # this is something we need to do on a periodic basis, and not right
        # as soon as we start up. so like the engine, and the relay service,
        # this should be run in a separate thread... which will cycle through
        # our streamIds and gather history for each one periodically.
        self.peer.run()

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
