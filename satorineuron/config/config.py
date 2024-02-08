import os
import yaml


def args_to_config_path(*args, root: callable) -> str:
    ''' formats args so code isn't duplicated in every repository '''
    if not args:
        args = ['config.yaml']
    elif args[-1].endswith('.yaml') or args[-1].endswith('.yml'):
        args = list(args)
    elif len(args) == 1:
        args = [f'{args[0]}.yaml']
    else:
        variables = [arg for arg in args[:-1]]
        variables.append(f'{args[-1]}.yaml')
        args = variables
    args.insert(0, 'config')
    return root(*args)


def read(*args, path: str = None, root: callable = None):
    ''' gets configuration out of the yaml file '''
    path = path or args_to_config_path(*args, root=root)
    if os.path.exists(path):
        with open(path, mode='r') as f:
            return f.readlines()
    return []


def write(
    *args,
    lines: list,
    path: str = None,
    root: callable = None,
):
    ''' writes lines to the file at path '''
    path = path or args_to_config_path(*args, root=root)
    with open(path, mode='w') as f:
        f.writelines(lines)


def get(*args, path: str = None, root: callable = None, decrypt: callable = None):
    ''' gets configuration out of the yaml file '''
    path = path or args_to_config_path(*args, root=root)
    if os.path.exists(path):
        with open(path, mode='r') as f:
            try:
                return yaml.load(f, Loader=yaml.FullLoader) or {}
            except AttributeError:
                return yaml.load(f) or {}
            # decryption at this level not necessary
            # contents = f.read()
            # if decrypt is not None:
            #    contents = decrypt(contents)
            # try:
            #    return yaml.load(contents, Loader=yaml.FullLoader) or {}
            # except AttributeError:
            #    return yaml.load(f) or {}
    return {}


def put(
    *args,
    data: dict = None,
    path: str = None,
    root: callable = None,
) -> dict:
    ''' makes a yaml fill somewhere in config folder '''
    if data is not None:
        path = path or args_to_config_path(*args, root=root)
        with open(path, mode='w') as f:
            yaml.dump(data, f, default_flow_style=False)
    return path


def add(
    *args,
    data: dict = None,
    path: str = None,
    root: callable = None,
) -> dict:
    ''' makes a yaml fill somewhere in config folder '''
    if data is not None:
        existing = get(*args, path=path, root=root)
        path = path or args_to_config_path(*args, root=root)
        with open(path, mode='w') as f:
            yaml.dump({**existing, **data}, f, default_flow_style=False)
    return path


def root(path: str = '', *args):
    ''' produces a path string of project path plus args '''
    return os.path.abspath(
        os.path.join(os.path.dirname(os.path.dirname(path)), *args))


def env(root: callable = None, get: callable = None):
    return os.environ.get(
        f'{os.path.basename(root()).upper()}_ENV', get().get('env', None))


def var(name: str, set: str = None, default: str = None) -> str:
    if set:
        os.environ[name] = set
        return set
    if default and os.environ.get(name, None) is None:
        os.environ[name] = default
        return default
    return os.environ.get(name, None)
