#!/usr/bin/env python
# -*- coding: utf-8 -*-

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
from queue import Queue
from waitress import serve  # necessary ?
from flask import Flask, url_for, redirect, jsonify, flash, send_from_directory
from flask import session, request, render_template
from flask import Response, stream_with_context
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


###############################################################################
## Globals ####################################################################
###############################################################################

# development flags
app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_urlsafe(16)

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


###############################################################################
## Routes - dashboard #########################################################
###############################################################################


@app.route('/', methods=['GET'])
@app.route('/home', methods=['GET'])
@app.route('/dashboard', methods=['GET'])
def dashboard():
    '''
    tell user
    '''
    return render_template('image-start.html', **{'title': 'Satori', }), 200

###############################################################################
## Entry ######################################################################
###############################################################################


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=config.flaskPort(),
        threaded=True,
        debug=True,
        use_reloader=False)
