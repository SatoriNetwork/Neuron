'''
this is to make sure our design for interprocess communication will work
we want to have multiple threads modifying and reading the same objects...
if this works well we could perhaps replace the loops with listeners and
behavior subjects as streams.
'''

import threading
import time
import datetime as dt

class DataManager:
    
    def __init__(self):
        self.updates = {}
        self.availableInputs = [0,1,2,3,4,5,6,7,8,9]
        self.helperTextCounter = 0
        
    def runSubscriber(self, models):
        self.helperTextCounter += 1 # only one stream updates 
        if self.helperTextCounter not in self.availableInputs:
            self.helperTextCounter = 1
        self.updates[self.helperTextCounter] = str(dt.datetime.utcnow().second)
        for model in models:
            if self.helperTextCounter in model.inputs:
                model.inputsUpdated = True

    def runPublisher(self, models):
        for model in models:
            if model.predictionUpdated == True:
                model.predictionUpdated = False
                print(f'Publishing: {model.name()}: {model.prediction}')

    def runScholar(self, models):
        newInput = self.availableInputs[-1] + 1
        self.availableInputs.append(newInput)
        for model in models:
            model.newAvailableInputs.append(newInput)
            print(f'runScholar - {model.name()}: {model.inputs}')

                
class ModelManager:
    
    def __init__(self, name, inputs):
        self.targetKey = name
        self.inputs = [1,2,3]
        self.model = None
        self.prediction = None
        self.updates = {}
        # flags
        self.modelUpdated = False
        self.inputsUpdated = False
        self.predictionUpdated = False
        self.newAvailableInputs = []

    def name(self): 
        return self.targetKey

    def runPredictor(self, data):
        # this would avoid two things writing at the same time maybe? replace flags with logic like this if its a problem.
        # all([True if data.updates[i] == self.lastUpdates[i] else False for i in self.inputs])
        # or we could have two flags - write on our own system read on the other
        if self.model != None and (self.modelUpdated or self.inputsUpdated):
            if self.modelUpdated:
                self.modelUpdated = False
            if self.inputsUpdated:
                self.inputsUpdated = False
            self.prediction = str(dt.datetime.utcnow().second)
            self.predictionUpdated = True
            for i in self.inputs:
                self.updates[i] = data.updates.get(i)
            print(f'{self.targetKey} using: {self.model} with: {self.updates} prediction: {self.prediction}')

    def runExplorer(self, data):
        if self.newAvailableInputs != []:
            self.inputs = self.inputs + self.newAvailableInputs
            self.newAvailableInputs = []
            self.model = str(dt.datetime.utcnow())
            self.modelUpdated = True
            print(f'{self.targetKey} runExplorer')

    
class Learner:

    def __init__(
        self,
        data:DataManager=None,
        model:ModelManager=None,
        models:'set(ModelManager)'=None,
    ):
        '''
        data - a DataManager for the data
        model - a ModelManager for the model
        models - a list of ModelManagers
        '''
        self.data = data
        self.models = models
        if model is not None:
            self.models = {self.models + [model]}

    def run(self):
        '''
        Main Loops - one for each model and one for the data manager.
        '''

        def subscriber():
            ''' loop for data '''

            def rest():
                x = 9
                if x == -1:
                    while True:
                        time.sleep(60*60)
                time.sleep(x)

            while True:
                #rest()
                self.data.runSubscriber(self.models)

        def publisher():
            ''' loop for data '''

            def rest():
                x = 1
                if x == -1:
                    while True:
                        time.sleep(60*60)
                time.sleep(x)

            while True:
                #rest()
                self.data.runPublisher(self.models)

        def scholar():
            ''' loop for data '''

            def rest():
                x = 30
                if x == -1:
                    while True:
                        time.sleep(60*60)
                time.sleep(x)

            while True:
                #rest()
                self.data.runScholar(self.models)

        def predictor(model:ModelManager):
            ''' loop for producing predictions '''

            def rest():
                x = 4
                if x == -1:
                    while True:
                        time.sleep(60*60)
                time.sleep(x)

            while True:
                #rest()
                model.runPredictor(self.data)

        def explorer(model:ModelManager):
            ''' loop for producing models '''
        
            def rest():
                x = 13
                if x == -1:
                    while True:
                        time.sleep(60*60)
                time.sleep(x)

            while True:
                #rest()
                model.runExplorer(self.data)

        threads = {}
        threads['subscriber'] = threading.Thread(target=subscriber, daemon=True)
        threads['publisher'] = threading.Thread(target=publisher, daemon=True)
        threads['scholar'] = threading.Thread(target=scholar, daemon=True)
        predictions = {}
        scores = {}
        inputs = {}
        for model in self.models:
            threads[f'{model.targetKey}.predictor'] = threading.Thread(target=predictor, args=[model], daemon=True)
            threads[f'{model.targetKey}.explorer'] = threading.Thread(target=explorer, args=[model], daemon=True)
            predictions[model.targetKey] = ''
            scores[model.targetKey] = ''
            inputs[model.targetKey] = []

        for thread in threads.values():
            print('starting')
            thread.start()

        while threading.active_count() > 0:
            time.sleep(0)

# python .\tests\scratch\interprocess.py
learner = Learner(
    data=DataManager(),
    models={
        ModelManager(name='A', inputs=[1,2,3]),
        ModelManager(name='B', inputs=[2,3,4]),
        ModelManager(name='C', inputs=[3,5,6])
        }
    )

learner.run()