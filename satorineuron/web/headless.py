#!/usr/bin/env python
# -*- coding: utf-8 -*-
# mainly used for generating unique ids for data and model paths since they must be short

# run with:
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &
from flask_cors import CORS
# from typing import Union
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
from satorineuron import VERSION, MOTTO
from satorineuron import VERSION, config
from satorineuron import logging
from satorineuron.relay import acceptRelaySubmission, processRelayCsv, generateHookFromTarget, registerDataStream
from satorineuron.web import forms
from satorineuron.init.start import StartupDag
from satorineuron.web.utils import deduceCadenceString, deduceOffsetString

logging.info(f'version: {VERSION}', print=True)

###############################################################################
## Globals ####################################################################
###############################################################################
logging.setup(level=0)
# development flags
debug = True
darkmode = False
firstRun = True
badForm = {}
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)
updateTime = 0
# updateQueue = Queue()
ENV = config.get().get('env', os.environ.get(
    'ENV', os.environ.get('SATORI_RUN_MODE', 'dev')))
# DELEGATE = config.get().get('delegate', None)
CORS(app, origins=[{
    'local': 'http://192.168.0.10:5002',
    'dev': 'http://localhost:5002',
    'test': 'https://test.satorinet.io',
    'prod': 'https://satorinet.io'}[ENV]])


###############################################################################
## Startup ####################################################################
###############################################################################
while True:
    try:
        start = StartupDag(
            env=ENV,
            urlServer={
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
            urlSynergy={
                'local': 'https://192.168.0.10:24602',
                'dev': 'https://localhost:24602',
                'test': 'https://test.satorinet.io:24602',
                'prod': 'https://synergy.satorinet.io:24602'}[ENV],
            isDebug=sys.argv[1] if len(sys.argv) > 1 else False)
        # threading.Thread(target=start.start, daemon=True).start()
        logging.info(f'environment: {ENV}', print=True)
        # if DELEGATE is not None:
        #     wallet = start.details.wallet
        #     if isinstance(wallet.rewardaddress, str) and wallet.rewardaddress not in [wallet.address, wallet.vaultaddress, DELEGATE]:
        #         start.server.stakeProxyRequest(DELEGATE)
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
    time.sleep(60*60*24)

################################################################################
### Functions ##################################################################
################################################################################
#
#


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.route('/ping', methods=['GET'])
def ping():
   from datetime import datetime
   return jsonify({'now': datetime.now().strftime("%Y-%m-%d %H:%M:%S")})


@app.route('/mining/to/address', methods=['GET'])
def mineToAddressStatus():
    return str(start.server.mineToAddressStatus()), 200


@app.route('/mine/to/address/<address>', methods=['GET'])
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


@app.route('/proxy/parent/status', methods=['GET'])
def proxyParentStatus():
    success, result = start.server.stakeProxyChildren()
    if success:
        return result, 200
    return f'Failed stakeProxyChildren: {result}', 400


@app.route('/proxy/child/charity/<address>/<id>', methods=['GET'])
def charityProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyCharity(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyCharity: {result}', 400


@app.route('/proxy/child/no_charity/<address>/<id>', methods=['GET'])
def charityNotProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyCharityNot(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyCharityNot: {result}', 400


@app.route('/proxy/child/approve/<address>/<id>', methods=['GET'])
def approveProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyApprove(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyApprove: {result}', 400


@app.route('/proxy/child/deny/<address>/<id>', methods=['GET'])
def denyProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyDeny(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyDeny: {result}', 400


@app.route('/proxy/child/remove/<address>/<id>', methods=['GET'])
def removeProxyChild(address: str, id: int):
    success, result = start.server.stakeProxyRemove(address, childId=id)
    if success:
        return result, 200
    return f'Failed stakeProxyRemove: {result}', 400


#
#
################################################################################
### Entry ######################################################################
################################################################################
#
#
if __name__ == '__main__':
    app.run(
        host='127.0.0.1',
        port=config.flaskPort(),
        threaded=True,
        debug=debug,
        use_reloader=False)
