''' google api limit is 100 per 100 seconds '''

import threading
import time
import datetime as dt
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from satori import config

class Google:
    def __init__(self) -> None:
        self.connect()
        self.sent = dt.datetime.now()
        self.queue = [];
        self.thread = threading.Thread(target=self.sendEvery)
        self.thread.start()

    def connect(self):
        self.client = gspread.authorize(
            credentials=ServiceAccountCredentials.from_json_keyfile_name(
                filename=config.root('..', 'creds', 'google.json'),
                scopes=[
                    'https://spreadsheets.google.com/feeds',
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive.file',
                    'https://www.googleapis.com/auth/drive']))
        return self.client

    def advanceTime(self):
        now = dt.datetime.now()
        if (now.day != self.sent.day):
            self.connect()
        self.sent = now

    def sendEvery(self, seconds:int=6):
        while True:
            self.advanceTime()
            time.sleep(seconds)
            self.fromQueue()
            self.fromQueue()
            self.fromQueue()

    def fromQueue(self):
        if len(self.queue) > 0:
            row, col, value = self.queue[-1]
            self.queue = self.queue[:-1]
            self.toSheet(row=row, col=col, value=value)

    def toSheet(self, row, col, value):
        print(f'sending to google... {row}, {col}, {value}')
        sheet = (self.client or self.connect()).open(title='EURUSD Demo Results').sheet1
        sheet.update_cell(row=row, col=col, value=value)

    def toQueue(self, data:pd.DataFrame=None):
        for _, row in (data if data is not None else pd.DataFrame()).iterrows():
            self.cleanQueue(row['row'], row['col'])
            self.queue.append((row['row'], row['col'], str(row['value'])))

    def cleanQueue(self, row, col):
        if len(self.queue) > 0:
            cleanedQueue = []
            for (r, c, v) in self.queue:
                if row != r or col != c:
                    cleanedQueue.append((r,c,v))
            self.queue = cleanedQueue

    def send(self, model, points:int, predictions:dict, scores:dict):
        startingRow = 2
        for ix, column in enumerate(model.data.columns.tolist()):
            if column == model.id:
                row = ix + startingRow
                rows = [row]
                cols = [1]
                values = [model.id]
                for i, (_, r) in enumerate(model.data.iloc[-1*points:, [ix]].iterrows()):
                    rows.append(row)
                    cols.append(i + 2)
                    values.append(r[column])
                rows.extend([row, row])
                cols.extend([i + 3, i + 4])
                values.extend([predictions.get(column, ''), scores.get(column, '')])
        self.toQueue(data=pd.DataFrame({'row': rows,  'col': cols,  'value': values}))
