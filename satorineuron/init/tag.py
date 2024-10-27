from typing import Union


class Version:
    def __init__(self, string: str = '0.0.0'):
        string = Version.validate(string)
        self.string = string
        self.version = [int(x) for x in string.split('.')]
        self.major = self.version[0]
        self.minor = self.version[1]
        self.patch = self.version[2]

    @staticmethod
    def validate(string: str) -> str:
        if not isinstance(string, str):
            return '0.0.0'
        if string.count('.') < 2:
            return '0.0.0'
        if len(string) < 5:
            return '0.0.0'
        return string

    def __eq__(self, other):
        if isinstance(other, Version):
            return self.version == other.version
        return self.version == [int(x) for x in other.split('.')]

    def __lt__(self, other):
        if isinstance(other, Version):
            return self.version < other.version
        return self.version < [int(x) for x in other.split('.')]

    def __le__(self, other):
        return self == other or self < other

    def __gt__(self, other):
        return not self <= other  # noqa

    def __ge__(self, other):
        return not self < other  # noqa

    def __repr__(self):
        return self.string

    def __str__(self):
        return self.string


class LatestTag:
    def __init__(self, version: Union[Version, None] = None, serverURL: str = 'https://stage.satorinet.io'):
        self.priorTag = ''
        self.tag = ''
        self.version = version
        self.serverURL = serverURL

    @property
    def isNew(self):
        return self.priorTag != self.tag

    def get(self) -> str:
        try:
            import requests
            r = requests.get(
                'https://api.github.com/repos/SatoriNetwork/Neuron/tags')
            if r.status_code == 200:
                return r.json()[0].get('name')
        except Exception as _:
            pass
        return ''

    def getTagFromWeb(self) -> str:
        try:
            import requests
            r = requests.get(self.serverURL + '/version/neuron')
            if r.status_code == 200:
                return r.text
        except Exception as _:
            pass
        return ''

    def cycle(self) -> str:
        newTag = self.get()
        priorTag = self.priorTag
        if newTag != self.tag:
            self.priorTag = self.tag
            self.tag = newTag
        return priorTag

    def getVersion(self) -> str:
        resp = self.get()
        if resp == '':
            resp = self.getTagFromWeb()
        if resp == '':
            return self.version
        newTag = Version(self.get())
        priorTag = self.priorTag
        if newTag != self.tag:
            self.priorTag = self.tag
            self.tag = newTag
        return priorTag

    def mustUpdate(self) -> bool:
        self.getVersion()
        return (
            self.version.major < self.tag.major or
            self.version.minor < self.tag.minor)
