import sys
import time
import subprocess


def startSatori():
    return subprocess.Popen([sys.executable, 'satori.py'])


def monitorAndRestartSatori():
    while True:
        print("Starting Satori...")
        process = startSatori()
        while True:
            try:
                return_code = process.poll()
                if return_code is not None:
                    print(f'Satori exited with code {return_code}.')
                    break
                time.sleep(1)
            except KeyboardInterrupt:
                print("Shutting down monitor...")
                process.terminate()
                process.wait()
                return


if __name__ == "__main__":
    monitorAndRestartSatori()
