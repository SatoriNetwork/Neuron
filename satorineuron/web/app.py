#!/usr/bin/env python
# -*- coding: utf-8 -*-

# run with:
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &

import os
import json
import threading
import secrets
import webbrowser
import time
from waitress import serve
from flask import Flask, url_for, redirect, jsonify, flash, send_from_directory
from flask import session, request, render_template
from flask import Response, stream_with_context
from satorineuron import config
from satorineuron import logging
from satorineuron.web import forms
from satorilib.concepts.structs import Observation, StreamId, StreamsOverview
from satorineuron.init.start import StartupDag
from satorineuron.web.utils import deduceCadenceString

###############################################################################
## Helpers ####################################################################
###############################################################################


def spoofStreamer():
    from satorineuron import spoof
    thread = threading.Thread(target=spoof.Streamr(
        sourceId='streamrSpoof',
        streamId='simpleEURCleanedHL',
    ).run, daemon=True)
    thread.start()
    thread = threading.Thread(target=spoof.Streamr(
        sourceId='streamrSpoof',
        streamId='simpleEURCleanedC',
    ).run, daemon=True)
    thread.start()

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
        break
    except ConnectionError as e:
        # try again...
        time.sleep(30)
    # except RemoteDisconnected as e:
    except Exception as e:
        # try again...
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

###############################################################################
## Errors #####################################################################
###############################################################################


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

###############################################################################
## Routes - static ############################################################
###############################################################################


@app.route('/favicon.ico/')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static/img/favicon'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon')


@app.route('/static/<path:path>/')
def send_static(path):
    return send_from_directory('static', path)


@app.route('/generated/<path:path>/')
def send_generated(path):
    return send_from_directory('generated', path)


@app.route('/upload/', methods=['POST'])
def upload_csv():
    if 'file' not in request.files:
        return 'No file uploaded', 400
    f = request.files['file']
    if f.filename == '':
        return 'No selected file', 400
    if f and f.filename.endswith('.csv'):
        f.save('/Satori/Neuron/uploaded/history.csv')
        # redirect('/dashboard')  # url_for('dashboard')
        return 'Successful upload.', 200
    else:
        return 'Invalid file format. Only CSV files are allowed', 400


@app.route('/test/')
def test():
    logging.info(request.MOBILE)
    return render_template('test.html')


@app.route('/kwargs/')
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


@app.route('/ping/', methods=['GET'])
def ping():
    from datetime import datetime
    return jsonify({'now': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


@app.route('/pause/<timeout>/', methods=['GET'])
def pause(timeout):
    try:
        timeout = int(timeout)
        if timeout < 12:
            start.pause(timeout*60*60)
    except Exception as _:
        flash('invalid pause timeout', 'error')
    return redirect(url_for('dashboard'))


@app.route('/unpause/', methods=['GET'])
def unpause():
    start.unpause()
    return redirect(url_for('dashboard'))


@app.route('/mode/light/', methods=['GET'])
def modeLight():
    global darkmode
    darkmode = False
    return redirect(url_for('dashboard'))


@app.route('/mode/dark/', methods=['GET'])
def modeDark():
    global darkmode
    darkmode = True
    return redirect(url_for('dashboard'))

###############################################################################
## Routes - forms #############################################################
###############################################################################


@app.route('/configuration/', methods=['GET', 'POST'])
def edit_configuration():
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


@app.route('/hook/<target>/', methods=['GET'])
def hook(target: str = 'Close'):
    ''' generates a hook for the given target '''
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
    returns the value of the observaiton 
    as a string, integer or double.
    if empty string is returned the observation
    is not relayed to the network.
    '''                    
    if response.text != '':
        return float(response.json(){generateDrill()})
    return None
""", 200


@app.route('/relay/', methods=['POST'])
def relay():
    '''
    format for json post (as python dict):{
        "source": "satori",
        "name": "nameOfSomeAPI",
        "target": "optional",
        "data": 420,
    }
    '''

    def accept_submittion(data: dict):
        if not start.relayValidation.valid_relay(data):
            return 'Invalid payload. here is an example: {"source": "satori", "name": "nameOfSomeAPI", "target": "optional", "data": 420}', 400
        if not start.relayValidation.stream_claimed(
            name=data.get('name'),
            target=data.get('target')
        ):
            save = start.relayValidation.register_stream(
                data=data)
            if save == False:
                return 'Unable to register stream with server', 500
            # get pubkey, recreate connection...
            start.checkin()
            start.pubsubConnect()
        # ...pass data onto pubsub
        start.pubsub.publish(
            topic=StreamId(
                source=data.get('source', 'satori'),
                author=start.wallet.publicKey,
                stream=data.get('name'),
                target=data.get('target')).topic(),
            data=data.get('data'))
        return 'Success: ', 200

    payload = json.loads(request.get_json())
    return accept_submittion(payload)


@app.route('/register_stream/', methods=['POST'])
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
        if data.get('uri') is None:
            data['uri'] = data.get('url')
        if data.get('target') is None:
            data['target'] = ''
        if start.relayValidation.invalid_url(data.get('url')):
            badForm = data
            flash('Url is an invalid URL')
            return redirect('/dashboard')
        if start.relayValidation.invalid_url(data.get('uri')):
            badForm = data
            flash('Uri is an invalid URI')
            return redirect('/dashboard')
        if start.relayValidation.invalid_hook(data.get('hook')):
            badForm = data
            flash('Invalid hook. Start with "def postRequestHook(r):"')
            return redirect('/dashboard')
        if data.get('history') is not None and start.relayValidation.invalid_url(data.get('history')):
            flash(
                'Warning: unable to validate History field as a valid URL. Saving anyway.')
        # if start.relayValidation.stream_claimed(name=data.get('name'), target=data.get('target')):
        #    badForm = data
        #    flash('You have already created a stream by this name.')
        #    return redirect('/dashboard')
        result = start.relayValidation.test_call(data)
        if result == False:
            badForm = data
            flash('Unable to call uri. Check your uri and headers.')
            return redirect('/dashboard')
        hookResult = None
        if data.get('hook') is not None and data.get('hook').lstrip().startswith('def postRequestHook('):
            hookResult = start.relayValidation.test_hook(data, result)
            if hookResult == None:
                badForm = data
                flash('Invalid hook. Unable to execute.')
                return redirect('/dashboard')
        hasHistory = data.get('history') is not None and data.get(
            'history').lstrip().startswith('class GetHistory(')
        if hasHistory:
            historyResult = start.relayValidation.test_history(data)
            if historyResult == False:
                badForm = data
                flash('Invalid history. Unable to execute.')
                return redirect('/dashboard')
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
                logging.error(e)

        # attempt to save to server.
        save = start.relayValidation.register_stream(data=data)
        # subscribe to save ipfs automatically
        subscribed = start.relayValidation.subscribe_to_stream(data=data)
        start.relayValidation.save_local(data)
        if hasHistory:
            try:
                # this can take a very long time - will flask/browser timeout?
                start.relayValidation.save_history(data)
            except Exception as e:
                logging.error(e)
                badForm = data
                flash(
                    'Unable to save stream because saving history process '
                    f'errored. Fix or remove history text. Error: {e}')
                return redirect('/dashboard')
        # get pubkey, recreate connection, restart relay engine
        start.checkin()
        start.pubsubConnect()
        start.startRelay()
        if save == False:
            badForm = data
            flash('Unable to save stream.')
            return redirect('/dashboard')
        if subscribed == False:
            flash('FYI: Unable to subscribe stream.')
        badForm = {}
        flash('Stream saved. Test call result: ' +
              (str(hookResult) if hookResult is not None else str(result.text)))
        return redirect('/dashboard')

    newRelayStream = forms.RelayStreamForm(formdata=request.form)
    return accept_submittion(newRelayStream)


@app.route('/edit_stream/<topic>/', methods=['GET'])
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
@app.route('/remove_stream/<topic>/', methods=['GET'])
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


@app.route('/remove_stream_by_post/', methods=['POST'])
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
@app.route('/home/', methods=['GET'])
@app.route('/dashboard/', methods=['GET'])
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
    # logging.debug('streamsOverview')
    # logging.debug(streamsOverview)

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


@app.route('/model-updates/')
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


@app.route('/wallet/')
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
    resp = {
        'darkmode': darkmode,
        'title': 'Wallet',
        'image': img_tag,
        'wallet': start.wallet}
    return render_template('wallet.html', **resp)

###############################################################################
## Routes - subscription ######################################################
###############################################################################


@app.route('/subscription/update/', methods=['POST'])
def update():
    """
    returns nothing
    ---
    post:
      operationId: score
      requestBody:
        content:
          application/json:
            {
            "source-id": id,
            "stream-id": id,
            "observation-id": id,
            "content": {
                key: value
            }}
      responses:
        '200':
          json
    """
    ''' from streamr - datastream has a new observation
    upon a new observation of a datastream, the nodejs app will send this
    python flask app a message on this route. The flask app will then pass the
    message to the data manager, specifically the scholar (and subscriber)
    threads by adding it to the appropriate subject. (the scholar, will add it
    to the correct table in the database history, notifying the subscriber who
    will, if used by any current best models, notify that model's predictor
    thread via a subject that a new observation is available by providing the
    observation directly in the subject).

    This app needs to create the DataManager, ModelManagers, and Learner in
    in order to have access to those objects. Specifically the DataManager,
    we need to be able to access it's BehaviorSubjects at data.newData
    so we can call .on_next() here to pass along the update got here from the
    Streamr LightClient, and trigger a new prediction.
    '''
    x = Observation.parse(request.json)
    start.engine.data.newData.on_next(x)

    return request.json

###############################################################################
## Routes - history ###########################################################
# we may be able to make these requests
###############################################################################


@app.route('/history/request/')
def publsih():
    ''' to streamr - create a new datastream to publish to '''
    # todo: spoof a dataset response - random generated data, so that the
    #       scholar can be built to ask for history and download it.
    resp = {}
    return render_template('unknown.html', **resp)


@app.route('/history/')
def publsihMeta():
    ''' to streamr - publish to a stream '''
    resp = {}
    return render_template('unknown.html', **resp)

###############################################################################
## UDP communication ##########################################################
###############################################################################


@app.route('/udp/stream')
def udpStream():

    def event_stream():
        count = 0
        while True:
            time.sleep(1)
            count += 1
            yield f"data: {count}\n\n"

    return Response(
        stream_with_context(event_stream()),
        content_type='text/event-stream')


@app.route('/udp/message', methods=['POST'])
def udpMessage():
    ''' recieves data from udp relay '''
    def validateJson() -> bool:
        try:
            json_data = json.loads(payload.get('data', ''))
            return json_data
        except json.JSONDecodeError:
            # Handle non-JSON data or log it
            print(f'Invalid JSON received from {payload.get("address")}: {payload.get("data")}')
        except Exception as e:
            # General error handling
            print(f'Error processing data from {payload.get("address")}: {e}')
    payload = request.json
    data = validateJson() # should data actually be json? is the protocol?
    print(data)


@app.route('/udp/ports', methods=['GET'])
def udpGet():
    ''' recieves data from udp relay '''
    # return {localPort: (remoteIp, remotePort)}
    return jsonify({})


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
