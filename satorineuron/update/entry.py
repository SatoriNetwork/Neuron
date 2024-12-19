from satorineuron.update import config
from satorineuron.update import pull
from satorineuron.update import hashes

def update():

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
        if pullFromGithub():
            return True
        if config.pullAllowedByTime():
            folderHashes = hashes.getFolders()
            if pullFromServer():
                return True
            folderHashes = hashes.getFolders()
            return detectSuccess()
