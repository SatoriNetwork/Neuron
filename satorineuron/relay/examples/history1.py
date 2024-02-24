HTTP_TIMEOUT = 300


class GetHistory(object):
    '''example 1'''

    def __init__(self, *args, **kwargs):
        super(GetHistory, self).__init__(*args, **kwargs)
        import requests
        self.i = 0
        self.value = (
            requests.get(url='http://something.com',timeout=HTTP_TIMEOUT).text
            .split('body')[1]
            .replace('<', '').replace('>', '').replace('/', ''))

    def getAll(self, *args, **kwargs):
        return None

    def getNext(self, *args, **kwargs):
        self.i += 1
        print(self.value)
        return self.value

    def isDone(self, *args, **kwargs):
        return self.i > 3


"""
something
http://something.com

def postRequestHook(text: str):
    return (
        text
        .split('body')[1]
        .replace('<', '').replace('>', '').replace('/', ''))
    
class GetHistory(object):
    '''example 1'''
    def __init__(self, *args, **kwargs):
        super(GetHistory, self).__init__(*args, **kwargs)
        import requests
        self.i = 0
        self.value = (
            requests.get(url='http://something.com').text
            .split('body')[1]
            .replace('<', '').replace('>', '').replace('/', ''))
    def getAll(self, *args, **kwargs):
        return None
    def getNext(self, *args, **kwargs):
        self.i += 1
        print(self.value)
        return self.value
    def isDone(self, *args, **kwargs):
        return self.i > 3
"""
