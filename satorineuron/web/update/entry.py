import requests
from . import config
from . import pull
from . import hashes

def update():

    def shouldPullFromGithub() -> bool:
        r = requests.get('https://stage.satorinet.io/api/v1/update/github/required')
        if r.status_code == 200:
            if r.text.lower() == 'true':
                return True
        return False

    def shouldPullFromServer() -> bool:
        r = requests.get('https://stage.satorinet.io/api/v1/update/code/required')
        if r.status_code == 200:
            if r.text.lower() == 'true':
                return True
        return False

    def pullFromGithub():
        matched = True
        for k, v in folderHashes.items():
            if targetHashes.get(k) != v:
                matched = False
                knownSuccess = pull.validateGithub(*pull.fromGithub(k))
                if knownSuccess:
                    matched = True
        return matched

    def pullFromServer():
        matched = True
        for k, v in folderHashes.items():
            if targetHashes.get(k) != v:
                matched = False
                pull.fromServer(k)
                config.putTime() # don't pull from server too often
        return matched

    def detectSuccess():
        for k, v in folderHashes.items():
            if targetHashes.get(k) != v:
                return False
        return True

    if config.pullAllowedByConfig():
        targetHashes = hashes.getTargets()
        folderHashes = hashes.getFolders()
        if shouldPullFromGithub() and pullFromGithub():
            return True
        if config.pullAllowedByTime():
            folderHashes = hashes.getFolders()
            if shouldPullFromServer() and pullFromServer():
                return True
            folderHashes = hashes.getFolders()
            return detectSuccess()
