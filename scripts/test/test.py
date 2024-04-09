# from concurrent.futures import ThreadPoolExecutor
# from email.mime.text import MIMEText
# import argparse
# import asyncio
# import collections
# import contextlib
# import datetime
# import email.mime.multipart
# import email.mime.text
# import enum
# import functools
# import hashlib
# import http
# import http.client
# import http.server
# import itertools
# import json
# import logging
# import logging.handlers
# import logging.handlers
# import math
# import multiprocessing
# import multiprocessing.pool
# import os
# import pathlib
# import pickle
# import queue
# import random
# import re
# import select
# import signal
# import socket
# import sqlite3
# import sqlite3
# import sqlite3.dbapi2
# import subprocess
# import sys
# import threading
# import tkinter.ttk
# import unittest
# import urllib
# import urllib.error
# import urllib.parse
# import urllib.request
# import xml
# import xml.etree.ElementTree as ET

# import importlib
#
# def import_module(module_name):
#    try:
#        module = importlib.import_module(module_name)
#        globals()[module_name] = module
#        print(f"Imported {module_name}")
#    except ImportError as e:
#        print(f"Failed to import {module_name}: {e}")
#
# Example usage
# module_list = ["json", "os", "sys", "urllib.request"]
# for mod in module_list:
#    import_module(mod)


# attempt to import all standard library modules

import pkgutil
import importlib
import sys


def import_all_stdlib():
    # Get a list of all standard library modules
    stdlib_modules = list(sys.builtin_module_names)

    # Add all modules found by pkgutil.iter_modules, filtering by prefix to avoid third-party modules
    for importer, modname, ispkg in pkgutil.iter_modules():
        if "site-packages" not in str(importer):
            stdlib_modules.append(modname)

    # Attempt to import each module
    for module in set(stdlib_modules):  # Use set to avoid duplicates
        try:
            importlib.import_module(module)
            print(f"Imported {module}")
        except Exception as e:
            print(f"Failed to import {module}: {e}")


if __name__ == "__main__":
    import_all_stdlib()
