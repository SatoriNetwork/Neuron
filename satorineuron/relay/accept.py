from satorilib.concepts import StreamId
from satorilib import logging
import pandas as pd


def processRelayCsv(start: 'StartupDag', df: pd.DataFrame):
    # from satorineuron.init.start import getStart
    # start = getStart()
    statuses = []
    for ix, row in df.iterrows():
        if len(start.relay.streams) + ix+1 >= 50:
            return ['relay stream limit reached'], 400
        # data = row.to_dict(na_action='ignore')
        data = {col: None if pd.isna(val) else val for col, val in row.items()}
        if data.get('stream') is None or data.get('stream') == '':
            continue
        data['name'] = data.get('stream', '')
        data['source'] = data.get('source', 'satori')
        data['url'] = data.get('url', '') or ''
        if data.get('hook') is None or data.get('hook') == '':
            msg, status = generateHookFromTarget(data.get('target', ''))
            if status == 200:
                data['hook'] = msg
        # msg, status = _registerDataStreamMock(start, data=data)
        msg, status = registerDataStream(start, data=data, restart=False)
        statuses.append(status)
        # start.workingUpdates.on_next(
        #    f"{data['stream']}{data['target']} - {'success' if status == 200 else msg}")
        start.workingUpdates.put(
            f"{data['stream']}{data['target']} - {'success' if status == 200 else msg}")
    failures = [str(i) for i, s in enumerate(statuses) if s != 200]
    if len(failures) == 0:
        start.checkin()
        start.pubsConnect()
        start.startRelay()
        return 'all succeeded', 200
    elif len(failures) == len(statuses):
        return 'all failed', 500
    start.checkin()
    start.pubsConnect()
    start.startRelay()
    return f'rows {",".join(failures)} failed', 200


def _registerDataStreamMock(start: 'StartupDag', data: dict):
    ''' for testing front end UI of please wait updates '''
    import time
    time.sleep(5)
    return 'Success: ', 200


def acceptRelaySubmission(start: 'StartupDag', data: dict):
    data['url'] = data.get('url', '') or ''
    if not start.relayValidation.validRelay(data):
        return 'Invalid payload. here is an example: {"source": "satori", "name": "nameOfSomeAPI", "target": "optional", "data": 420}', 400
    if not start.relayValidation.streamClaimed(
        name=data.get('name'),
        target=data.get('target')
    ):
        save = start.relayValidation.registerStream(data=data)
        if save == False:
            return 'Unable to register stream with server', 500
        # get pubkey, recreate connection...
        start.checkin()
        start.pubsConnect()
    # ...pass data onto pubsub
    start.publish(
        topic=StreamId(
            source=data.get('source', 'satori'),
            author=start.wallet.publicKey,
            stream=data.get('name'),
            target=data.get('target')).topic(),
        data=data.get('data'),
        toCentral=False)
    # todo: why not to central?
    # todo: why am I not passing these here?
    # observationTime=timestamp,
    # observationHash=observationHash
    return 'Success: ', 200


def registerDataStream(start: 'StartupDag', data: dict, restart: bool = True):
    data['url'] = data.get('url', '') or ''
    if len(start.relay.streams) >= 50:
        return ['relay stream limit reached'], 400
    if data.get('uri') is None:
        data['uri'] = data.get('url')
    if data.get('target') is None:
        data['target'] = ''
    if not start.relayValidation.validUrl(data.get('url')):
        return ['Url is an invalid URL'], 400
    if not start.relayValidation.validUrl(data.get('uri')):
        return ['Url is an invalid URI'], 400
    if not start.relayValidation.validHook(data.get('hook')):
        return ['Invalid hook. Start with "def postRequestHook(r):"'], 400
    msgs = []
    if data.get('history') is not None and not start.relayValidation.validUrl(data.get('history')):
        msgs.append(
            'Warning: unable to validate History field as a valid URL. Saving anyway.')
    # if start.relayValidation.streamClaimed(name=data.get('name'), target=data.get('target')):
    #    badForm = data
    #    flash('You have already created a stream by this name.')
    #    return redirect('/dashboard')
    result = start.relayValidation.testCall(data)
    if result == False:
        msgs.append('Unable to call uri. Check your uri and headers.')
        return msgs, 400
    hookResult = None
    if data.get('hook') is not None and data.get('hook').lstrip().startswith('def postRequestHook('):
        hookResult = start.relayValidation.testHook(data, result)
        if hookResult == None:
            msgs.append('Invalid hook. Unable to execute.')
            return msgs, 400
    hasHistory = data.get('history') is not None and data.get(
        'history').lstrip().startswith('class GetHistory(')
    if hasHistory:
        historyResult = start.relayValidation.testHistory(data)
        if historyResult == False:
            msgs.append('Invalid history. Unable to execute.')
            return msgs, 400
    # if already exists, remove it
    thisStream = StreamId(
        source=data.get('source', 'satori'),
        author=start.wallet.publicKey,
        stream=data.get('name'),
        target=data.get('target'))
    if thisStream in [s.streamId for s in start.relay.streams]:
        try:
            # do not actually delete on the server, we will modify when save
            # removeStreamLogic(
            #     thisStream,
            #     doRedirect=False)
            # delete on client
            start.relayValidation.claimed.remove(thisStream)
        except Exception as e:
            logging.error('relay err', e)

    # attempt to save to server.
    save = start.relayValidation.registerStream(data=data)

    # we no longer use ipfs.
    # subscribe to save ipfs automatically
    # subscribed = start.relayValidation.subscribeToStream(data=data)

    start.relayValidation.saveLocal(data)
    if hasHistory:
        try:
            # this can take a very long time - will flask/browser timeout?
            start.relayValidation.saveHistory(data)
        except Exception as e:
            logging.error('relay err, in history', e)
            msgs.append(
                'Unable to save stream because saving history process '
                f'errored. Fix or remove history text. Error: {e}')
            return msgs, 400
    # get pubkey, recreate connection, restart relay engine
    if restart:
        start.checkin()
        start.pubsConnect()
        start.startRelay()
    if save == False:
        msgs.append('Unable to save stream.')
        return msgs, 500
    # if subscribed == False:
    #    msgs.append('FYI: Unable to subscribe stream.')
    #    return msgs, 500
    msgs.append('Stream saved. Test call result: ' +
                (str(hookResult) if hookResult is not None else str(result.text)))
    return msgs, 200


def generateHookFromTarget(target: str = ''):
    '''creates a function that drills down into a json object accoring a path'''
    def replaceLastOccurrence(input_str, old_substring, new_substring):
        parts = input_str.rsplit(old_substring, 1)
        if len(parts) > 1:
            return parts[0] + new_substring + parts[1]
        else:
            return input_str

    def generateDrill():
        parts = target.split('.')
        return replaceLastOccurrence(''.join([
            '.get("' + part + '", {})' for part in parts]), ', {})', ', None)')

    target = target if target != '' else 'Close'
    return f"""def postRequestHook(response: 'requests.Response'):
    '''
    called and given the response each time
    the endpoint for this data stream is hit.
    returns the value of the observation
    as a string, integer or double.
    if empty string is returned the observation
    is not relayed to the network.
    '''
    if response.text != '':
        return float(response.json(){generateDrill()})
    return None
""", 200
