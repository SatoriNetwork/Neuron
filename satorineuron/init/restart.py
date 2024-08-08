import os
import sys


def restartLocalSatori():
    '''Restarts the current program, only works on OS with proper shell support.'''
    python = sys.executable
    os.execl(python, python, *sys.argv)
