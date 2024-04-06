import os
from functools import partial
from .config import root, read, write, get, put, env, var, add


# root = partial(root, os.path.abspath(__file__)) # no, put configs outside lib:
root = partial(root, os.path.abspath(__file__), '../')
read = partial(read, root=root)
write = partial(write, root=root)
get = partial(get, root=root)
put = partial(put, root=root)
add = partial(add, root=root)
env = partial(env, get=get, root=root)


def verbose(name: str):
    if name == 'flaskPort':
        return 'user interface port'
    if name == 'nodejsPort':
        return 'streamr light client port'
    if name == 'dataPath':
        return 'absolute data path'
    if name == 'modelPath':
        return 'absolute model path'
    if name == 'walletPath':
        return 'absolute wallet path'
    if name == 'defaultSource':
        return 'default data streams source'
    if name == 'electrumxServers':
        return 'electrumx servers'


def manifest():
    return get('manifest') or {}


def modify(data: dict):
    ''' modifies the config yaml without erasing comments (unlike put) '''

    def extractKey(line: str):
        return line.replace('#', '').strip().split(':')[0]

    replacement = []
    for line in read():
        key = extractKey(line)
        if key in data.keys():
            replacement.append(f'{key}: {data[key]}\n')
        else:
            replacement.append(line)
    write(lines=replacement)


def flaskPort():
    return get().get(verbose('flaskPort'), '24601')


def nodejsPort():
    return get().get(verbose('nodejsPort'), '24686')


def dataPath(filename=None):
    ''' data path takes presidence over relative data path if both exist '''
    if filename:
        return os.path.join(path(of='data'), filename)
    return path(of='data')


def modelPath(filename=None):
    ''' model path takes presidence over relative model path if both exist '''
    if filename:
        return os.path.join(path(of='models'), filename)
    return path(of='models')


def walletPath(filename=None):
    ''' wallet path takes presidence over relative model path if both exist '''
    if filename:
        return os.path.join(path(of='wallet'), filename)
    return path(of='wallet')


def defaultSource():
    return get().get(verbose('defaultSource'), 'streamr')


def electrumxServers():
    return get().get(verbose('electrumxServers'), [
        'rvn4lyfe.com:50002', 'moontree.com:50002',
        'ravennode-01.beep.pw:50002', 'ravennode-02.beep.pw:50002',  # HyperPeek
        'electrum-rvn.dnsalias.net:50002'])


def path(of='data'):
    ''' used to get the data or model path '''
    return get().get(verbose(f'{of}Path'), root(f'./{of}'))
