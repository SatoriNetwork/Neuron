#!/usr/bin/env python
# -*- coding: utf-8 -*-

# run with:
# sudo nohup /app/anaconda3/bin/python app.py > /dev/null 2>&1 &

import os
import secrets
import webbrowser
from flask import Flask, render_template, jsonify
from flask import send_from_directory, session, request, Response
from flask_sockets import Sockets


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
sockets = Sockets(app)

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

###############################################################################
## Socket #####################################################################
###############################################################################


@sockets.route('/websocket')
def handle_websocket(ws):
    while not ws.closed:
        message = ws.receive()
        print('received message: ' + message)
        ws.send('Data received!')

###############################################################################
## Entry ######################################################################
###############################################################################


if __name__ == '__main__':
    if not debug:
        webbrowser.open('http://127.0.0.1:24602', new=0, autoraise=True)

    from gevent import pywsgi
    from geventwebsocket.handler import WebSocketHandler
    print('24602')
    server = pywsgi.WSGIServer(
        ('0.0.0.0', 24602),
        app,
        handler_class=WebSocketHandler,
        # threaded=True,
        # use_reloader=False,
        # debug=debug
    )
    server.serve_forever()
