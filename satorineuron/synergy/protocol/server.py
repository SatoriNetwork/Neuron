''' contains the protocol to communicate with the synergy server '''
from typing import Union
import json


class SynergyProtocol:
    def __init__(
        self,
        # we don't have to specify stream here.
        # we do that once we connect to them.
        # source: str,  # provided by subscriber
        # stream: str,  # provided by subscriber
        # target: str,  # provided by subscriber
        author: str,  # provided by subscriber
        subscriber: str,  # provided by subscriber
        subscriberPort: str,  # provided by subscriber
        subscriberIp: Union[str, None] = None,  # provided by server
        authorPort: Union[str, None] = None,  # provided by author
        authorIp: Union[str, None] = None,  # provided by server
    ):
        self.author = author
        self.subscriber = subscriber
        self.subscriberPort = subscriberPort
        self.subscriberIp = subscriberIp
        self.authorPort = authorPort
        self.authorIp = authorIp

    @staticmethod
    def fromJson(jsonStr: str) -> 'SynergyProtocol':
        return SynergyProtocol(**json.loads(jsonStr))

    def toDict(self):
        return {
            self.author: self.author,
            self.subscriber: self.subscriber,
            self.subscriberPort: self.subscriberPort,
            self.subscriberIp: self.subscriberIp,
            self.authorPort: self.authorPort,
            self.authorIp: self.authorIp}

    def toJson(self):
        return json.dumps(self.toDict())
