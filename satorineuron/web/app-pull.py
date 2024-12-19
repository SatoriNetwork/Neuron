import os
import sys
import time
import subprocess
from satorineuron.update import update


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
                return_code = process.poll()
                if return_code is not None:
                    print(f'Satori exited with code {return_code}.')
                    if return_code == 2:  # just restart satori app
                        break
                    return return_code  # 0 shutdown, 1 restart container, err
                time.sleep(1)
            except KeyboardInterrupt:
                print('Shutting down monitor...')
                process.terminate()
                process.wait()
                return 0


if __name__ == '__main__':
    return_code = monitorAndRestartSatori()
    os._exit(return_code)
