import time
import threading


class RawStreamRelayEngine:
    def __init__(self):
        self.thread = None
        self.killed = False
        self.latest = {}

    def status(self):
        if self.killed:
            return 'stopping'
        if self.thread == None:
            return 'stopped'
        if self.thread.is_alive():
            return 'running'
        # should we restart the thread if it dies? we shouldn't see this:
        return 'unknown'

    def callRelay(self, stream):
        print('running', stream)

    def runForever(self):
        def cadence():
            ''' returns cadence in seconds, engine does not allow < 60 '''
            return 6
        start = int(time.time())
        while True:
            now = int(time.time())
            if self.killed:
                print('AHHHHH KILLED')
                break
            for stream in ['a', 'b', 'c']:
                if (now - start) % cadence() == 0:
                    threading.Timer(
                        cadence(),
                        self.callRelay,
                        [stream],
                    ).start()
            time.sleep(.99999)

    def run(self):
        self.thread = threading.Thread(target=self.runForever, daemon=True)
        self.thread.start()

    def kill(self):
        self.killed = True
        time.sleep(3)
        self.thread = None
        self.killed = False


x = RawStreamRelayEngine()
x.run()

x.kill()


# test
# a = Stream(name='A', cadence=5)
# b = Stream(name='B', cadence=6)
# c = Stream(name='C', cadence=7)
# x = RawStreamRelayEngine(streams=[a, b, c])
# x.runForever()
