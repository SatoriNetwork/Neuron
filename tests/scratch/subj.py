import time
from reactivex import Subject

class Hello(object):
    def __init__(self):
        self.count = 0
        self.events = Subject()
    
    def doit(self):
        self.events.on_next({'source': 'hellow world', 'data': 'clicked', 'count':self.count})
        
import time
from reactivex.subject import BehaviorSubject

class Hello2(object):
    def __init__(self):
        self.count = 0
        self.events = Subject()
    
    def doit(self):
        self.count +=1
        self.events.on_next({'source': 'hellow world', 'data': 'clicked', 'count':self.count})

y = 0
def changey(thing):
    global y 
    y = thing
    
if __name__ == '__main__':
    h = Hello2()
    h.events.subscribe(lambda x: changey(x))
    
    time.sleep(1)
    h.doit()
    h.doit()
    time.sleep(1)
    h.doit()
    h.doit()
    print( '--', y)
    
    exit();
