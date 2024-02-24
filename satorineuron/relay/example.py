'''
The Satori Node is equipped with a built-in relay engine, made to easily relay
primary (raw, as oppoised to predictive) data streams. Relay entries can be 
added on the UI of the Satori Node. 

Alternatively, one can relay through the API. This example shows how to do so.
'''
import time
import json
import requests

HTTP_TIMEOUT = 300


class RelayStreamExample:
    def __init__(
        self,
        name,
        uri,
        headers=None,
        payload=None,
        cadence=60*60,
        source='satori',
        target='',
        hook=None,
        datatype=None,
        description=None,
        tags=None,
        offset=None,
        url=None,
    ):
        self.source = source
        self.name = name
        self.target = target
        self.uri = uri
        self.headers = headers
        self.payload = payload
        self.cadence = cadence
        self.hook = hook
        self.datatype = datatype
        self.description = description
        self.tags = tags
        self.offset = offset
        self.url = url

    def call(self):
        ''' calls API and relays data to Satori Node '''
        if self.payload is None:
            response = requests.get(self.uri, headers=self.headers, timeout=HTTP_TIMEOUT)
        else:
            response = requests.post(
                self.uri, headers=self.headers, json=self.payload, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        if self.hook is not None:
            return self.hook(response.text)
        else:
            if self.target == None:
                return response.text
            # assumes the API returns a JSON object
            return response.json().get(self.target, None)

    def passToNode(self, value):
        ''' once the data is retrieved, pass it to the Satori Node '''
        return requests.post(
            'http://localhost:24601/relay',
            timeout=HTTP_TIMEOUT,
            json=json.dumps({
                # required
                'source': self.source,
                'name': self.name,
                'target': self.target,
                'data': value,
                # optional
                'datatype': self.datatype,
                'description': self.description,
                'tags': self.tags,
                'cadence': self.cadence,
                'offset': self.offset,
                'url': self.url}))

    def runForever(self):
        while True:
            value = self.call()
            if value is None:
                print('No data returned from API')
            else:
                if self.passToNode(value).status_code == 200:
                    print('Relay successful')
                else:
                    print('Relay failed')
            time.sleep(self.cadence)


def postRequestHook(response: str):
    ''' example hook to extract temperature from OpenMeteo API '''
    return json.loads(response).get('current_weather', {}).get('windspeed')


if __name__ == '__main__':
    relay = RelayStreamExample(
        name='WeatherBerlin',
        uri='https://api.open-meteo.com/v1/forecast?latitude=52.52&longitude=13.41&current_weather=true',
        headers=None,
        payload=None,
        cadence=60*60,
        source='satori',
        target='windspeed',
        hook=postRequestHook,
        datatype='float',
        description='Weather data from OpenMete',
        tags='weather,openmeteo,berlin,germany,windspeed',
        offset=None,
        url='https://api.open-meteo.com/')
    relay.runForever()
