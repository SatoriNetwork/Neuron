'''
This script is baked into the installer executables.
This script runs the P2P script that exists within the dockerfile itself.
The reason we've abstracted it is so that we can perform some modifications and
a certain amount of evolution to the P2P script without requiring people to
download the installer again. Of course it will go out to the trusted server
and ask for a hash of the script that is valid and only execute the code if the
script matches that hash.

We've gone away from this pattern, namely, the satori runner starts the neuron
and using this script runs the p2p script inside the neuron which could change
but really, the p2p script should never really change, so we're baking it into 
the runner itself.
'''

# must include and compile all the packages requied by the internal script
import typing as t
import os
import json
import hashlib
import traceback
import asyncio
import socket
import requests  # ==2.31.0
import aiohttp  # ==3.8.4

# # standard library imports -
# # in case our future script needs to utilize more functionality without
# # recompiling which necesitates the need for re-download and reinstall.
import argparse
# import asyncio
import collections
import contextlib
import copy
import ctypes
import datetime as dt
import dataclasses
import email.mime.multipart
import email.mime.text
import enum
import encodings
import functools
# import hashlib
import http.client
import http.server
import importlib
import itertools
# import json
import logging
import math
import multiprocessing
import multiprocessing.pool
# import os
import pathlib
import pickle
import queue
import random
import re
import select
import signal
# import socket
import sqlite3
import subprocess
import sys
import threading
import timeit
import uuid
import urllib
import urllib.error
import urllib.parse
import urllib.request
import xml


INSTALL_DIR = os.path.join(os.environ.get('APPDATA', 'C:\\'), 'Satori')


def generateHash(inputStr: str) -> str:
    '''
    Generates a SHA-256 hash for the given string.
    hashlib requires bytes-like object.
    '''
    return hashlib.sha256(inputStr.encode('utf-8')).hexdigest()


def run(installDir: str = None):
    p2pScript = os.path.join(installDir or INSTALL_DIR, 'scripts', 'p2p.py')
    # p2pScript = 'C:\\repos\\Satori\\Neuron\\scripts\\p2p.py'
    if not os.path.isfile(p2pScript):
        print(f"File not found: {p2pScript}")
        return
    with open(p2pScript, "r") as file:
        script = file.read()
    r = requests.get('https://synergy.satorinet.io/verify/scripthash')
    if r.status_code == 200:
        hashes = r.json()
        if generateHash(script) in hashes:
            try:
                namespace = {}
                exec(script, namespace)
            except Exception as e:
                print(f'An error occurred while executing the code: {e}')
                traceback.print_exc()
    else:
        print('Satori Network unreachable, check internet connection and restart. '
              'Proceeding without p2p functionality.')


run()
