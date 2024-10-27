import sys, os
import time
import subprocess


def startSatori():
    return subprocess.Popen([sys.executable, '/Satori/Neuron/satorineuron/web/satori.py'])


def monitorAndRestartSatori():
    while True:
        print("Starting Satori...")
        process = startSatori()
        while True:
            try:
                return_code = process.poll()
                if return_code is not None:
                    print(f'Satori exited with code {return_code}.')
                    # break
                    return return_code
                time.sleep(1)
            except KeyboardInterrupt:
                print("Shutting down monitor...")
                process.terminate()
                process.wait()
                return 0


if __name__ == "__main__":
    return_code = monitorAndRestartSatori()
    os._exit(return_code)
