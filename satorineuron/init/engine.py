from satorilib import logging
from satorilib.api import memory
from satorilib.concepts import Observation, Stream
from satorilib.pubsub import SatoriPubSubConn
from satoriengine.concepts import HyperParameter
from satoriengine.model import metrics
from satoriengine import ModelManager, Engine, DataManager
from satorineuron import config
import copy


def establishConnection(pubkey: str, key: str, url: str = None, onConnect: callable = None, onDisconnect: callable = None, emergencyRestart: callable = None, subscription: bool = True):
    ''' establishes a connection to the satori server, returns connection object '''
    from satorineuron.init.start import getStart

    def router(response: str):
        ''' TODO: may need to conform response to the observation format first. '''
        # couldn't we move the new data into this function itself? why route the
        # data to the data manager, just to route it to the models only? data
        # manager seems like a extra thread that isn't necessary, a middle man.

        # response:
        # {"topic": "{\"source\": \"satori\", \"author\": \"021bd7999774a59b6d0e40d650c2ed24a49a54bdb0b46c922fd13afe8a4f3e4aeb\", \"stream\": \"coinbaseALGO-USD\", \"target\": \"data.rates.ALGO\"}", "data": "0.23114999999999997"}
        if response != 'failure: error, a minimum 10 seconds between publications per topic.':
            if response.startswith('{"topic":') or response.startswith('{"data":'):
                logging.info('received message:', response, print=True)
                getStart().engine.data.newData.on_next(Observation.parse(response))

        # furthermore, shouldn't we do more than route it to the correct models?
        # like, shouldn't we save it to disk, compress if necessary, pin, and
        # report the pin to the satori server? like so:
        # def save(self, stream: Stream, data: str = None):
        #     ''' saves data to local disk '''
        # def pin(self, stream: Stream, data: str = None):
        #     ''' pins the data to ipfs '''
        # def report(self, stream: Stream, ipfsAddress: str = None):
        #     ''' report's the ipfs address to the satori server '''
        # self.save(stream, data=result)
        # self.report(stream, self.pin(stream, data=result))
        # ...
        # after revewing the data manger I see it handles lots of edge cases,
        # such as not relaying duplicate values, etc. so it seems its more than
        # just a function, and shouldn't be eliminated.

    logging.info(
        'subscribing to:' if subscription else 'publishing to:', url)
    return SatoriPubSubConn(
        uid=pubkey,
        router=router if subscription else None,
        payload=key,
        url=url,
        emergencyRestart=emergencyRestart,
        onConnect=onConnect,
        onDisconnect=onDisconnect)
    # payload={
    #    'publisher': ['stream-a'],
    #    'subscriptions': ['stream-b', 'stream-c', 'stream-d']})


# accept optional data necessary to generate models data and learner


def getEngine(
    subscriptions: list[Stream],
    publications: list[Stream],
) -> Engine:
    ''' starts the Engine. returns Engine. '''
    from satorineuron.init.start import getStart

    def generateModelManager():
        ''' generate a set of Model(s) for Engine '''

        # # unused
        # def generateCombinedFeature(
        #    df: pd.DataFrame = None,
        #    columns: list[tuple] = None,
        #    prefix='Diff'
        # ):
        #    '''
        #    example of making a feature out of data you know ahead of time.
        #    most of the time you don't know what kinds of data you'll get...
        #    '''
        #    def name():
        #        return (columns[0][0], columns[0][1], f'{prefix}{columns[0][2]}{columns[1][2]}')
        #
        #    if df is None:
        #        return name()
        #    columns = columns or []
        #    feature = df.loc[:, columns[0]] - df.loc[:, columns[1]]
        #    feature.name = name()
        #    return feature

        # these will be sensible defaults based upon the patterns in the data
        kwargs = {
            'hyperParameters': [
                HyperParameter(
                    name='lookback_len',
                    value=1,
                    kind=int,
                    limit=1,
                    minimum=1,
                    maximum=64),
                HyperParameter(
                    name='n_estimators',
                    value=300,
                    kind=int,
                    limit=100,
                    minimum=200,
                    maximum=5000),
                HyperParameter(
                    name='learning_rate',
                    value=0.3,
                    kind=float,
                    limit=.05,
                    minimum=.01,
                    maximum=.1),
                HyperParameter(
                    name='max_depth',
                    value=6,
                    kind=int,
                    limit=1,
                    minimum=10,
                    maximum=2),
                HyperParameter(
                    name='early_stopping_rounds',
                    value=200,
                    kind=int,
                    limit=1,
                    minimum=100,
                    maximum=400),
            ],
            'xgbParams': ['n_estimators','learning_rate','max_depth','early_stopping_rounds'],
            'metrics':  {
                # raw data features
                'Raw': metrics.rawDataMetric,
                # daily percentage change, 1 day ago, 2 days ago, 3 days ago...
                # **{f'Daily{i}': partial(metrics.dailyPercentChangeMetric, yesterday=i) for i in list(range(1, 31))},
                # rolling period transformation percentage change, max of the last 7 days, etc...
                # **{f'Rolling{tx[0:3]}{i}': partial(metrics.rollingPercentChangeMetric, window=i, transformation=tx)
                #    for tx, i in product('sum() max() min() mean() median() std()'.split(), list(range(2, 21)))},
                # rolling period transformation percentage change, max of the last 50 or 70 days, etc...
                # **{f'Rolling{tx[0:3]}{i}': partial(metrics.rollingPercentChangeMetric, window=i, transformation=tx)
                #    for tx, i in product('sum() max() min() mean() median() std()'.split(), list(range(22, 90, 7)))}
            },
            # 'features': {
            #    ('streamrSpoof', 'simpleEURCleanedHL', 'DiffHighLow'):
            #        partial(
            #            generateCombinedFeature,
            #            columns=[
            #                ('streamrSpoof', 'simpleEURCleanedHL', 'High'),
            #                ('streamrSpoof', 'simpleEURCleanedHL', 'Low')])
            # },
        }
        return {
            ModelManager(
                variable=publication.predicting,
                output=publication.id,
                targets=[
                    subscription.id
                    # will be unique by publication, no need to enforce
                    for subscription in subscriptions
                    if (
                        subscription.reason is not None and
                        subscription.reason.source == publication.id.source and
                        subscription.reason.author == publication.id.author and
                        subscription.reason.stream == publication.id.stream and
                        subscription.reason.target == publication.id.target
                    )],
                chosenFeatures=[(
                    subscription.id.source,
                    subscription.id.author,
                    subscription.id.stream,
                    subscription.id.target)
                    # will be unique by publication, no need to enforce
                    for subscription in subscriptions
                    if (
                        subscription.reason is not None and
                        subscription.reason.source == publication.id.source and
                        subscription.reason.author == publication.id.author and
                        subscription.reason.stream == publication.id.stream and
                        subscription.reason.target == publication.id.target
                )],
                memory=memory.Memory,
                **copy.deepcopy(kwargs))
            # if publication.id in getStart().caches.keys()
            for publication in publications
        }

    ModelManager.setConfig(config)
    # DataManager.setConfig(config)
    modelManager = generateModelManager()
    dataMananger = DataManager(getStart=getStart)
    return Engine(
        getStart=getStart,
        data=dataMananger,
        models=modelManager)
