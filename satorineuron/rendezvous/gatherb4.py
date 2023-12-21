from typing import Union
import time
import datetime as dt
import pandas as pd
from satorilib import logging
from satorilib.api.time import datetimeFromString, now
from satorineuron.rendezvous.structs.message import PeerMessage, PeerMessages

# this is the original version and it seemed to work fine, but it is overly
# complex in such a way that we're always getting this history backwards and
# eventually attaching it to the root. When in reality we should just get it
# in chronological order, it's much simpler that way.


class GathererBefore():
    '''
    manages the the process of getting the history of this topic incrementally.
    the process works like this: 
        1. ask all channels for the observation
        2. give every channel a call back once they get a messge
        3. on the call back get the most popular message from all replies
        4. have a timeout here which will force it to move on (using timer)
        5. once it has the most popular reply it either:
            if we don't have this observation yet:
                saves it to disk, and repeats the process with new time
            else: it tells the models data is updated, and cleans up.    
    '''

    def __init__(self, parent: 'Topic'):
        self.parent = parent
        self.refresh()

    def refresh(self):
        self.timeout = None
        self.messages: dict[str, list[PeerMessage]] = {}
        self.messagesToSave = PeerMessages([])
        self.getData()

    def getData(self):
        self.data = self.parent.disk.read()

    @property
    def hashes(self):
        if self.data is not None:
            return self.data.hash.values  # + self.messagesToSave.hashes
        return []

    def prepare(self):
        ''' we verify that our first row (the root) matches the consensus '''
        if self.data is None or self.data.empty:
            return self.request()
        if self.data.shape[0] > 1:
            trunk = self.data.iloc[[1]]
            logging.debug('in prepare', trunk, print='blue')
            self.request(datetime=datetimeFromString(trunk.index[0]))
        else:
            self.request()
        self.startSupervisor()

    def startSupervisor(self):
        ''' incase we lose connection, try again in 60 seconds '''
        from satorineuron.init.start import getStart
        asyncThread = getStart().asyncThread
        if hasattr(self, 'supervisor') and self.supervisor is not None:
            asyncThread.cancelTask(self.supervisor)
        self.supervisor = asyncThread.repeatRun(
            task=self.initiateIfIdle,
            interval=60)

    def initiateIfIdle(self):
        if hasattr(self, 'lastHeard') and self.lastHeard < time.time() - 60:
            logging.debug('inititating from idle', self.lastHeard,
                          time.time() - 60, print='blue')
            self.initiate()

    def initiate(self, message: PeerMessage = None):

        def askForLatestData():
            return self.request(message)

        if self.data is None or self.data.empty:
            return askForLatestData()
        hasRoot = self.parent.disk.hasRoot(self.data)
        if not hasRoot:
            success, row = self.parent.disk.validateAllHashesReturnError(
                self.data)
            if success:
                return askForLatestData()
            return self.request(datetime=datetimeFromString(row.index[0]))
        return askForLatestData()

    # def makeTimeout(self, msgId: str):
    #    ''' handles cancel the existing timeout task before reassigning '''
    #    from satorineuron.init.start import getStart
    #    asyncThread = getStart().asyncThread
    #    if hasattr(self, 'timeout') and self.timeout is not None:
    #        asyncThread.cancelTask(self.timeout)
    #    self.timeout = asyncThread.delayedRun(
    #        task=self.finish,
    #        delay=60,
    #        msgId=msgId)

    def request(self, message: PeerMessage = None, datetime: dt.datetime = None):
        msgId = self.parent.nextBroadcastId()
        # self.makeTimeout(msgId) # timeout pattern unreliable
        self.parent.requestOneObservation(
            datetime=datetime or (
                datetimeFromString(message.observationTime)
                if message is not None else now()),
            msgId=msgId)
        self.messages[msgId]: list[PeerMessage] = []

    def onResponse(self, message: PeerMessage):
        self.lastHeard = time.time()
        msg = self.discoverPopularResponse(message)
        if msg is not None:
            self.handleMostPopular(msg)

    def discoverPopularResponse(self, message: PeerMessage) -> Union[PeerMessage, None]:
        self.messages[message.msgId].append(message)
        messages = self.messages[message.msgId]
        mostPopularResponse = max(
            messages,
            key=lambda message: len([
                r for r in messages if r == message]))
        mostPopularResponseCount = len(
            [r for r in messages if r == mostPopularResponse])
        if (
            mostPopularResponseCount < len(self.parent.channels) / 2 or
            mostPopularResponse.data in [None, 'None', b'None']
        ):
            return None
        return mostPopularResponse

    def handleMostPopular(self, message: PeerMessage):
        '''
        if we don't have this observation yet:
            saves it to disk, and repeats the process with new time
        else: it tells the models data is updated, and cleans up.
        '''
        # if self.parent.streamId.stream == 'coinbaseADA-USD':
        #    logging.debug('handleMostPopular 1:',
        #                  message.hash is None,
        #                  message.hash in self.hashes,
        #                  hasattr(self, 'root'), (
        #                      hasattr(self, 'root') and
        #                      isinstance(self.root, pd.DataFrame) and
        #                      self.data.sort_index().iloc[[0]].equals(self.root)),
        #                  self.parent.disk.validateAllHashes(),
        #                  print='teal')
        if (
            (message.hash is None or
             message.hash in self.hashes) and
            hasattr(self, 'root') and
            isinstance(self.root, pd.DataFrame) and
            self.data.sort_index().iloc[[0]].equals(self.root) and
            self.parent.disk.validateAllHashes(self.data)
        ):
            return self.finishProcess()
        df = message.asDataFrame
        df.columns = ['value', 'hash']
        if self.parent.disk.isARoot(df):
            self.root = df
            if self.parent.disk.matchesRoot(df, localDf=self.data):
                self.finishProcess()
            else:
                self.parent.disk.removeItAndBeforeIt(df.index[0])
        if message.hash not in self.hashes:
            self.parent.disk.append(df)
        self.getData()
        # self.messagesToSave.append(message)
        # self.parent.tellModelsAboutNewHistory()
        # self.request(message)
        self.initiate(message)

    def finishProcess(self):
        logging.debug('FINISHING PROCESS', print='red')
        self.cleanup()

    # def finishProcessTimeoutPattern(self):
    #    logging.debug('df to save is ',
    #                  self.messagesToSave.msgsToDataframe(), print='green')
    #    self.parent.disk.append(self.messagesToSave.msgsToDataframe())
    #    self.parent.tellModelsAboutNewHistory()
    #    self.cleanup()

    # def finish(self, msgId: int):
    #    '''
    #    if we haven't recieved enough responses by now, we just move on.
    #    '''
    #    if (
    #        len(self.messagesToSave) > 0 and
    #        msgId not in [msg.msgId for msg in self.messagesToSave]
    #    ):
    #        logging.debug('FINISHING', msgId, print='red')
    #        self.finishProcess()

    def cleanup(self):
        ''' cleans up the gatherer '''
        # clean up messages
        self.parent.cleanChannels([key for key in self.messages.keys()])
        # clean up dataset
        success, df = self.parent.disk.cleanByHashes()
        logging.debug('strema:', self.parent.streamId, print='red')
        logging.debug('CLEANING BY HASH -- success df',
                      success,
                      df.head() if isinstance(df, pd.DataFrame) else 'None',
                      print='red')
        if success and df is not None:
            logging.debug('writing', print='red')
            self.parent.disk.write(df)
        # self.refresh()
