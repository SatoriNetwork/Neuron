import os 
import time
import pandas as pd
import datetime as dt
from forex_python import converter as forex

class fx:
    def compileHistory(name:str='EUR', savePath:str='../data/history', days:int=8000, cooldown:int=1, saveDuring:bool=False, now:dt.datetime=None) -> pd.DataFrame:
        ''' gets, one by one and compiles the last days of data '''
        now = now or dt.datetime.today()
        df = pd.DataFrame({})
        last = 0
        for i in range(days): 
            time.sleep(cooldown)
            date = (now - dt.timedelta(days=i)).date()
            rates = forex.get_rates(name, date)
            # try again, sometimes it doesn't give all columns???
            if len(rates.keys()) < 30 or 'USD' not in rates.keys():
                rates = forex.get_rates(name, date)
            rates['year'] = date.year
            rates['month'] = date.month
            rates['day'] = date.day
            rates['weekday'] = date.weekday()
            print(date)
            df = df.append(pd.DataFrame(rates, index=[str(date)]))
            if saveDuring and df.shape[0] == last + 1:
                df.to_csv(name)
                last = df.shape[0]
        df = df.iloc[::-1]
        df.to_csv(os.path.join(savePath,f'{name}.csv')) # most recent last
        return df

    def getCurrent(name:str='EUR', date:'dt.datetime.date'=None) -> pd.DataFrame:
        ''' returns most recent price (as of 3pm daily) '''
        date = date or dt.datetime.today().date()
        rates = forex.get_rates(name, date)
        rates['year'] = date.year
        rates['month'] = date.month
        rates['day'] = date.day
        rates['weekday'] = date.weekday()
        return pd.DataFrame(rates, index=[str(date)])