import logging
logging.basicConfig(level=logging.INFO)

def getTargets():
    import requests
    response = requests.get('https://stage.satorinet.io/codehashes')
    try:
        return response.json()
    except Exception as e:
        logging.debug(e)
        return {'neuron': '','engine': '','wallet': '','synapse': '','lib': ''}


def hashFolder(folderPath:str, exclude:list[str]=None):
    import re
    import os
    import hashlib
    exclude = exclude or []
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
        #for dir_name in sorted(dirs):
        #    if dir_name in exclude:
        #        logging.debug(f'skipping {dir_name}')
        #        continue
        #    logging.debug(f'dir_name {dir_name}')
        #    hasher.update(dir_name.encode('utf-8'))
        for file_name in sorted(files):
            logging.debug(f'filename {file_name}')
            file_path = os.path.join(root, file_name)
            hasher.update(file_name.encode('utf-8'))
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):  # Read in chunks to handle large files
                    hasher.update(chunk)
    return hasher.hexdigest()



def getFolders() -> dict[str, str]:
    return {
        'neuron': hashFolder('/Satori/Neuron/satorineuron', [r".*__pycache__$", '/Satori/Neuron/satorineuron/web/static/download']),
        'engine': hashFolder('/Satori/Engine/satoriengine', [r".*__pycache__$"]),
        #'Wallet': hashFolder('/Satori/Wallet/satoriwallet', [r".*__pycache__$"]),
        #'Synapse': hashFolder('/Satori/Synapse/satorisynapse', [r".*__pycache__$"]),
        'lib': hashFolder('/Satori/Lib/satorilib', [r".*__pycache__$"])}
