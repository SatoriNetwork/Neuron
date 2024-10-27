import os
import sys
import time
import subprocess

lastPull = 0


def startSatori():
    return subprocess.Popen([sys.executable, 'satori.py'])


def pullSatori():
    process = subprocess.Popen(['/bin/bash', 'pull.sh'])
    process.wait()
    global lastPull
    lastPull = time.time()


def isProdMode() -> bool:
    return os.environ.get('ENV', os.environ.get('SATORI_RUN_MODE', 'dev')) == 'prod'


def monitorAndRestartSatori():
    while True:
        print("Starting Satori...")
        # actually it seems we can interrupt with ctrl+c either way
        # isProd = isProdMode()
        if time.time() - lastPull > 60*60:
            pullSatori()
        process = startSatori()
        # if isProd:
        process.wait()
        # else: #(must be able to interrupt with ctrl+c)
        #    while True:
        #        try:
        #            return_code = process.poll()
        #            if return_code is not None:
        #                print(f'Satori exited with code {return_code}.')
        #                break
        #            time.sleep(1)
        #        except KeyboardInterrupt:
        #            print("Shutting down monitor...")
        #            process.terminate()
        #            process.wait()
        #            return


if __name__ == "__main__":
    monitorAndRestartSatori()
