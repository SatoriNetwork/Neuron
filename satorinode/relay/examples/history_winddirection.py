class GetHistory(object):
    '''
    supplies the history of the data stream
    one observation at a time (getNext, isDone)
    or all at once (getAll)
    example 3 winddirection last 10 days every 10 minutes
    '''

    def __init__(self, *args, **kwargs):
        super(GetHistory, self).__init__(*args, **kwargs)
        import requests
        self.response = requests.get(
            url='https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&past_days=10&hourly=winddirection_10m')
        self.times = self.response.json().get('hourly', {}).get('time', [])
        self.values = self.response.json().get(
            'hourly', {}).get('winddirection_10m', [])

    def getAll(self, *args, **kwargs):
        ''' 
        if getAll returns a list or pandas DataFrame
        then getNext is never called
        '''
        def conformTime(s: str):
            import datetime as dt
            return (
                dt.datetime
                .fromisoformat(s)
                .astimezone(dt.timezone.utc)
                .strftime('%Y-%m-%d %H:%M:%S.%f'))

        import pandas as pd
        assert (len(self.times) == len(self.values))
        return pd.DataFrame(
            data=self.values,
            columns=['windDirection'],
            index=[conformTime(s) for s in self.times])

    def getNext(self, *args, **kwargs):
        '''
        should return a value or a list of two values, 
        the first being the time in UTC as a string of the observation,
        the second being the observation value
        '''
        return None

    def isDone(self, *args, **kwargs):
        ''' returns true when there are no more observations to supply '''
        return True


"""
WeatherBerlin.windDirection
https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true

def postRequestHook(response: 'response.Request'): 
    return response.json().get('current_weather', {}).get('winddirection')
"""
