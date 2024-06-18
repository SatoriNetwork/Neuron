class GetHistoryTemplate(object):
    '''gets the history of this dataset one observation at a time using the getNext method'''

    def __init__(self, *args, **kwargs):
        pass

    def getNext(self, *args, **kwargs):
        '''
        should return a value or a list of two values,
        the first being the time in UTC as a string of the observation,
        the second being the observation value.
        '''
        return None

    def isDone(self, *args, **kwargs):
        return None

    def getAll(self, *args, **kwargs):
        ''' 
        if getAll returns a list or pandas DataFrame then getNext is not called.
        should return a dataframe with the time in UTC as the index:
                                        target
            2023-02-24 23:42:55.598905    16.1
            2023-02-25 14:30:33.739717    16.2
        '''
        return None

    @staticmethod
    def historyTemplate():
        return """class GetHistory(object):
  '''supplies the history of the data stream one observation at a time (getNext, isDone) or all at once (getAll)'''
  def __init__(self, *args, **kwargs):
    pass
  def getNext(self, *args, **kwargs):
    '''should return a value or a list of two values, the first being the time in UTC as a string of the observation,the second being the observation value'''
    return ''
  def isDone(self, *args, **kwargs):
    '''returns true when there are no more observations to supply'''
    return ''
  def getAll(self, *args, **kwargs):
    ''' if getAll returns a list or pandas DataFrame then getNext is never called '''
    return None
"""


class GetHistory(GetHistoryTemplate):
    '''supplies the history of the data stream one observation at a time (getNext, isDone) or all at once (getAll)'''

    def __init__(self, *args, **kwargs):
        super(GetHistoryTemplate, self).__init__(*args, **kwargs)
        raise Exception('unimplemented')
