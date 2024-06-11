from enum import Enum


class ConnectionTo(Enum):
    electrumx = 1
    central = 2
    pubsub = 3
    synergy = 4
    p2p = 5
