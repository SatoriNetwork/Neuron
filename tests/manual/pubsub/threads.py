import threading


class PubSubTest(object):
    def __init__(
            self, router: 'function' = None, *args, **kwargs):
        super(PubSubTest, self).__init__(*args, **kwargs)
        self.router = router
        self.listening = True
        self.ear = self.setEar()

    def setEar(self):
        self.ear = threading.Thread(target=self.listen, daemon=True)
        self.ear.start()

    def setListening(self, listening: bool):
        self.listening = listening

    def setRouter(self, router: 'function' = None):
        self.router = router

    def listen(self):
        while True:
            self.router()


def router1():
    import time
    time.sleep(5)
    print('router1')


def router2():
    import time
    time.sleep(5)
    print('router2')


ps = PubSubTest(router=router1)
ps.setRouter(router2)
