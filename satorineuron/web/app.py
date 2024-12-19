import os
import sys
import time
import subprocess

lastPull = 0

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


def pullSatori():
    process = subprocess.Popen(
        ['/bin/bash', 'pull.sh'],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    #process.wait()
    stdout, stderr = process.communicate()
    #print("STDOUT:", stdout.decode())
    #print("STDERR:", stderr.decode())
    global lastPull
    lastPull = time.time()


def isProdMode() -> bool:
    return os.environ.get('ENV', os.environ.get('SATORI_RUN_MODE', 'dev')) == 'prod'


def allowedToPull() -> bool:
    '''
    open /Satori/Neuron/config/config.yaml if it exists,
    check if the value of 'pull code updates' is true
    '''
    config_path = '/Satori/Neuron/config/config.yaml'
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith('pull code updates'):
                    return line.split(':')[1].strip().lower() == 'true'
    return True


def monitorAndRestartSatori():
    while True:
        print("Starting Satori...")
        if allowedToPull() and time.time() - lastPull > 60*60:
            pullSatori()
        else:
            print("skipped pull...")
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
                print("Shutting down monitor...")
                process.terminate()
                process.wait()
                return 0


if __name__ == "__main__":
    loadEnvVars('/Satori/Neuron/config/vars.env')
    return_code = monitorAndRestartSatori()
    os._exit(return_code)
