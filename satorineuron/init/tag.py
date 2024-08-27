class LatestTag:
    def __init__(self):
        self.priorTag = ''
        self.tag = ''

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

    def cycle(self) -> str:
        newTag = self.get()
        priorTag = self.priorTag
        if newTag != self.tag:
            self.priorTag = self.tag
            self.tag = newTag
        return priorTag
