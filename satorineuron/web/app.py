#!/usr/bin/env python
# -*- coding: utf-8 -*-

# run with:
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &

from typing import Union
import os
import json
import threading
import secrets
import webbrowser
import time
import traceback
import pandas as pd
from waitress import serve
from flask import Flask, url_for, redirect, jsonify, flash, send_from_directory
from flask import session, request, render_template
from flask import Response, stream_with_context
from satorineuron import config
from satorineuron import logging
from satorineuron.relay import acceptRelaySubmission, processRelayCsv, generateHookFromTarget, registerDataStream
from satorineuron.web import forms
from satorilib.concepts.structs import Observation, StreamId, StreamsOverview
from satorilib.api.wallet.wallet import TransactionFailure
from satorilib.api.time import timestampToSeconds
from satorineuron.init.start import StartupDag
from satorineuron.web.utils import deduceCadenceString

###############################################################################
## Globals ####################################################################
###############################################################################

# development flags
debug = True
darkmode = False
badForm = {}
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
updating = False

###############################################################################
## Startup ####################################################################
###############################################################################
MODE = os.environ.get('SATORI_RUN_MODE', 'dev')
while True:
    try:
        start = StartupDag(
            urlServer={
                'dev': 'http://localhost:5002',
                'prod': None,  # 'https://satorinet.io',
                'dockerdev': 'http://192.168.0.10:5002',
            }[MODE],
            urlPubsub={
                'dev': 'ws://localhost:3000',
                'prod': None,  # 'ws://satorinet.io:3000',
                'dockerdev': 'ws://192.168.0.10:3000',
            }[MODE])
        start.start()
        logging.info('Satori Neuron started!', color='green')
        break
    except ConnectionError as e:
        # try again...
        traceback.print_exc()
        logging.error(f'ConnectionError in app startup: {e}', color='red')
        time.sleep(30)
    # except RemoteDisconnected as e:
    except Exception as e:
        # try again...
        traceback.print_exc()
        logging.error(f'Exception in app startup: {e}', color='red')
        time.sleep(30)

###############################################################################
## Functions ##################################################################
###############################################################################


def returnNone():
    r = Response()
    # r.set_cookie("My important cookie", value=some_cool_value)
    return r, 204


def get_user_id():
    return session.get('user_id', '0')


def getFile(ext: str = '.csv') -> tuple[str, int, Union[None, 'FileStorage']]:
    if 'file' not in request.files:
        return 'No file uploaded', 400, None
    f = request.files['file']
    if f.filename == '':
        return 'No selected file', 400, None
    if f:
        if ext is None:
            return 'success', 200, f
        elif isinstance(ext, str) and f.filename.endswith(ext):
            return 'success', 200, f
        else:
            return 'Invalid file format. Only CSV files are allowed', 400, None
    return 'unknown error getting file', 500, None
###############################################################################
## Errors #####################################################################
###############################################################################


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

###############################################################################
## Routes - static ############################################################
###############################################################################


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static/img/favicon'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon')


@app.route('/static/<path:path>')
def sendStatic(path):
    return send_from_directory('static', path)


@app.route('/generated/<path:path>')
def generated(path):
    return send_from_directory('generated', path)


@app.route('/upload_history_csv', methods=['POST'])
def uploadHistoryCsv():
    msg, status, f = getFile('.csv')
    if f is not None:
        f.save('/Satori/Neuron/uploaded/history.csv')
        return 'Successful upload.', 200
    else:
        flash(msg, 'success' if status == 200 else 'error')
    return redirect(url_for('dashboard'))


@app.route('/upload_datastream_csv', methods=['POST'])
def uploadDatastreamCsv():
    msg, status, f = getFile('.csv')
    if f is not None:
        df = pd.read_csv(f)
        processRelayCsv(start, df)
        logging.info('Successful upload', 200, print=True)
    else:
        logging.error(msg, status, print=True)
        flash(msg, 'success' if status == 200 else 'error')
    return redirect(url_for('dashboard'))


@app.route('/test')
def test():
    logging.info(request.MOBILE)
    return render_template('test.html')


@app.route('/kwargs')
def kwargs():
    ''' ...com/kwargs?0-name=widget_name0&0-value=widget_value0&0-type=widget_type0&1-name=widget_name1&1-value=widget_value1&1-#type=widget_type1 '''
    kwargs = {}
    for i in range(25):
        if request.args.get(f'{i}-name') and request.args.get(f'{i}-value'):
            kwargs[request.args.get(f'{i}-name')
                   ] = request.args.get(f'{i}-value')
            kwargs[request.args.get(f'{i}-name') +
                   '-type'] = request.args.get(f'{i}-type')
    return jsonify(kwargs)


@app.route('/ping', methods=['GET'])
def ping():
    from datetime import datetime
    return jsonify({'now': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


@app.route('/pause/<timeout>', methods=['GET'])
def pause(timeout):
    try:
        timeout = int(timeout)
        if timeout < 12:
            start.pause(timeout*60*60)
    except Exception as _:
        flash('invalid pause timeout', 'error')
    return redirect(url_for('dashboard'))


@app.route('/unpause', methods=['GET'])
def unpause():
    start.unpause()
    return redirect(url_for('dashboard'))


@app.route('/mode/light', methods=['GET'])
def modeLight():
    global darkmode
    darkmode = False
    return redirect(url_for('dashboard'))


@app.route('/mode/dark', methods=['GET'])
def modeDark():
    global darkmode
    darkmode = True
    return redirect(url_for('dashboard'))

###############################################################################
## Routes - forms #############################################################
###############################################################################


@app.route('/configuration', methods=['GET', 'POST'])
def editConfiguration():
    import importlib
    global forms
    forms = importlib.reload(forms)

    def present_form(edit_configuration):
        edit_configuration.flaskPort.data = config.flaskPort()
        edit_configuration.nodejsPort.data = config.nodejsPort()
        edit_configuration.dataPath.data = config.dataPath()
        edit_configuration.modelPath.data = config.modelPath()
        edit_configuration.walletPath.data = config.walletPath()
        edit_configuration.defaultSource.data = config.defaultSource()
        edit_configuration.electrumxServers.data = config.electrumxServers()
        resp = {
            'darkmode': darkmode,
            'title': 'Configuration',
            'edit_configuration': edit_configuration}
        return render_template('forms/config.html', **resp)

    def accept_submittion(edit_configuration):
        data = {}
        if edit_configuration.flaskPort.data not in ['', None, config.flaskPort()]:
            data = {
                **data, **{config.verbose('flaskPort'): edit_configuration.flaskPort.data}}
        if edit_configuration.nodejsPort.data not in ['', None, config.nodejsPort()]:
            data = {
                **data, **{config.verbose('nodejsPort'): edit_configuration.nodejsPort.data}}
        if edit_configuration.dataPath.data not in ['', None, config.dataPath()]:
            data = {
                **data, **{config.verbose('dataPath'): edit_configuration.dataPath.data}}
        if edit_configuration.modelPath.data not in ['', None, config.modelPath()]:
            data = {
                **data, **{config.verbose('modelPath'): edit_configuration.modelPath.data}}
        if edit_configuration.walletPath.data not in ['', None, config.walletPath()]:
            data = {
                **data, **{config.verbose('walletPath'): edit_configuration.walletPath.data}}
        if edit_configuration.defaultSource.data not in ['', None, config.defaultSource()]:
            data = {
                **data, **{config.verbose('defaultSource'): edit_configuration.defaultSource.data}}
        if edit_configuration.electrumxServers.data not in ['', None, config.electrumxServers()]:
            data = {**data, **{config.verbose('electrumxServers'): [
                edit_configuration.electrumxServers.data]}}
        config.modify(data=data)
        return redirect('/dashboard')

    edit_configuration = forms.EditConfigurationForm(formdata=request.form)
    if request.method == 'POST':
        return accept_submittion(edit_configuration)
    return present_form(edit_configuration)


@app.route('/hook/<target>', methods=['GET'])
def hook(target: str = 'Close'):
    ''' generates a hook for the given target '''
    return generateHookFromTarget(target)


@app.route('/hook/', methods=['GET'])
def hookEmptyTarget():
    ''' generates a hook for the given target '''
    # in the case target is empty string
    return generateHookFromTarget('Close')


@app.route('/relay', methods=['POST'])
def relay():
    '''
    format for json post (as python dict):{
        "source": "satori",
        "name": "nameOfSomeAPI",
        "target": "optional",
        "data": 420,
    }
    '''

    # def accept_submittion(data: dict):
    #    if not start.relayValidation.valid_relay(data):
    #        return 'Invalid payload. here is an example: {"source": "satori", "name": "nameOfSomeAPI", "target": "optional", "data": 420}', 400
    #    if not start.relayValidation.stream_claimed(
    #        name=data.get('name'),
    #        target=data.get('target')
    #    ):
    #        save = start.relayValidation.register_stream(
    #            data=data)
    #        if save == False:
    #            return 'Unable to register stream with server', 500
    #        # get pubkey, recreate connection...
    #        start.checkin()
    #        start.pubsubConnect()
    #    # ...pass data onto pubsub
    #    start.pubsub.publish(
    #        topic=StreamId(
    #            source=data.get('source', 'satori'),
    #            author=start.wallet.publicKey,
    #            stream=data.get('name'),
    #            target=data.get('target')).topic(),
    #        data=data.get('data'))
    #    return 'Success: ', 200
    return acceptRelaySubmission(start, json.loads(request.get_json()))


@app.route('/send_satori_transaction', methods=['POST'])
def sendSatoriTransaction():
    import importlib
    global forms
    global badForm
    forms = importlib.reload(forms)

    def accept_submittion(sendSatoriForm):
        if sendSatoriForm.sweep.data == True:
            try:
                result = start.wallet.sendAllTransaction(
                    sendSatoriForm.address.data or '')
                if result is None:
                    flash('Send Failed: try again in a few minutes.')
                else:
                    flash(str(result))
            except TransactionFailure as e:
                flash(f'Send Failed: {e}')
        else:
            try:
                result = start.wallet.satoriTransaction(
                    amount=sendSatoriForm.amount.data or 0,
                    address=sendSatoriForm.address.data or '')
                if result is None:
                    flash('Send Failed: try again in a few minutes.')
                else:
                    flash(str(result))
            except TransactionFailure as e:
                flash(f'Send Failed: {e}')
        return redirect('/wallet')

    sendSatoriForm = forms.SendSatoriTransaction(formdata=request.form)
    return accept_submittion(sendSatoriForm)


@app.route('/register_stream', methods=['POST'])
def registerStream():
    import importlib
    global forms
    global badForm
    forms = importlib.reload(forms)

    def accept_submittion(newRelayStream):
        # done: we should register this stream and
        # todo: save the uri, headers, payload, and hook to a config manifest file.
        global badForm
        data = {
            # **({'source': newRelayStream.source.data} if newRelayStream.source.data not in ['', None] else {}), # in the future we will allow users to specify a source like streamr or satori
            **({'topic': newRelayStream.topic.data} if newRelayStream.topic.data not in ['', None] else {}),
            **({'name': newRelayStream.name.data} if newRelayStream.name.data not in ['', None] else {}),
            **({'target': newRelayStream.target.data} if newRelayStream.target.data not in ['', None] else {}),
            **({'cadence': newRelayStream.cadence.data} if newRelayStream.cadence.data not in ['', None] else {}),
            **({'offset': newRelayStream.offset.data} if newRelayStream.offset.data not in ['', None] else {}),
            **({'datatype': newRelayStream.datatype.data} if newRelayStream.datatype.data not in ['', None] else {}),
            **({'description': newRelayStream.description.data} if newRelayStream.description.data not in ['', None] else {}),
            **({'tags': newRelayStream.tags.data} if newRelayStream.tags.data not in ['', None] else {}),
            **({'url': newRelayStream.url.data} if newRelayStream.url.data not in ['', None] else {}),
            **({'uri': newRelayStream.uri.data} if newRelayStream.uri.data not in ['', None] else {}),
            **({'headers': newRelayStream.headers.data} if newRelayStream.headers.data not in ['', None] else {}),
            **({'payload': newRelayStream.payload.data} if newRelayStream.payload.data not in ['', None] else {}),
            **({'hook': newRelayStream.hook.data} if newRelayStream.hook.data not in ['', None] else {}),
            **({'history': newRelayStream.history.data} if newRelayStream.history.data not in ['', None] else {}),
        }
        if data.get('hook') in ['', None, {}]:
            hook, status = generateHookFromTarget(data.get('target', ''))
            if status == 200:
                data['hook'] = hook
        msgs, status = registerDataStream(start, data)
        if status == 400:
            badForm = data
        for msg in msgs:
            flash(msg)
        return redirect('/dashboard')

    newRelayStream = forms.RelayStreamForm(formdata=request.form)
    return accept_submittion(newRelayStream)


@app.route('/edit_stream/<topic>', methods=['GET'])
def editStream(topic=None):
    # name,target,cadence,offset,datatype,description,tags,url,uri,headers,payload,hook
    import importlib
    global forms
    global badForm
    forms = importlib.reload(forms)
    try:
        badForm = [
            s for s in start.relay.streams
            if s.streamId.topic() == topic][0].asMap(noneToBlank=True)
    except IndexError:
        # on rare occasions
        # IndexError: list index out of range
        # cannot reproduce, maybe it's in the middle of reconnecting?
        pass
    return redirect('/dashboard')


# @app.route('/remove_stream/<source>/<stream>/<target>/', methods=['GET'])
# def removeStream(source=None, stream=None, target=None):
@app.route('/remove_stream/<topic>', methods=['GET'])
def removeStream(topic=None):
    # removeRelayStream = {
    #    'source': source or 'satori',
    #    'name': stream,
    #    'target': target}
    removeRelayStream = StreamId.fromTopic(topic)
    return removeStreamLogic(removeRelayStream)


def removeStreamLogic(removeRelayStream: StreamId, doRedirect=True):
    def accept_submittion(removeRelayStream: StreamId, doRedirect=True):
        r = start.server.removeStream(payload=json.dumps({
            'source': removeRelayStream.source,
            'pubkey': start.wallet.publicKey,  # should match removeRelayStream.author
            'stream': removeRelayStream.stream,
            'target': removeRelayStream.target,
        }))
        if (r.status_code == 200):
            msg = 'Stream deleted.'
            # get pubkey, recreate connection, restart relay engine
            try:
                start.relayValidation.claimed.remove(removeRelayStream)
            except Exception as e:
                logging.error(e)
            start.checkin()
            start.pubsubConnect()
            start.startRelay()
        else:
            msg = 'Unable to delete stream.'
        if doRedirect:
            flash(msg)
            return redirect('/dashboard')

    return accept_submittion(removeRelayStream, doRedirect)


@app.route('/remove_stream_by_post', methods=['POST'])
def removeStreamByPost():

    def accept_submittion(removeRelayStream):
        r = start.server.removeStream(payload=json.dumps({
            'source': removeRelayStream.get('source', 'satori'),
            'pubkey': start.wallet.publicKey,
            'stream': removeRelayStream.get('name'),
            'target': removeRelayStream.get('target'),
        }))
        if (r.status_code == 200):
            msg = 'Stream deleted.'
            # get pubkey, recreate connection, restart relay engine
            try:
                start.relayValidation.claimed.remove(removeRelayStream)
            except Exception as e:
                logging.error(e)
            start.checkin()
            start.pubsubConnect()
            start.startRelay()
        else:
            msg = 'Unable to delete stream.'
        flash(msg)
        return redirect('/dashboard')

    removeRelayStream = json.loads(request.get_json())
    return accept_submittion(removeRelayStream)
###############################################################################
## Routes - dashboard #########################################################
###############################################################################


@app.route('/', methods=['GET'])
@app.route('/home', methods=['GET'])
@app.route('/dashboard', methods=['GET'])
def dashboard():
    '''
    UI
    - send to setup process if first time running the app...
    - show earnings
    - access to wallet
    - access metrics for published streams
        (which streams do I have?)
        (how often am I publishing to my streams?)
    - access to data management (monitor storage resources)
    - access to model metrics
        (show accuracy over time)
        (model inputs and relative strengths)
        (access to all predictions and the truth)
    '''
    if start.engine is None:
        streamsOverview = [{'source': 'Streamr', 'stream': 'DATAUSD/binance/ticker', 'target': 'Close', 'subscribers': '3',
                            'accuracy': '97.062 %', 'prediction': '3621.00', 'value': '3548.00', 'predictions': [2, 3, 1]}]
    else:
        streamsOverview = [model.overview() for model in start.engine.models]

    import importlib
    global forms
    global badForm
    forms = importlib.reload(forms)

    def present_stream_form():
        '''
        this function could be used to fill a form with the current
        configuration for a stream in order to edit it.
        '''
        if isinstance(badForm.get('streamId'), StreamId):
            name = badForm.get('streamId').stream
            target = badForm.get('streamId').target
        elif isinstance(badForm.get('streamId'), dict):
            name = badForm.get('streamId', {}).get('stream', '')
            target = badForm.get('streamId', {}).get('target', '')
        else:
            name = ''
            target = ''
        newRelayStream = forms.RelayStreamForm(formdata=request.form)
        newRelayStream.topic.data = badForm.get(
            'topic', badForm.get('kwargs', {}).get('topic', ''))
        newRelayStream.name.data = badForm.get('name', None) or name
        newRelayStream.target.data = badForm.get('target', None) or target
        newRelayStream.cadence.data = badForm.get('cadence', None)
        newRelayStream.offset.data = badForm.get('offset', None)
        newRelayStream.datatype.data = badForm.get('datatype', '')
        newRelayStream.description.data = badForm.get('description', '')
        newRelayStream.tags.data = badForm.get('tags', '')
        newRelayStream.url.data = badForm.get('url', '')
        newRelayStream.uri.data = badForm.get('uri', '')
        newRelayStream.headers.data = badForm.get('headers', '')
        newRelayStream.payload.data = badForm.get('payload', '')
        newRelayStream.hook.data = badForm.get('hook', '')
        newRelayStream.history.data = badForm.get('history', '')
        return newRelayStream
    # exampleStream = [Stream(streamId=StreamId(source='satori', author='self', stream='streamName', target='target'), cadence=3600, offset=0, datatype=None, description='example datastream', tags='example, raw', url='https://www.satorineuron.com', uri='https://www.satorineuron.com', headers=None, payload=None, hook=None, ).asMap(noneToBlank=True)]
    resp = {
        'darkmode': darkmode,
        'title': 'Satori',
        'wallet': start.wallet,
        'streamsOverview': streamsOverview,
        'configOverrides': config.get(),
        'paused': start.paused,
        'newRelayStream': present_stream_form(),
        'shortenFunction': lambda x: x[0:15] + '...' if len(x) > 18 else x,
        'relayStreams':  # example stream +
        ([
            {
                **stream.asMap(noneToBlank=True),
                **{'latest': start.relay.latest.get(stream.streamId.topic(), '')},
                **{'late': start.relay.late(stream.streamId, timestampToSeconds(start.cacheOf(stream.streamId).getLatestObservationTime()))},
                **{'cadenceStr': deduceCadenceString(stream.cadence)},
                **{'offsetStr': deduceCadenceString(stream.offset)}}
            for stream in start.relay.streams]
         if start.relay is not None else []),

        'placeholderPostRequestHook': """def postRequestHook(response: 'requests.Response'): 
    '''
    called and given the response each time
    the endpoint for this data stream is hit.
    returns the value of the observaiton 
    as a string, integer or double.
    if empty string is returned the observation
    is not relayed to the network.
    '''                    
    if response.text != '':
        return float(response.json().get('Close', -1.0))
    return -1.0
""",
        'placeholderGetHistory': """class GetHistory(object):
    '''
    supplies the history of the data stream
    one observation at a time (getNext, isDone)
    or all at once (getAll)
    '''
    def __init__(self):
        super(GetHistory, self).__init__()

    def getNext(self):
        '''
        should return a value or a list of two values,
        the first being the time in UTC as a string of the observation,
        the second being the observation value
        '''
        return None

    def isDone(self):
        ''' returns true when there are no more observations to supply '''
        return None

    def getAll(self):
        ''' 
        if getAll returns a list or pandas DataFrame
        then getNext is never called
        '''
        return None

""",
    }
    return render_template('dashboard.html', **resp)


@app.route('/model-updates')
def modelUpdates():
    def update():
        global updating
        if updating:
            yield 'data: []\n\n'
        updating = True
        streamsOverview = StreamsOverview(start.engine)
        listeners = []
        # listeners.append(start.engine.data.newData.subscribe(
        #    lambda x: streamsOverview.setIt() if x is not None else None))
        if start.engine is not None:
            for model in start.engine.models:
                listeners.append(model.predictionUpdate.subscribe(
                    lambda x: streamsOverview.setIt() if x is not None else None))
            while True:
                if streamsOverview.viewed:
                    time.sleep(60)
                else:
                    # parse it out here?
                    yield "data: " + str(streamsOverview.overview).replace("'", '"') + "\n\n"
                    streamsOverview.setViewed()
        else:
            yield "data: " + str(streamsOverview.demo).replace("'", '"') + "\n\n"

    import time
    return Response(update(), mimetype='text/event-stream')


@app.route('/working_updates')
def workingUpdates():
    def update():
        try:
            yield 'data: \n\n'
            messages = []
            listeners = []
            listeners.append(start.workingUpdates.subscribe(
                lambda x: messages.append(x) if x is not None else None))
            while True:
                time.sleep(1)
                if len(messages) > 0:
                    msg = messages.pop(0)
                    if msg == 'working_updates_end':
                        break
                    yield "data: " + str(msg).replace("'", '"') + "\n\n"
        except Exception as e:
            logging.error('working_updates error:', e, print=True)

    import time
    return Response(update(), mimetype='text/event-stream')


@app.route('/working_updates_end')
def workingUpdatesEnd():
    start.workingUpdates.on_next('working_updates_end')
    return 'ok', 200


@app.route('/wallet')
def wallet():
    # not handling buffering correctly, so getting a list of transactions gets cut off and kills the page.
    start.wallet.get(allWalletInfo=False)
    import io
    import qrcode
    from base64 import b64encode
    img = qrcode.make(start.wallet.address)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    # return send_file(buf, mimetype='image/jpeg')
    img = b64encode(buf.getvalue()).decode('ascii')
    img_tag = f'<img src="data:image/jpg;base64,{img}" class="img-fluid"/>'

    import importlib
    global forms
    forms = importlib.reload(forms)

    def present_tx_form():
        '''
        this function could be used to fill a form with the current
        configuration for a stream in order to edit it.
        '''
        sendSatoriTransaction = forms.SendSatoriTransaction(
            formdata=request.form)
        sendSatoriTransaction.address.data = ''
        sendSatoriTransaction.amount.data = ''
        return sendSatoriTransaction

    resp = {
        'darkmode': darkmode,
        'title': 'Wallet',
        'image': img_tag,
        'wallet': start.wallet,
        'sendSatoriTransaction': present_tx_form()}
    return render_template('wallet.html', **resp)


@app.route('/vault')
def vault():
    resp = {'darkmode': darkmode, 'title': 'Vault'}
    return render_template('vault.html', **resp)


@app.route('/voting')
def voting():
    resp = {'darkmode': darkmode, 'title': 'Voting'}
    return render_template('voting.html', **resp)


@app.route('/relay_csv', methods=['GET'])
def relayCsv():
    ''' returns a csv file of the current relay streams '''
    import pandas as pd
    return (
        pd.DataFrame([{
            **{'source': stream.streamId.source},
            **{'author': stream.streamId.author},
            **{'stream': stream.streamId.stream},
            **{'target': stream.streamId.target},
            **stream.asMap(noneToBlank=True),
            **{'latest': start.relay.latest.get(stream.streamId.topic(), '')},
            **{'cadenceStr': deduceCadenceString(stream.cadence)},
            **{'offsetStr': deduceCadenceString(stream.offset)}}
            for stream in start.relay.streams]
            if start.relay is not None else []).to_csv(index=False),
        200,
        {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename=relay_streams.csv'
        }
    )


@app.route('/relay_history_csv/<topic>', methods=['GET'])
def relayHistoryCsv(topic: str = None):
    ''' returns a csv file of the history of the relay stream '''
    cache = start.cacheOf(StreamId.fromTopic(topic))

    return (
        (
            cache.df.drop(columns=['hash'])
            if cache is not None and cache.df is not None and 'hash' in cache.df.columns
            else pd.DataFrame({'failure': [
                f'no history found for stream with stream id of {topic}']}
            )
        ).to_csv(),
        200,
        {
            'Content-Type': 'text/csv',
            'Content-Disposition': f'attachment; filename={cache.id.stream}.{cache.id.target}.csv'
        })


@app.route('/merge_history_csv/<topic>', methods=['POST'])
def mergeHistoryCsv(topic: str = None):
    ''' merge history uploaded  '''
    cache = start.cacheOf(StreamId.fromTopic(topic))
    if cache is not None:
        msg, status, f = getFile('.csv')
        if f is not None:
            df = pd.read_csv(f)
            print('df', df)
            cache.merge(df)
            success, _ = cache.validateAllHashes()
            if success:
                flash('history merged successfully!', 'success')
            else:
                cache.saveHashes()
                success, _ = cache.validateAllHashes()
                if success:
                    flash('history merged successfully!', 'success')
        else:
            flash(msg, 'success' if status == 200 else 'error')
    else:
        flash('history data not found', 'error')
    return redirect(url_for('dashboard'))


@app.route('/remove_history_csv/<topic>', methods=['GET'])
def removeHistoryCsv(topic: str = None):
    ''' removes history '''
    cache = start.cacheOf(StreamId.fromTopic(topic))
    if cache is not None and cache.df is not None:
        cache.remove()
        flash('history cleared successfully', 'success')
    else:
        flash('history not found', 'error')
    return redirect(url_for('dashboard'))


@app.route('/trigger_relay/<topic>', methods=['GET'])
def triggerRelay(topic: str = None):
    ''' triggers relay stream to happen '''
    if start.relay.triggerManually(StreamId.fromTopic(topic)):
        flash('relayed successfully', 'success')
    else:
        flash('failed to relay', 'error')
    return redirect(url_for('dashboard'))

###############################################################################
## Routes - subscription ######################################################
###############################################################################

# unused - we're not using any other networks yet, but when we do we can pass
# their values to this and have it diseminate
# @app.route('/subscription/update/', methods=['POST'])
# def update():
#    """
#    returns nothing
#    ---
#    post:
#      operationId: score
#      requestBody:
#        content:
#          application/json:
#            {
#            "source-id": id,
#            "stream-id": id,
#            "observation-id": id,
#            "content": {
#                key: value
#            }}
#      responses:
#        '200':
#          json
#    """
#    ''' from streamr - datastream has a new observation
#    upon a new observation of a datastream, the nodejs app will send this
#    python flask app a message on this route. The flask app will then pass the
#    message to the data manager, specifically the scholar (and subscriber)
#    threads by adding it to the appropriate subject. (the scholar, will add it
#    to the correct table in the database history, notifying the subscriber who
#    will, if used by any current best models, notify that model's predictor
#    thread via a subject that a new observation is available by providing the
#    observation directly in the subject).
#
#    This app needs to create the DataManager, ModelManagers, and Learner in
#    in order to have access to those objects. Specifically the DataManager,
#    we need to be able to access it's BehaviorSubjects at data.newData
#    so we can call .on_next() here to pass along the update got here from the
#    Streamr LightClient, and trigger a new prediction.
#    '''
#    x = Observation.parse(request.json)
#    start.engine.data.newData.on_next(x)
#
#    return request.json

###############################################################################
## Routes - history ###########################################################
# we may be able to make these requests
###############################################################################


@app.route('/history/request')
def publsih():
    ''' to streamr - create a new datastream to publish to '''
    # todo: spoof a dataset response - random generated data, so that the
    #       scholar can be built to ask for history and download it.
    resp = {}
    return render_template('unknown.html', **resp)


@app.route('/history')
def publsihMeta():
    ''' to streamr - publish to a stream '''
    resp = {}
    return render_template('unknown.html', **resp)

###############################################################################
## UDP communication ##########################################################
###############################################################################


@app.route('/udp/ports', methods=['GET'])
def udpPorts():
    ''' recieves data from udp relay '''
    return str(start.peer.gatherChannels())


@app.route('/udp/stream')
def udpStream():

    def event_stream():
        '''
        here we gather all the messages from the rendezvous object
        it will be a list of tuples (address, message)
        then we have to organize it into a dictionary for the udp relay
        then make it a string. will be interpretted this way:
        literal: dict[str, object] = ast.literal_eval(message)
        data = literal.get('data', None)
        localPort = literal.get('localPort', None)
        '''
        while True:
            time.sleep(1)
            messages = start.peer.gatherMessages()
            if len(messages) > 0:
                yield 'data:' + str(messages) + '\n\n'
            yield '\n'

    return Response(
        stream_with_context(event_stream()),
        content_type='text/event-stream')


@app.route('/udp/reconnect', methods=['GET'])
def udpReconnect():
    start.rendezvousConnect()
    return 'ok', 200


@app.route('/udp/message', methods=['POST'])
def udpMessage():
    ''' recieves data from udp relay '''
    # payload = request.json
    # print('udpMessage', payload)
    # data = payload.get('data', None)
    # localPort = payload.get('address', {}).get('local', {}).get('port', None)
    # remoteIp = payload.get('address', {}).get('remote', {}).get('ip', None)
    # remotePort = payload.get('address', {}).get('remote', {}).get('port', None)
    data = request.data
    remoteIp = request.headers.get('remoteIp')
    remotePort = int(request.headers.get('remotePort'))
    localPort = int(request.headers.get('localPort'))
    # print('udpMessage', data, 'from', remoteIp, remotePort, 'to', localPort)
    if any(v is None for v in [localPort, remoteIp, remotePort, data]):
        return 'fail'
    start.peer.passMessage(localPort, remoteIp, remotePort, message=data)
    return 'ok'


###############################################################################
## Entry ######################################################################
###############################################################################


if __name__ == '__main__':
    # if False:
    #    spoofStreamer()

    # serve(app, host='0.0.0.0', port=config.get()['port'])
    if not debug:
        webbrowser.open('http://127.0.0.1:24601', new=0, autoraise=True)
    app.run(
        host='0.0.0.0',
        port=config.flaskPort(),
        threaded=True,
        debug=debug,
        use_reloader=False)   # fixes run twice issue
    # app.run(host='0.0.0.0', port=config.get()['port'], threaded=True)
    # https://stackoverflow.com/questions/11150343/slow-requests-on-local-flask-server
    # did not help

# http://localhost:24601/
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &
# > python satori\web\app.py
