from satorilib import logging
from typing import Callable
import requests
from satorilib import logging
from satorilib.utils import colored
from satorirendezvous.client.structs.message import FromServerMessage
from satorirendezvous.example.client.structs.protocol import ToServerSubscribeProtocol as ToServerProtocol


class RendezvousByRest():
    ''' conn for server, using signature and key for identity  '''

    def __init__(
        self,
        signature: str,
        signed: str,
        host: str,
        timed: bool = True,
        onMessage: Callable = None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.msgId = 0
        self.rendezvousServer = host
        self.timed = timed
        self.listen = True
        self.onMessage = onMessage or self.display
        self.inbox = []
        self.outbox = {}
        self.signature = signature
        self.signed = signed
        self.checkin()

    def display(self, msg, addr=None):
        logging.info(f'from: {addr}, {msg}', print=True)

    def send(self, cmd: str, msgs: list[str] = None):
        ''' compiles a payload including msgId, updates outbox, and sends '''
        def generatePayload():
            if not ToServerProtocol.isValidCommand(cmd):
                logging.error('command not valid', cmd, print=True)
                return
            try:
                print('msgs', msgs)
                print('type(msgs)', type(msgs))
                payload = ToServerProtocol.compile(cmd, *[
                    x for x in [str(self.msgId), *(msgs or [])]
                    if isinstance(x, int) or (x is not None and len(x) > 0)])
                return payload
            except Exception as e:
                logging.warning('err w/ payload', e, cmd, self.msgId, msgs)
                return None

        def sendPayload(payload: str = None):
            self.msgId += 1
            self.outbox[self.msgId] = payload
            logging.debug('Rendezvous payload: ', payload, print='teal')
            response = requests.post(self.rendezvousServer, data=payload)
            logging.debug('Rendezvous response: ', response, print='blue')
            if response.status_code != 200 or not response.text.startswith('{"response": '):
                logging.warning('bad response', response, payload)
            else:
                logging.debug('good response', response)
            logging.debug('response.json()', response.json(), print='blue')
            # response.json() {'response': "RendezvousClient(('97.117.28.178', 4431), 0)"}
            # why is it giving this back?

            # why do we expect multiple messages here?
            # for msg in response.json()['response']:
            #    logging.debug('good response msg:', msg)
            #    message = FromServerMessage(msg)
            #    self.inbox.append(message)
            #    self.onMessage(message)
            msg = response.json()['response']
            message = FromServerMessage(msg)
            self.inbox.append(message)
            self.onMessage(message)

        payload = generatePayload()
        if payload is not None:
            sendPayload(payload)

    def checkin(self):
        ''' authenticated checkin '''
        # self.send(f'CHECKIN|{self.msgId}|{self.signature}|{self.signed}')
        # self.send(f'SUBSCRIBE|{self.msgId}|{self.signature}|{self.signed}')
        logging.debug('checkin started', print='red')
        self.send(
            cmd=ToServerProtocol.subscribePrefix,
            msgs=[self.signature, self.signed])
