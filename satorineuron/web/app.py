import os
import sys
import time
import subprocess
from satorineuron.update import update

def loadEnvVars(envFile):
    """
    Load environment variables from a file into os.environ.
    """
    if os.path.exists(envFile):
        with open(envFile) as f:
            for line in f:
                # Skip comments and empty lines
                line = line.strip()
                if line and not line.startswith('#'):
                    key, _, value = line.partition('=')
                    os.environ[key.strip()] = value.strip()
        #print(f"Loaded environment variables from {envFile}")
    else:
        #print(f"Environment file {envFile} not found. Skipping...")
        pass

def startSatori():
    return subprocess.Popen([sys.executable, '/Satori/Neuron/satorineuron/web/satori.py'])


def isProdMode() -> bool:
    return os.environ.get('ENV', os.environ.get('SATORI_RUN_MODE', 'dev')) == 'prod'

def isNotWalletMode() -> bool:
    return os.environ.get('RUNMODE') != 'wallet'


def monitorAndRestartSatori():
    while True:
        if isProdMode() and isNotWalletMode():
            update()
        print('Starting Satori...')
        process = startSatori()
        while True:
            try:
                time.sleep(5)
                return_code = process.poll()
                if return_code is not None:
                    print(f'Satori exited with code {return_code}.')
                    if return_code == 2:  # just restart satori app
                        break
                    return return_code  # 0 shutdown, 1 restart container, err
            except KeyboardInterrupt:
                print('Shutting down monitor...')
                process.terminate()
                process.wait()
                return 0


if __name__ == '__main__':
    loadEnvVars('/Satori/Neuron/config/.env')
    return_code = monitorAndRestartSatori()
    os._exit(return_code)
