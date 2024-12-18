from satorineuron.code import config
from satorineuron.code import pull
from satorineuron.code import hashes

def run():
    if config.allowedToPull():
        # pull from github
        targetHashes = hashes.getTargets()
        folderHashes = hashes.getFolders()
        matched = True
        for k, v in folderHashes:
            if targetHashes.get(k) != v:
                matched = False
                pull.fromGithub(k)
                config.putTime()
        if matched:
            return True
        # pull from server
        folderHashes = hashes.getFolders()
        matched = True
        for k, v in folderHashes:
            if targetHashes.get(k) != v:
                matched = False
                pull.fromServer(k)
        if matched:
            return True
        # return
        folderHashes = hashes.getFolders()
        for k, v in folderHashes:
            if targetHashes.get(k) != v:
                return False
        return True
