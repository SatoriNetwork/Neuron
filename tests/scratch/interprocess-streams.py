'''
this is to make sure our design for interprocess communication will work
we want to have multiple threads modifying and reading the same objects...
if this works well we could perhaps replace the loops with listeners and
behavior subjects as streams.
'''

import threading
import time
import datetime as dt
from reactivex.subject import BehaviorSubject

class DataManager:
    
    def __init__(self):
        self.updates = {}
        self.availableInputs = [0,1,2,3,4,5,6,7,8,9]
        self.helperTextCounter = 0
        self.listeners = []
        
    def runSubscriber(self, models):
        self.helperTextCounter += 1 # only one stream updates 
        if self.helperTextCounter not in self.availableInputs:
            self.helperTextCounter = 1
        self.updates[self.helperTextCounter] = str(dt.datetime.utcnow().second)
        for model in models:
            if self.helperTextCounter in model.inputs:
                model.inputsUpdated.on_next(True)

    def runPublisher(self, models):
        def publish(modelName, prediction):
            #model.predictionUpdated.on_next(False)
            print(f'Publishing: {modelName}: {prediction}')
            
        for model in models:
            print(f'pub {model.targetKey}')
            self.listeners.append(model.predictionUpdated.subscribe(lambda x: publish(*x) if x else None))
    
    def runScholar(self, models):
        newInput = self.availableInputs[-1] + 1
        self.availableInputs.append(newInput)
        for model in models:
            model.newAvailableInput.on_next(newInput)
            print(f'runScholar - {model.name()}: {model.inputs}')

                
class ModelManager:
    
    def __init__(self, name, inputs):
        self.targetKey = name
        self.inputs = [1,2,3]
        self.model = None
        self.prediction = None
        self.updates = {}
        # flags
        self.modelUpdated = BehaviorSubject(False)
        self.inputsUpdated = BehaviorSubject(False)
        self.predictionUpdated = BehaviorSubject(False)
        self.newAvailableInput = BehaviorSubject(None)

    def name(self): 
        return self.targetKey

    def runPredictor(self, data):
        def makePrediction():
            self.prediction = str(dt.datetime.utcnow().second)
            self.predictionUpdated.on_next([self.targetKey, self.prediction])
            for i in self.inputs:
                self.updates[i] = data.updates.get(i)
            print(f'{self.targetKey} using: {self.model} with: {self.updates} prediction: {self.prediction}')
        
        def makePredictionFromNewModel():
            self.modelUpdated.on_next(False)
            makePrediction()
        
        def makePredictionFromNewInputs():
            self.inputsUpdated.on_next(False)
            makePrediction()
                
        self.modelUpdated.subscribe(lambda x: makePredictionFromNewModel() if x and self.model != None else None)
        self.inputsUpdated.subscribe(lambda x: makePredictionFromNewInputs() if x and self.model != None else None)
        
    def runExplorer(self):
        
        def explore(x):
            self.inputs.append(x)
            self.model = str(dt.datetime.utcnow())
            print(f'{self.targetKey} runExplorer')
            self.newAvailableInput.on_next(None)
            self.modelUpdated.on_next(True)
        
        self.newAvailableInput.subscribe(lambda x: explore(x) if x is not None else None)

    
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
            while True:
                time.sleep(.1)
                self.data.runSubscriber(self.models)

        def publisher():
            ''' loop for data '''
            self.data.runPublisher(self.models)

        def scholar():
            ''' loop for data '''
            while True:
                time.sleep(1)
                self.data.runScholar(self.models)

        def predictor(model:ModelManager):
            ''' loop for producing predictions '''
            model.runPredictor(self.data)

        def explorer(model:ModelManager):
            ''' loop for producing models '''
            model.runExplorer()

        # non looping functions don't need to be threads... 
        publisher()
        threads = {}
        threads['subscriber'] = threading.Thread(target=subscriber, daemon=True)
        #threads['publisher'] = threading.Thread(target=publisher, daemon=True)
        threads['scholar'] = threading.Thread(target=scholar, daemon=True)
        #predictions = {}
        #scores = {}
        #inputs = {}
        for model in self.models:
            predictor(model)
            explorer(model)
            #threads[f'{model.targetKey}.predictor'] = threading.Thread(target=predictor, args=[model], daemon=True)
            #threads[f'{model.targetKey}.explorer'] = threading.Thread(target=explorer, args=[model], daemon=True)
            #predictions[model.targetKey] = ''
            #scores[model.targetKey] = ''
            #inputs[model.targetKey] = []

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