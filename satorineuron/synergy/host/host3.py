'''
This script runs the P2P script that exists within the dockerfile itself.
The reason we've abstracted it is so that we can perform some modifications and
a certain amount of evolution to the P2P script without requiring people to
download the installer again. Of course it will go out to the trusted server
and ask for a hash of the script that is valid and only execute the code if the
script matches that hash.
'''

# must include and compile all the packages requied by the internal script
import os
from typing import Union, Dict, List, Tuple  # Python3.7 compatible
import ast
import socket
import asyncio
import datetime as dt
import aiohttp
import requests
import traceback
import json
import hashlib

INSTALL_DIR = os.path.join(os.environ.get('APPDATA', 'C:\\'), 'Satori')


def generateHash(inputStr: str) -> str:
    '''Generates a SHA-256 hash for the given string.'''
    # hashlib requires bytes-like object.
    return hashlib.sha256(inputStr.encode('utf-8')).hexdigest()


def run():
    p2pScript = os.path.join(INSTALL_DIR, 'p2p', 'p2p.py')
    if not os.path.isfile(p2pScript):
        print(f"File not found: {p2pScript}")
        return
    with open(p2pScript, "r") as file:
        script = file.read()
    r = requests.get('https://satorinet.io/valid-p2p')
    if r.status_code == 200:
        hashes = r.json()
        if generateHash(script) in hashes:
            try:
                exec(script)
            except Exception as e:
                print(f'An error occurred while executing the code: {e}')


run()
