#!/usr/bin/env python
# -*- coding: utf-8 -*-
# mainly used for generating unique ids for data and model paths since they must be short

# run with:
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &
from flask_cors import CORS
from typing import Union
from functools import wraps, partial
import os
import sys
import json
import secrets
import webbrowser
import time
import traceback
import pandas as pd
import threading
import logging as log
from logging.handlers import RotatingFileHandler
from queue import Queue
from waitress import serve  # necessary ?
from flask import Flask, url_for, redirect, jsonify, flash, send_from_directory
from flask import session, request, render_template
from flask import Response, stream_with_context, render_template_string
from satorilib.concepts.structs import StreamId, StreamOverviews
from satorilib.api.wallet.wallet import TransactionFailure
from satorilib.api.time import timeToSeconds
from satorilib.api.wallet import RavencoinWallet, EvrmoreWallet
from satorilib.utils import getRandomName, getRandomQuote
from satorisynapse import Envelope, Signal
from satorineuron import VERSION, MOTTO, config
from satorineuron import logging
from satorineuron.relay import acceptRelaySubmission, processRelayCsv, generateHookFromTarget, registerDataStream
from satorineuron.web import forms
from satorineuron.init.start import StartupDag
from satorineuron.web.utils import deduceCadenceString, deduceOffsetString

logging.info(f'verison: {VERSION}', print=True)


###############################################################################
## Globals ####################################################################
###############################################################################

logging.logging.getLogger('werkzeug').setLevel(logging.logging.ERROR)

debug = True
darkmode = False
firstRun = True
badForm = {}
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
updateTime = 0
updateQueue = Queue()
timeout = 1
ENV = config.get().get('env', os.environ.get(
    'ENV', os.environ.get('SATORI_RUN_MODE', 'dev')))
CORS(app, origins=[{
    'local': 'http://192.168.0.10:5002',
    'dev': 'http://localhost:5002',
    'test': 'https://test.satorinet.io',
    'prod': 'https://satorinet.io'}[ENV]])

fail2ban_dir = config.get().get("fail2ban_log", None)
if fail2ban_dir:
    if not os.path.exists(fail2ban_dir):
        os.makedirs(fail2ban_dir)
    log_file = os.path.join(fail2ban_dir, 'satori_auth.log')

    fail2ban_handler = RotatingFileHandler(
        log_file, maxBytes=100000, backupCount=1)
    fail2ban_handler.setLevel(log.INFO)
    fail_log = log.getLogger("fail2ban")
    fail_log.addHandler(fail2ban_handler)
else:
    fail_log = None


###############################################################################
## Startup ####################################################################
###############################################################################
while True:
    try:
        start = StartupDag(
            env=ENV,
            urlServer={
                # TODO: local endpoint should be in a config file.
                'local': 'http://192.168.0.10:5002',
                'dev': 'http://localhost:5002',
                'test': 'https://test.satorinet.io',
                'prod': 'https://stage.satorinet.io'}[ENV],
            urlMundo={
                'local': 'http://192.168.0.10:5002',
                'dev': 'http://localhost:5002',
                'test': 'https://test.satorinet.io',
                'prod': 'https://mundo.satorinet.io'}[ENV],
            urlPubsubs={
                'local': ['ws://192.168.0.10:24603'],
                'dev': ['ws://localhost:24603'],
                'test': ['ws://test.satorinet.io:24603'],
                'prod': ['ws://pubsub1.satorinet.io:24603', 'ws://pubsub5.satorinet.io:24603', 'ws://pubsub6.satorinet.io:24603']}[ENV],
            # 'prod': ['ws://pubsub2.satorinet.foundation:24603', 'ws://pubsub5.satorinet.io:24603', 'ws://pubsub6.satorinet.io:24603']}[ENV],
            urlSynergy={
                'local': 'https://192.168.0.10:24602',
                'dev': 'https://localhost:24602',
                'test': 'https://test.satorinet.io:24602',
                'prod': 'https://synergy.satorinet.io:24602'}[ENV],
            isDebug=sys.argv[1] if len(sys.argv) > 1 else False)

        # print('building engine')
        # start.buildEngine()
        # threading.Thread(target=start.start, daemon=True).start()
        logging.info(f'environment: {ENV}', print=True)
        logging.info('Satori Neuron is starting...', color='green')
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


def hashSaltIt(string: str) -> str:
    import hashlib
    # return hashlib.sha256(rowStr.encode()).hexdigest()
    # return hashlib.md5(rowStr.encode()).hexdigest()
    return hashlib.blake2s(
        (string+string).encode(),
        digest_size=8).hexdigest()


def isActuallyLockable():
    conf = config.get()
    return conf.get('neuron lock enabled') is not None and (
        conf.get('neuron lock hash') is not None or
        conf.get('neuron lock password') is not None)


def isActuallyLocked():
    conf = config.get()
    return conf.get('neuron lock enabled') == True and (
        conf.get('neuron lock hash') is not None or
        conf.get('neuron lock password') is not None)


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


def getResp(resp: Union[dict, None] = None) -> dict:
    return {
        'version': VERSION,
        'lockEnabled': isActuallyLocked(),
        'lockable': isActuallyLockable(),
        'motto': MOTTO,
        'env': ENV,
        'paused': start.paused,
        'darkmode': darkmode,
        'title': 'Satori',
        **(resp or {})}


def closeVault(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start.closeVault()
        return f(*args, **kwargs)
    return decorated_function


def authRequired(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            # conf = config.get()
            # if not conf.get('neuron lock enabled', False) or (
            #    not conf.get('neuron lock password') and
            #    not conf.get('neuron lock hash')
            # ):
            if isActuallyLocked():
                return redirect(url_for('passphrase', next=request.url))
            else:
                session['authenticated'] = True
        return f(*args, **kwargs)
    return decorated_function


passphrase_html = '''
    <!doctype html>
    <title>Satori</title>
    <h1>Unlock the Satori Neuron</h1>
    <form method="post">
      <p><input type="password" name="passphrase">
      <input type="hidden" name="next" value="{{ next }}">
      <p><input type="submit" name="unlock" value="Submit">
    </form>
'''


@app.route('/unlock', methods=['GET', 'POST'])
def passphrase():

    def tryToInterpretAsInteger(password: str, exectedPassword: Union[str, int]) -> bool:
        if isinstance(exectedPassword, int):
            try:
                return int(password) == expectedPassword
            except Exception as _:
                pass
        if fail_log:
            fail_log.warning(
                f"Failed login attempt | IP: {request.remote_addr}")
        return False

    global timeout
    if request.method == 'POST':
        time.sleep(timeout)
        target = request.form.get('next') or 'dashboard'
        conf = config.get()
        expectedPassword = conf.get('neuron lock password')
        expectedPassword = expectedPassword or conf.get('neuron lock hash', '')
        if (
            request.form['passphrase'] == expectedPassword or
            hashSaltIt(request.form['passphrase']) == expectedPassword or
            tryToInterpretAsInteger(
                request.form['passphrase'], expectedPassword)
        ):
            session['authenticated'] = True
            timeout = 1
            return redirect(target)
        else:
            timeout = min(timeout * 1.618, 60*5)
            return "Wrong passphrase, try again.\n\nIf you're unable to unlock your Neuron remove the setting in the config file."
    next_url = request.args.get('next')
    return render_template_string(passphrase_html, next=next_url)


@app.route('/lock/enable', methods=['GET', 'POST'])
def lockEnable():
    # vaultPath = config.walletPath('vault.yaml')
    # if os.path.exists(vaultPath) or create:
    if isActuallyLockable():
        config.add(data={'neuron lock enabled': True})
    return redirect(url_for('dashboard'))


@app.route('/lock/relock', methods=['GET', 'POST'])
@authRequired
def lockRelock():
    ''' no ability to disable, this gives the user peace of mind '''
    session['authenticated'] = False
    return redirect(url_for('dashboard'))

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
@authRequired
def sendStatic(path):
    if start.vault is not None and not start.vault.isEncrypted:
        return send_from_directory('static', path)
    flash('please unlock the vault first')
    return redirect(url_for('dashboard'))


@app.route('/upload_history_csv', methods=['POST'])
@authRequired
def uploadHistoryCsv():
    msg, status, f = getFile('.csv')
    if f is not None:
        f.save('/Satori/Neuron/uploaded/history.csv')
        return 'Successful upload.', 200
    else:
        flash(msg, 'success' if status == 200 else 'error')
    return redirect(url_for('dashboard'))


@app.route('/upload_datastream_csv', methods=['POST'])
@authRequired
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


# @app.route('/test')
# def test():
#    logging.info(request.MOBILE)
#    return render_template('test.html')


# @app.route('/kwargs')
# def kwargs():
#    ''' ...com/kwargs?0-name=widget_name0&0-value=widget_value0&0-type=widget_type0&1-name=widget_name1&1-value=widget_value1&1-#type=widget_type1 '''
#    kwargs = {}
#    for i in range(25):
#        if request.args.get(f'{i}-name') and request.args.get(f'{i}-value'):
#            kwargs[request.args.get(f'{i}-name')
#                   ] = request.args.get(f'{i}-value')
#            kwargs[request.args.get(f'{i}-name') +
#                   '-type'] = request.args.get(f'{i}-type')
#    return jsonify(kwargs)


@app.route('/ping', methods=['GET'])
def ping():
    from datetime import datetime
    return jsonify({'now': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


@app.route('/pause/<timeout>', methods=['GET'])
@authRequired
def pause(timeout):
    try:
        timeout = int(timeout)
        if timeout < 12:
            start.pause(timeout*60*60)
    except Exception as _:
        flash('invalid pause timeout', 'error')
    return redirect(url_for('dashboard'))


@app.route('/unpause', methods=['GET'])
@authRequired
def unpause():
    start.unpause()
    return redirect(url_for('dashboard'))


@app.route('/backup/<target>', methods=['GET'])
@authRequired
def backup(target: str = 'satori'):
    if start.vault is not None and not start.vault.isEncrypted:
        outputPath = '/Satori/Neuron/satorineuron/web/static/download'
        if target == 'satori':
            from satorilib.api.disk.zip.zip import zipSelected
            zipSelected(
                folderPath=f'/Satori/Neuron/{target}',
                outputPath=f'{outputPath}/{target}.zip',
                selectedFiles=['config', 'data', 'models', 'wallet', 'uploaded'])
        else:
            from satorilib.api.disk.zip.zip import zipFolder
            zipFolder(
                folderPath=f'/Satori/Neuron/{target}',
                outputPath=f'{outputPath}/{target}')
        return redirect(url_for('sendStatic', path=f'download/{target}.zip'))
    flash('please unlock the vault first')
    return redirect(url_for('dashboard'))


@app.route('/restart', methods=['GET'])
@authRequired
def restart():
    start.udpQueue.put(Envelope(ip='', vesicle=Signal(restart=True)))
    html = (
        '<!DOCTYPE html>'
        '<html>'
        '<head>'
        '    <title>Restarting Satori Neuron</title>'
        '    <script type="text/javascript">'
        '        setTimeout(function(){'
        '            window.location.href = window.location.protocol + "//" + window.location.host;'
        '        }, 1000 * 60 * 10); // 600,000 milliseconds'
        '    </script>'
        '</head>'
        '<body>'
        '    <p>Satori Neuron is attempting to restart. <b>Please wait,</b> the restart process can take several minutes as it downloads updates.</p>'
        '    <p>If after 10 minutes this page has not refreshed, <a href="javascript:void(0);" onclick="window.location.href = window.location.protocol' +
        " + '//' + " + 'window.location.host;">click here to refresh the Satori Neuron UI</a>.</p>'
        '    <p>Thank you.</p>'
        '</body>'
        '</html>'
    )
    return html, 200


@app.route('/shutdown', methods=['GET'])
@authRequired
def shutdown():
    start.udpQueue.put(Envelope(ip='', vesicle=Signal(shutdown=True)))
    html = (
        '<!DOCTYPE html>'
        '<html>'
        '<head>'
        '    <title>Shutting Down Satori Neuron</title>'
        '</head>'
        '<body>'
        '    <p>Satori Neuron is attempting to shut down. To verify it has shut down you can make sure the container is not running under the Container tab in Docker, and you can close the terminal window which shows the logs of the Satori Neuron.</p>'
        '</body>'
        '</html>'
    )
    return html, 200


@app.route('/mode/light', methods=['GET'])
@authRequired
def modeLight():
    global darkmode
    darkmode = False
    return redirect(url_for('dashboard'))


@app.route('/mode/dark', methods=['GET'])
@authRequired
def modeDark():
    global darkmode
    darkmode = True
    return redirect(url_for('dashboard'))

###############################################################################
## Routes - forms #############################################################
###############################################################################


@app.route('/configuration', methods=['GET', 'POST'])
@authRequired
@closeVault
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
        return render_template('forms/config.html', **getResp({
            'title': 'Configuration',
            'edit_configuration': edit_configuration}))

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
@authRequired
def hook(target: str = 'Close'):
    ''' generates a hook for the given target '''
    return generateHookFromTarget(target)


@app.route('/hook/', methods=['GET'])
@authRequired
def hookEmptyTarget():
    ''' generates a hook for the given target '''
    # in the case target is empty string
    return generateHookFromTarget('Close')


@app.route('/relay', methods=['POST'])
@authRequired
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
    #    if not start.relayValidation.validRelay(data):
    #        return 'Invalid payload. here is an example: {"source": "satori", "name": "nameOfSomeAPI", "target": "optional", "data": 420}', 400
    #    if not start.relayValidation.streamClaimed(
    #        name=data.get('name'),
    #        target=data.get('target')
    #    ):
    #        save = start.relayValidation.registerStream(
    #            data=data)
    #        if save == False:
    #            return 'Unable to register stream with server', 500
    #        # get pubkey, recreate connection...
    #        start.checkin()
    #        start.pubsConnect()
    #    # ...pass data onto pubsub
    #    start.publish(
    #        topic=StreamId(
    #            source=data.get('source', 'satori'),
    #            author=start.wallet.publicKey,
    #            stream=data.get('name'),
    #            target=data.get('target')).topic(),
    #        data=data.get('data'))
    #    return 'Success: ', 200
    return acceptRelaySubmission(start, json.loads(request.get_json()))


@app.route('/mining/mode/on', methods=['GET'])
@authRequired
def miningModeOn():
    return str(start.setMiningMode(True)), 200


@app.route('/mining/mode/off', methods=['GET'])
@authRequired
def miningModeOff():
    return str(start.setMiningMode(False)), 200


@app.route('/stake/check', methods=['GET'])
@authRequired
def stakeCheck():
    status = start.performStakeCheck()
    return str(status), 200


@app.route('/stake/proxy/request/<address>', methods=['GET'])
@authRequired
def stakeProxyRequest(address: str):
    success, msg = start.server.stakeProxyRequest(address)
    if success:
        return str('ok'), 200
    return str('failure'), 400


@app.route('/send_satori_transaction_from_wallet/<network>', methods=['POST'])
@authRequired
def sendSatoriTransactionFromWallet(network: str = 'main'):
    # return sendSatoriTransactionUsing(start.getWallet(network=network), network, 'wallet')
    result = sendSatoriTransactionUsing(
        start.getWallet(network=network), network, 'wallet')
    if isinstance(result, str) and len(result) == 64:
        flash(str(result))
    return redirect(f'/wallet/{network}')


@app.route('/send_satori_transaction_from_vault/<network>', methods=['POST'])
@authRequired
def sendSatoriTransactionFromVault(network: str = 'main'):
    result = sendSatoriTransactionUsing(start.vault, network, 'vault')
    if len(result) == 64:
        flash(str(result))
    return redirect(f'/vault/{network}')


def sendSatoriTransactionUsing(
    myWallet: Union[RavencoinWallet, EvrmoreWallet],
    network: str,
    loc: str,
    override: Union[dict[str, str], None] = None
):
    if myWallet is None:
        flash(f'Send Failed: {e}')
        return redirect(f'/wallet/{network}')

    import importlib
    global forms
    global badForm
    forms = importlib.reload(forms)

    def accept_submittion(sendSatoriForm):
        def refreshWallet():
            time.sleep(4)
            # doesn't respect the cooldown
            myWallet.get(allWalletInfo=False)

        # doesn't respect the cooldown
        myWallet.getUnspentSignatures(force=True)
        try:
            # logging.debug('sweep', sendSatoriForm['sweep'], color='magenta')
            result = myWallet.typicalNeuronTransaction(
                sweep=sendSatoriForm['sweep'],
                amount=sendSatoriForm['amount'] or 0,
                address=sendSatoriForm['address'] or '')
            if result.msg == 'creating partial, need feeSatsReserved.':
                responseJson = start.server.requestSimplePartial(
                    network=network)
                result = myWallet.typicalNeuronTransaction(
                    sweep=sendSatoriForm['sweep'],
                    amount=sendSatoriForm['amount'] or 0,
                    address=sendSatoriForm['address'] or '',
                    completerAddress=responseJson.get('completerAddress'),
                    feeSatsReserved=responseJson.get('feeSatsReserved'),
                    changeAddress=responseJson.get('changeAddress'),
                )
            if result is None:
                flash('Send Failed: wait 10 minutes, refresh, and try again.')
            elif result.success:
                if (  # checking any on of these should suffice in theory...
                    result.tx is not None and
                    result.reportedFeeSats is not None and
                    result.reportedFeeSats > 0 and
                    result.msg == 'send transaction requires fee.'
                ):
                    r = start.server.broadcastSimplePartial(
                        tx=result.tx,
                        reportedFeeSats=result.reportedFeeSats,
                        feeSatsReserved=responseJson.get('feeSatsReserved'),
                        walletId=responseJson.get('partialId'),
                        network=(
                            'ravencoin' if start.networkIsTest(network)
                            else 'evrmore'))
                    if r.text != '':
                        return r.text
                    else:
                        flash(
                            'Send Failed: wait 10 minutes, refresh, and try again.')
                else:
                    return result.result
            else:
                flash(f'Send Failed: {result.msg}')
        except TransactionFailure as e:
            flash(f'Send Failed: {e}')
        refreshWallet()
        return result

    sendSatoriForm = forms.SendSatoriTransaction(formdata=request.form)
    sendForm = {}
    override = override or {}
    sendForm['sweep'] = override.get('sweep', sendSatoriForm.sweep.data)
    sendForm['amount'] = override.get(
        'amount', sendSatoriForm.amount.data or 0)
    sendForm['address'] = override.get(
        'address', sendSatoriForm.address.data or '')
    return accept_submittion(sendForm)


@app.route('/register_stream', methods=['POST'])
@authRequired
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
        elif status == 200:
            badForm = {}
        for msg in msgs:
            flash(msg)
        return redirect('/dashboard')

    newRelayStream = forms.RelayStreamForm(formdata=request.form)
    return accept_submittion(newRelayStream)


@app.route('/edit_stream/<topic>', methods=['GET'])
@authRequired
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
    # return redirect('/dashboard#:~:text=Create%20Data%20Stream')
    return redirect('/dashboard#CreateDataStream')


# @app.route('/remove_stream/<source>/<stream>/<target>/', methods=['GET'])
# def removeStream(source=None, stream=None, target=None):
@app.route('/remove_stream/<topic>', methods=['GET'])
@authRequired
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
            # should match removeRelayStream.author
            'pubkey': start.wallet.publicKey,
            'stream': removeRelayStream.stream,
            'target': removeRelayStream.target,
        }))
        if (r.status_code == 200):
            msg = 'Stream deleted.'
            # get pubkey, recreate connection, restart relay engine
            try:
                start.relayValidation.claimed.remove(removeRelayStream)
            except Exception as e:
                logging.error('remove stream logic err', e)
            start.checkin()
            start.pubsConnect()
            start.startRelay()
        else:
            msg = 'Unable to delete stream.'
        if doRedirect:
            flash(msg)
            return redirect('/dashboard')

    return accept_submittion(removeRelayStream, doRedirect)


@app.route('/remove_stream_by_post', methods=['POST'])
@authRequired
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
                logging.error('remove strem by post err', e)
            start.checkin()
            start.pubsConnect()
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


@app.route('/')
@app.route('/home', methods=['GET'])
@app.route('/index', methods=['GET'])
@app.route('/dashboard', methods=['GET'])
@closeVault
@authRequired
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
    global firstRun
    theFirstRun = firstRun
    firstRun = False
    streamOverviews = (
        [model.miniOverview() for model in start.engine.models]
        if start.engine is not None else [])  # StreamOverviews.demo()
    start.openWallet()
    if start.vault is not None:
        start.openVault()
    holdingBalance = round(
        start.wallet.balanceAmount + (
            start.vault.balanceAmount if start.vault is not None else 0), 8)
    stakeStatus = holdingBalance >= 5 or start.details.wallet.get('rewardaddress', None) not in [
        None,
        start.details.wallet.get('address'),
        start.details.wallet.get('vaultaddress')]
    return render_template('dashboard.html', **getResp({
        'firstRun': theFirstRun,
        'wallet': start.wallet,
        # instead of this make chain single source of truth
        # 'stakeStatus': start.stakeStatus or holdingBalance >= 5
        'stakeStatus': stakeStatus,
        'miningMode': start.miningMode and stakeStatus,
        'miningDisplay': 'none',
        'proxyDisplay': 'none',
        'holdingBalance': holdingBalance,
        'streamOverviews': streamOverviews,
        'configOverrides': config.get(),
        'paused': start.paused,
        'newRelayStream': present_stream_form(),
        'shortenFunction': lambda x: x[0:15] + '...' if len(x) > 18 else x,
        'quote': getRandomQuote(),
        'relayStreams':  # example stream +
        ([
            {
                **stream.asMap(noneToBlank=True),
                **{'latest': start.relay.latest.get(stream.streamId.topic(), '')},
                **{'late': start.relay.late(stream.streamId, timeToSeconds(start.cacheOf(stream.streamId).getLatestObservationTime()))},
                **{'cadenceStr': deduceCadenceString(stream.cadence)},
                **{'offsetStr': deduceOffsetString(stream.offset)}}
            for stream in start.relay.streams]
         if start.relay is not None else []),

        'placeholderPostRequestHook': """def postRequestHook(response: 'requests.Response'):
    '''
    called and given the response each time
    the endpoint for this data stream is hit.
    returns the value of the observation
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
        pass

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
    }))


# @app.route('/fetch/balance', methods=['POST'])
# @authRequired
# def fetchBalance():
#    start.openWallet()
#    if start.vault is not None:
#    return 'OK', 200


@app.route('/fetch/wallet/stats/daily', methods=['GET'])
@authRequired
def fetchWalletStatsDaily():
    stats = start.server.fetchWalletStatsDaily()
    if stats == '':
        return 'No stats available.', 200
    df = pd.DataFrame(stats)
    if df.empty:
        return 'No stats available.', 200
    required_columns = ['placement', 'competitors']
    if not all(col in df.columns for col in required_columns):
        return 'No stats available.', 200
    # Calculate the normalized placement for each row
    df['normalized_placement'] = df['placement'] / df['competitors']
    # Calculate the average of normalized placements
    avg_normalized_placement = df['normalized_placement'].mean()*100
    count = len(df)
    # average_placement = df.groupby('predictor_stream_id')['placement'].mean().reset_index()
    return (
        f'This Neuron has participated in {count} competition{"" if count == 1 else "s"} today, '
        f'with an average placement of {int(avg_normalized_placement)} out of 100'), 200


@app.route('/pin_depin', methods=['POST'])
@authRequired
def pinDepinStream():
    # tell the server we want to toggle the pin of this stream
    # on the server that means mark the subscription as chosen by user
    # s = StreamId.fromTopic(request.data) # binary string actually works
    s = request.json
    payload = {
        'source': s.get('source', 'satori'),
        # 'pubkey': start.wallet.publicKey,
        'author': s.get('author'),
        'stream': s.get('stream', s.get('name')),
        'target': s.get('target'),
        # 'client': start.wallet.publicKey, # gets this from authenticated call
    }
    success, result = start.server.pinDepinStream(stream=payload)
    # return 'pinned' 'depinned' based on server response
    if success:
        return result, 200
    logging.error('pinDepinStream', s, success, result)
    return 'OK', 200


@app.route('/connections-status/refresh', methods=['GET'])
def connectionsStatusRefresh():
    start.connectionsStatusQueue.put(start.latestConnectionStatus)
    return str(start.latestConnectionStatus).replace("'", '"').replace(': True', ': true').replace(': False', ': false'), 200


@app.route('/connections-status')
def connectionsStatus():
    def update():
        while True:
            yield "data: " + str(start.connectionsStatusQueue.get()).replace("'", '"').replace(': True', ': true').replace(': False', ': false') + "\n\n"

    return Response(update(), mimetype='text/event-stream')


# old way
# @app.route('/model-updates')
# def modelUpdates():
#    def update():
#        global updating
#        if updating:
#            yield 'data: []\n\n'
#        logging.debug('modelUpdates', updating, color='yellow')
#        updating = True
#        streamOverviews = StreamOverviews(start.engine)
#        logging.debug('streamOverviews', streamOverviews, color='yellow')
#        listeners = []
#        # listeners.append(start.engine.data.newData.subscribe(
#        #    lambda x: streamOverviews.setIt() if x is not None else None))
#        if start.engine is not None:
#            logging.debug('start.engine is not None',
#                          start.engine is not None, color='yellow')
#            for model in start.engine.models:
#                listeners.append(model.predictionUpdate.subscribe(
#                    lambda x: streamOverviews.setIt() if x is not None else None))
#            while True:
#                logging.debug('in while loop', color='yellow')
#                if streamOverviews.viewed:
#                    logging.debug('NOT yeilding',
#                                  streamOverviews.viewed, color='yellow')
#                    time.sleep(60)
#                else:
#                    logging.debug('yeilding',
#                                  str(streamOverviews.overview).replace("'", '"'), color='yellow')
#                    # parse it out here?
#                    yield "data: " + str(streamOverviews.overview).replace("'", '"') + "\n\n"
#                    streamOverviews.setViewed()
#        else:
#            logging.debug('yeilding once', len(
#                str(streamOverviews.demo).replace("'", '"')), color='yellow')
#            yield "data: " + str(streamOverviews.demo).replace("'", '"') + "\n\n"
#
#    import time
#    return Response(update(), mimetype='text/event-stream')

@app.route('/model-updates')
def modelUpdates():
    def update():

        def on_next(model, x):
            global updateQueue
            if x is not None:
                overview = model.overview()
                # logging.debug('Yielding', overview.values, color='yellow')
                updateQueue.put(
                    "data: " + str(overview).replace("'", '"') + "\n\n")

        global updateTime
        global updateQueue
        listeners = []
        import time
        thisThreadsTime = time.time()
        updateTime = thisThreadsTime
        if start.engine is not None:
            for model in start.engine.models:
                # logging.debug('model', model.dataset.dropna(
                # ).iloc[-20:].loc[:, (model.variable.source, model.variable.author, model.variable.stream, model.variable.target)], color='yellow')
                listeners.append(
                    model.privatePredictionUpdate.subscribe(on_next=partial(on_next, model)))
            while True:
                data = updateQueue.get()
                if thisThreadsTime != updateTime:
                    return Response('data: redundantCall\n\n', mimetype='text/event-stream')
                yield data
        else:
            # logging.debug('yeilding once', len(
            #     str(StreamOverviews.demo()).replace("'", '"')), color='yellow')
            yield "data: " + str(StreamOverviews.demo()).replace("'", '"') + "\n\n"

    return Response(update(), mimetype='text/event-stream')


@app.route('/working_updates')
def workingUpdates():
    def update():
        try:
            yield 'data: \n\n'
            # messages = []
            # listeners = []
            # listeners.append(start.workingUpdates.subscribe(
            #    lambda x: messages.append(x) if x is not None else None))
            while True:
                msg = start.workingUpdates.get()
                if msg == 'working_updates_end':
                    break
                yield "data: " + str(msg).replace("'", '"') + "\n\n"
                # time.sleep(1)
                # if len(messages) > 0:
                #    msg = messages.pop(0)
                #    if msg == 'working_updates_end':
                #        break
                #    yield "data: " + str(msg).replace("'", '"') + "\n\n"
        except Exception as e:
            logging.error('working_updates error:', e, print=True)

    # import time
    return Response(update(), mimetype='text/event-stream')


@app.route('/working_updates_end')
def workingUpdatesEnd():
    # start.workingUpdates.on_next('working_updates_end')
    start.workingUpdates.put('working_updates_end')
    return 'ok', 200


@app.route('/chat', methods=['GET'])
@authRequired
def chatPage():
    def presentChatForm():
        '''
        this function could be used to fill a form with the current
        configuration for a stream in order to edit it.
        '''
        chatForm = forms.ChatPrompt(formdata=request.form)
        chatForm.prompt.data = ''
        return chatForm

    return render_template('chat-page.html', **getResp({
        'title': 'Chat',
        'chatForm': presentChatForm()}))


@app.route('/chat/session', methods=['POST'])
@authRequired
def chatSession():
    def query(chatForm: str = ''):
        import satorineuron.chat as chat
        prompt = chatForm.prompt.data
        for words in chat.session(message=prompt):
            start.chatUpdates.put(words)

    query(forms.ChatPrompt(formdata=request.form))
    return 'ok', 200


@app.route('/chat/updates')
@authRequired
def chatUpdates():
    def update():
        try:
            yield 'data: \n\n'
            while True:
                msg = start.chatUpdates.get()
                if msg == 'chat_updates_end':
                    break
                text = msg['message']['content']
                yield "data: " + str(text) + "\n\n"
                if msg['done']:
                    yield "data: \n\n\n\n"
                    break
        except Exception as e:
            logging.error('chatUpdates error:', e, print=True)
    return Response(update(), mimetype='text/event-stream')


@app.route('/chat/updates/end')
@authRequired
def chatUpdatesEnd():
    start.chatUpdates.send('chat_updates_end')
    return 'ok', 200


@app.route('/remove_wallet_alias/<network>')
@authRequired
def removeWalletAlias(network: str = 'main', alias: str = ''):
    myWallet = start.openWallet(network=network)
    myWallet.setAlias(None)
    start.server.removeWalletAlias()
    return wallet(network=network)
    # return render_template('wallet-page.html', **getResp({
    #    'title': 'Wallet',
    #    'walletIcon': 'wallet',
    #    'network': network,
    #    'image': getQRCode(myWallet.address),
    #    'wallet': myWallet,
    #    'exampleAlias': getRandomName(),
    #    'alias': '',
    #    'sendSatoriTransaction': presentSendSatoriTransactionform(request.form)}))


@app.route('/update_wallet_alias/<network>/<alias>')
@authRequired
def updateWalletAlias(network: str = 'main', alias: str = ''):
    myWallet = start.openWallet(network=network)
    myWallet.setAlias(alias)
    start.server.updateWalletAlias(alias)
    return wallet(network=network)
    # ('wallet-page.html', **getResp({
    #        'title': 'Wallet',
    #        'walletIcon': 'wallet',
    #        'network': network,
    #        'image': getQRCode(myWallet.address),
    #        'wallet': myWallet,
    #        'exampleAlias': getRandomName(),
    #        'alias': alias,
    #        'sendSatoriTransaction': presentSendSatoriTransactionform(request.form)}))


@app.route('/wallet/<network>', methods=['GET', 'POST'])
@closeVault
@authRequired
def wallet(network: str = 'main'):
    def accept_submittion(passwordForm):
        _vault = start.openVault(
            password=passwordForm.password.data,
            create=True)
        # if rvn is None or not rvn.isEncrypted:
        #    flash('unable to open vault')

    myWallet = start.openWallet(network=network)
    alias = myWallet.alias or start.server.getWalletAlias()
    if config.get().get('wallet lock'):
        if request.method == 'POST':
            accept_submittion(forms.VaultPassword(formdata=request.form))
        if start.vault is not None and not start.vault.isEncrypted:
            return render_template('wallet-page.html', **getResp({
                'title': 'Wallet',
                'walletIcon': 'wallet',
                'proxyParent': start.rewardAddress,
                'vaultIsSetup': start.vault is not None,
                'unlocked': True,
                'walletlockEnabled': True,
                'network': network,
                'image': getQRCode(myWallet.address),
                'wallet': myWallet,
                'exampleAlias': getRandomName(),
                'alias': alias,
                'sendSatoriTransaction': presentSendSatoriTransactionform(request.form)}))
        return render_template('wallet-page.html', **getResp({
            'title': 'Wallet',
            'walletIcon': 'wallet',
            'proxyParent': start.rewardAddress,
            'vaultIsSetup': start.vault is not None,
            'unlocked': False,
            'walletlockEnabled': True,
            'network': network,
            'vaultPasswordForm': presentVaultPasswordForm(),
        }))
    return render_template('wallet-page.html', **getResp({
        'title': 'Wallet',
        'walletIcon': 'wallet',
        'proxyParent': start.rewardAddress,
        'vaultIsSetup': start.vault is not None,
        'unlocked': True,
        'walletlockEnabled': False,
        'network': network,
        'image': getQRCode(myWallet.address),
        'wallet': myWallet,
        'exampleAlias': getRandomName(),
        'alias': alias,
        'sendSatoriTransaction': presentSendSatoriTransactionform(request.form)}))


def getQRCode(value: str) -> str:
    import io
    import qrcode
    from base64 import b64encode
    img = qrcode.make(value)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    # return send_file(buf, mimetype='image/jpeg')
    img = b64encode(buf.getvalue()).decode('ascii')
    return f'<img src="data:image/jpg;base64,{img}" class="img-fluid"/>'


def presentSendSatoriTransactionform(formData):
    '''
    this function could be used to fill a form with the current
    configuration for a stream in order to edit it.
    '''
    # not sure if this part is necessary
    global forms
    import importlib
    forms = importlib.reload(forms)
    sendSatoriTransaction = forms.SendSatoriTransaction(formdata=formData)
    sendSatoriTransaction.address.data = ''
    sendSatoriTransaction.amount.data = 0
    return sendSatoriTransaction


@app.route('/wallet_lock/enable', methods=['GET'])
@authRequired
def enableWalletLock():
    # the network portion should be whatever network I'm on.
    config.add(data={'wallet lock': True})
    return 'OK', 200


@app.route('/wallet_lock/disable', methods=['GET'])
@authRequired
def disableWalletLock():
    if start.vault is None:
        flash('Must unlock your wallet to disable walletlock.')
        return redirect('/dashboard')
    config.add(data={'wallet lock': False})
    return 'OK', 200


@app.route('/vault/<network>', methods=['GET', 'POST'])
@authRequired
def vaultMainTest(network: str = 'main'):
    return vault()


def presentVaultPasswordForm():
    '''
    this function could be used to fill a form with the current
    configuration for a stream in order to edit it.
    '''
    passwordForm = forms.VaultPassword(formdata=request.form)
    passwordForm.password.data = ''
    return passwordForm


@app.route('/vault', methods=['GET', 'POST'])
@authRequired
def vault():

    def defaultMineToVault():
        try:
            enableMineToVault
        except Exception as _:
            pass

    def accept_submittion(passwordForm):
        # start.workingUpdates.put('decrypting...')
        # logging.debug(passwordForm.password.data, color='yellow')
        _vault = start.openVault(
            password=passwordForm.password.data,
            create=True)
        if not config.get().get('neuron lock hash', False):
            config.add(data={'neuron lock hash': hashSaltIt(
                passwordForm.password.data)})
            if 'neuron lock enabled' not in config.get():
                config.add(data={'neuron lock enabled': False})
        # if rvn is None or not rvn.isEncrypted:
        #    flash('unable to open vault')

    if request.method == 'POST':
        accept_submittion(forms.VaultPassword(formdata=request.form))
    if start.vault is not None and not start.vault.isEncrypted:
        # start.workingUpdates.put('downloading balance...')
        from satorilib.api.wallet.eth import EthereumWallet
        account = EthereumWallet.generateAccount(start.vault._entropy)
        # if start.server.betaStatus()[1].get('value') == 1:
        #    claimResult = start.server.betaClaim(account.address)[1]
        #    logging.info(
        #        'beta NFT not yet claimed. Claiming Beta NFT:',
        #        claimResult.get('description'))
        # threading.Thread(target=defaultMineToVault, daemon=True).start()
        return render_template('vault.html', **getResp({
            'title': 'Vault',
            'walletIcon': 'lock',
            'image': getQRCode(start.vault.address),
            'network': start.network,  # change to main when ready
            'minedtovault': start.mineToVault,  # start.server.minedToVault(),
            'vaultPasswordForm': presentVaultPasswordForm(),
            'vaultOpened': True,
            'wallet': start.vault,
            'ethAddress': account.address,
            'ethPrivateKey': account.key.to_0x_hex(),
            'sendSatoriTransaction': presentSendSatoriTransactionform(request.form)}))
    # start.workingUpdates.put('loading...')
    return render_template('vault.html', **getResp({
        'title': 'Vault',
        'walletIcon': 'lock',
        'image': '',
        'network': start.network,  # change to main when ready
        'minedtovault': start.mineToVault,  # start.server.minedToVault(),
        'vaultPasswordForm': presentVaultPasswordForm(),
        'vaultOpened': False,
        'wallet': start.vault,
        'sendSatoriTransaction': presentSendSatoriTransactionform(request.form)}))


@app.route('/vault/report', methods=['GET'])
@authRequired
def reportVault(network: str = 'main'):
    if start.vault is None:
        return redirect('/dashboard')
    # the network portion should be whatever network I'm on.
    vault = start.getVault(network=network)
    vaultAddress = vault.address
    success, result = start.server.reportVault(
        walletSignature=start.getWallet(network=network).sign(vaultAddress),
        vaultSignature=vault.sign(vaultAddress),
        vaultPubkey=vault.publicKey,
        address=vaultAddress)
    if success:
        return 'OK', 200
    return f'Failed to report vault: {result}', 400


@app.route('/mining/to/address', methods=['GET'])
@authRequired
def mineToAddressStatus():
    return str(start.server.mineToAddressStatus()), 200


@app.route('/mine/to/address/<address>', methods=['GET'])
@authRequired
def mineToAddress(address: str):
    if start.vault is None:
        return '', 200
    # the network portion should be whatever network I'm on.
    network = 'main'
    start.details.wallet['rewardaddress'] = address
    vault = start.getVault(network=network)
    success, result = start.server.mineToAddress(
        vaultSignature=vault.sign(address),
        vaultPubkey=vault.publicKey,
        address=address)
    if success:
        return 'OK', 200
    return f'Failed to report vault: {result}', 400


@app.route('/stake/for/address/<address>', methods=['GET'])
@authRequired
def stakeForAddress(address: str):
    if start.vault is None:
        return '', 200
    # the network portion should be whatever network I'm on.
    network = 'main'
    vault = start.getVault(network=network)
    success, result = start.server.stakeForAddress(
        vaultSignature=vault.sign(address),
        vaultPubkey=vault.publicKey,
        address=address)
    if success:
        return 'OK', 200
    return f'Failed to report vault: {result}', 400


@app.route('/mine_to_vault/enable/<network>', methods=['GET'])
@authRequired
def enableMineToVault(network: str = 'main'):
    if start.vault is None:
        flash('Must unlock your vault to enable minetovault.')
        return redirect('/dashboard')
    success, result = start.enableMineToVault()
    if success:
        return 'OK', 200
    return f'Failed to enable minetovault: {result}', 400


@app.route('/mine_to_vault/disable/<network>', methods=['GET'])
@authRequired
def disableMineToVault(network: str = 'main'):
    if start.vault is None:
        flash('Must unlock your vault to disable minetovault.')
        return redirect('/dashboard')
    success, result = start.disableMineToVault()
    if success:
        return 'OK', 200
    return f'Failed to disable minetovault: {result}', 400


@app.route('/proxy/parent/status', methods=['GET'])
@authRequired
def proxyParentStatus():
    success, result = start.server.stakeProxyChildren()
    if success:
        return result, 200
    return f'Failed stakeProxyChildren: {result}', 400


@app.route('/proxy/child/approve/<address>/<id>', methods=['GET'])
@authRequired
def approveProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyApprove(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyApprove: {result}', 400


@app.route('/proxy/child/deny/<address>/<id>', methods=['GET'])
@authRequired
def denyProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyDeny(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyDeny: {result}', 400


@app.route('/proxy/child/remove/<address>/<id>', methods=['GET'])
@authRequired
def removeProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyRemove(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyRemove: {result}', 400


@app.route('/vote', methods=['GET', 'POST'])
@authRequired
def vote():

    def getVotes(wallet):
        # def valuesAsNumbers(map: dict):
        #    return {k: int(v) for k, v in map.items()}
        x = {
            'communityVotes': start.server.getManifestVote(),
            'walletVotes': {k: v/100 for k, v in start.server.getManifestVote(wallet).items()},
            'vaultVotes': ({k: v/100 for k, v in start.server.getManifestVote(start.vault).items()}
                           if start.vault is not None and start.vault.isDecrypted else {
                'predictors': 0,
                'oracles': 0,
                'inviters': 0,
                'creators': 0,
                'managers': 0})}
        return x

    def getStreams(wallet):
        # todo convert result to the strucutre the template expects:
        # [ {'cols': 'value'}]
        streams = start.server.getSanctionVote(wallet, start.vault)
        # logging.debug('streams', [
        #              s for s in streams if s['oracle_alias'] is not None], color='yellow')
        return streams
        # return []
        # return [{
        #    'sanctioned': 10,
        #    'active': True,
        #    'oracle_pubkey': 'pubkey',
        #    'oacle_alias': 'alias',
        #    'stream': 'stream',
        #    'target': 'target',
        #    'start': 'start',
        #    'cadence': 60*10,
        #    'id': '0',
        #    'total_vote': 27,
        # }, {
        #    'sanctioned': 0,
        #    'active': False,
        #    'oracle': 'pubkey',
        #    'alias': 'alias',
        #    'stream': 'stream',
        #    'target': 'target',
        #    'start': 'start',
        #    'cadence': 60*15,
        #    'id': '1',
        #    'vote': 36,
        # }]

    def accept_submittion(passwordForm):
        _vault = start.openVault(password=passwordForm.password.data)
        # if rvn is None and not rvn.isEncrypted:
        #    flash('unable to open vault')

    if request.method == 'POST':
        accept_submittion(forms.VaultPassword(formdata=request.form))

    myWallet = start.getWallet(network=start.network)
    if start.vault is not None and not start.vault.isEncrypted:
        return render_template('vote.html', **getResp({
            'title': 'Vote',
            'network': start.network,
            'vaultPasswordForm': presentVaultPasswordForm(),
            'vaultOpened': True,
            'wallet': myWallet,
            'vault': start.vault,
            'streams': getStreams(myWallet),
            **getVotes(myWallet)}))
    return render_template('vote.html', **getResp({
        'title': 'Vote',
        'network': start.network,
        'vaultPasswordForm': presentVaultPasswordForm(),
        'vaultOpened': False,
        'wallet': myWallet,
        'vault': start.vault,
        'streams': getStreams(myWallet),
        **getVotes(myWallet)}))


@app.route('/vote/submit/manifest/wallet', methods=['POST'])
@authRequired
def voteSubmitManifestWallet():
    # logging.debug(request.json, color='yellow')
    if (
        request.json.get('walletPredictors') > 0 or
        request.json.get('walletOracles') > 0 or
        request.json.get('walletInviters') > 0 or
        request.json.get('walletCreators') > 0 or
        request.json.get('walletManagers') > 0
    ):
        start.server.submitMaifestVote(
            wallet=start.getWallet(network=start.network),
            votes={
                'predictors': request.json.get('walletPredictors', 0),
                'oracles': request.json.get('walletOracles', 0),
                'inviters': request.json.get('walletInviters', 0),
                'creators': request.json.get('walletCreators', 0),
                'managers': request.json.get('walletManagers', 0)})
    return jsonify({'message': 'Manifest votes received successfully'}), 200


@app.route('/system_metrics', methods=['GET'])
def systemMetrics():
    from satorilib.api import system
    return jsonify({
        'hostname': os.uname().nodename,
        'cpu': system.getProcessor(),
        'cpu_count': system.getProcessorCount(),
        'cpu_usage_percent': system.getProcessorUsage(),
        'memory': system.getRamDetails(),
        'memory_total_gb': system.getRam(),
        'memory_available_percent': system.getRamAvailablePercentage(),
        'swap': system.getSwapDetails(),
        'disk': system.getDiskDetails(),
        'boot_time': system.getBootTime(),
        'uptime': system.getUptime(),
        'version': VERSION,
        'timestamp': time.time(),
    }), 200


# @app.route('/vote/submit/manifest/vault', methods=['POST'])
# @authRequired
# def voteSubmitManifestVault():
#     # logging.debug(request.json, color='yellow')
#     vaultPredictors = request.json.get('vaultPredictors')
#     vaultOracles = request.json.get('vaultOracles')
#     vaultInviters = request.json.get('vaultInviters')
#     vaultCreators = request.json.get('vaultCreators')
#     vaultManagers = request.json.get('vaultManagers')
#     vaultPredictors = 0 if vaultPredictors.strip() == '' else int(vaultPredictors)
#     vaultOracles = 0 if vaultOracles.strip() == '' else int(vaultOracles)
#     vaultInviters = 0 if vaultInviters.strip() == '' else int(vaultInviters)
#     vaultCreators = 0 if vaultCreators.strip() == '' else int(vaultCreators)
#     vaultManagers = 0 if vaultManagers.strip() == '' else int(vaultManagers)
#     if (
#         (
#             vaultPredictors > 0 or
#             vaultOracles > 0 or
#             vaultInviters > 0 or
#             vaultCreators > 0 or
#             vaultManagers > 0
#         ) and start.vault is not None and start.vault.isDecrypted
#     ):
#         start.server.submitMaifestVote(
#             start.getWallet(network=start.network),
#             votes={
#                 # TODO: authenticate the vault.
#                 # 'vault': start.vault.address,
#                 'predictors': vaultPredictors,
#                 'oracles': vaultOracles,
#                 'inviters': vaultInviters,
#                 'creators': vaultCreators,
#                 'managers': vaultManagers})
#     return jsonify({'message': 'Manifest votes received successfully'}), 200


@app.route('/vote/submit/sanction/wallet', methods=['POST'])
@authRequired
def voteSubmitSanctionWallet():
    # logging.debug(request.json, color='yellow')
    # {'walletStreamIds': [0], 'vaultStreamIds': [], 'walletVotes': [27], 'vaultVotes': []}
    # zip(walletStreamIds, walletVotes)
    # {'walletStreamIds': [None], 'walletVotes': [1]}
    if (
        len(request.json.get('walletStreamIds', [])) > 0 and
        len(request.json.get('walletVotes', [])) > 0 and
        len(request.json.get('walletStreamIds', [])) == len(request.json.get(
            'walletVotes', []))
    ):
        start.server.submitSanctionVote(
            wallet=start.getWallet(network=start.network),
            votes={
                'streamIds': request.json.get('walletStreamIds'),
                'votes': request.json.get('walletVotes')})
    return jsonify({'message': 'Stream votes received successfully'}), 200


@app.route('/vote/submit/sanction/vault', methods=['POST'])
@authRequired
def voteSubmitSanctionVault():
    # logging.debug(request.json, color='yellow')
    # {'walletStreamIds': [0], 'vaultStreamIds': [], 'walletVotes': [27], 'vaultVotes': []}
    # zip(walletStreamIds, walletVotes)
    if (
        len(request.json.get('vaultStreamIds', [])) > 0 and
        len(request.json.get('vaultVotes', [])) > 0 and
        len(request.json.get('vaultStreamIds')) == len(request.json.get('vaultVotes', [])) and
        start.vault is not None and start.vault.isDecrypted
    ):
        start.server.submitSanctionVote(
            start.vault,
            votes={
                'streamIds': request.json.get('vaultStreamIds'),
                'votes': request.json.get('vaultVotes')})
    return jsonify({'message': 'Stream votes received successfully'}), 200


# todo: this needs a ui button.
# this ability to clear them all lets us just display a subset of streams to vote on with a search for a specific one


@app.route('/vote/remove_all/sanction', methods=['GET'])
@authRequired
def voteRemoveAllSanction():
    # logging.debug(request.json, color='yellow')
    start.server.removeSanctionVote(
        wallet=start.getWallet(network=start.network))
    if (start.vault is not None and start.vault.isDecrypted):
        start.server.removeSanctionVote(start.vault)
    return jsonify({'message': 'Stream votes received successfully'}), 200


@app.route('/relay_csv', methods=['GET'])
@authRequired
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
            **{'offsetStr': deduceOffsetString(stream.offset)}}
            for stream in start.relay.streams]
            if start.relay is not None else []).to_csv(index=False),
        200,
        {
            'Content-Type': 'text/csv',
            'Content-Disposition': 'attachment; filename=relay_streams.csv'
        }
    )


@app.route('/relay_history_csv/<topic>', methods=['GET'])
@authRequired
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
@authRequired
def mergeHistoryCsv(topic: str = None):
    ''' merge history uploaded  '''
    cache = start.cacheOf(StreamId.fromTopic(topic))
    if cache is not None:
        msg, status, f = getFile('.csv')
        if f is not None:
            df = pd.read_csv(f)
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
@authRequired
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
@authRequired
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
@authRequired
def publsih():
    ''' to streamr - create a new datastream to publish to '''
    # todo: spoof a dataset response - random generated data, so that the
    #       scholar can be built to ask for history and download it.
    return render_template('unknown.html', **getResp())


@app.route('/history')
@authRequired
def publsihMeta():
    ''' to streamr - publish to a stream '''
    return render_template('unknown.html', **getResp())

###############################################################################
## UDP communication ##########################################################
###############################################################################


@app.route('/synapse/ping', methods=['GET'])
def synapsePing():
    ''' tells p2p script we're up and running '''
    # if start.wallet is None:
    #    return 'fail', 400
    # if start.synergy is not None:
    #    return 'ready', 200
    # return 'ok', 200
    # if start.synergy is None:
    #    return 'fail', 201
    return 'ready', 200


@app.route('/synapse/ports', methods=['GET'])
def synapsePorts():
    ''' receives data from udp relay '''
    return str(start.peer.gatherChannels())


@app.route('/synapse/stream')
def synapseStream():
    ''' here we listen for messages from the synergy engine '''

    def event_stream():
        while True:
            message = start.udpQueue.get()
            if isinstance(message, Envelope):
                yield 'data:' + message.toJson + '\n\n'

    return Response(
        stream_with_context(event_stream()),
        content_type='text/event-stream')


@app.route('/synapse/message', methods=['POST'])
def synapseMessage():
    ''' receives data from udp relay '''
    data = request.data
    remoteIp = request.headers.get('remoteIp')
    # remotePort = int(request.headers.get('remotePort')) #not needed at this time
    # localPort = int(request.headers.get('localPort'))
    if any(v is None for v in [remoteIp, data]):
        return 'fail', 400
    start.synergy.passMessage(remoteIp, message=data)
    return 'ok', 200


###############################################################################
## Entry ######################################################################
###############################################################################


if __name__ == '__main__':
    # if False:
    #    spoofStreamer()

    # serve(app, host='0.0.0.0', port=config.get()['port'])
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
