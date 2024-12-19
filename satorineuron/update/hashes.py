import requests
import logging
logging.basicConfig(level=logging.INFO)


def hashFolder(folderPath:str, exclude:list[str]=None, include: list[str]=None) -> str:
    import re
    import os
    import hashlib
    exclude = exclude or []
    include = include or []
    hasher = hashlib.sha256()
    for root, dirs, files in sorted(os.walk(folderPath)):
        logging.debug(f'rooft {root}')
        if root in exclude:
            logging.debug(f'skipping {root}')
            continue
        skip = False
        for path in exclude:
            if re.match(path, root):
                logging.debug(f'skipping {root}')
                skip = True
        if skip:
            logging.debug(f'skipping {root}')
            continue
        for filename in sorted(files):
            for path in include:
                if not re.match(path, filename):
                    continue
            logging.debug(f'filename {filename}')
            filepath = os.path.join(root, filename)
            hasher.update(filename.encode('utf-8'))
            with open(filepath, 'rb') as f:
                while chunk := f.read(8192):  # Read in chunks to handle large files
                    hasher.update(chunk)
    return hasher.hexdigest()


def getFolders() -> dict[str, str]:
    return {
        'lib': hashFolder('/Satori/Lib/satorilib', [r".*__pycache__$"]),
        'engine': hashFolder('/Satori/Engine/satoriengine', [r".*__pycache__$"]),
        'neuron': hashFolder('/Satori/Neuron/satorineuron', [r".*__pycache__$", '/Satori/Neuron/satorineuron/web/static/download'])}


def getTargets():
    #response = requests.get('https://stage.satorinet.io/repohashes')
    response = requests.get('http://137.184.38.160/repohashes')
    try:
        return response.json()
    except Exception as e:
        logging.debug(e)
        return {'lib': '', 'engine': '', 'neuron': ''}


def saveTargets():
    import os
    from satorilib.utils.hash import PasswordHash
    password = os.getenv('SAVE_REPOS_PASSWORD', input('Password: '))
    if password == '':
        return 'no password provided'
    response = requests.post(
        #'https://stage.satorinet.io/repohashes',
        'http://137.184.38.160/repohashes',
        headers={
            'Content-Type': 'application/json',
            'auth': PasswordHash.toString(PasswordHash.hash(password))},
        json=getFolders())
    try:
        return response.json()
    except Exception as e:
        logging.debug(e)
        return {'lib': '', 'engine': '', 'neuron': ''}
