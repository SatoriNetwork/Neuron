import os
import time


def byConfig() -> bool:
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


def byTime() -> bool:
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
    if os.path.exists(path):
        with open(path, 'w') as f:
            f.write(time.time())


def allowedToPull() -> bool:
    return byConfig() and byTime()
