import os
import time


def pullAllowedByConfig() -> bool:
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


def pullAllowedByTime() -> bool:
    '''
    open /Satori/Neuron/config/config.yaml if it exists,
    check if the value of 'pull code updates' is true
    '''
    path = '/Satori/Neuron/config/pulled.txt'
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                return time.time() - float(f.read()) > 60*60
        return True
    except Exception as e:
        print(e)
    return False


def putTime() -> bool:
    path = '/Satori/Neuron/config/pulled.txt'
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        f.write(str(time.time()))


def allowedToPull() -> bool:
    return pullAllowedByConfig() and pullAllowedByTime()
