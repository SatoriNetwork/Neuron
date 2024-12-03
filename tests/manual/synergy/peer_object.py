from satorineuron.synergy.domain.objects import SingleObservation
from satorisynapse import Envelope
from satorilib.utils.time import now, datetimeToTimestamp
ts = datetimeToTimestamp(now())
obs = SingleObservation(time=ts, data='data', hash='hash')
obs.isValid
msg = Envelope(ip='', vesicle=obs)
msg.toJson
env = Envelope.fromJson(msg.toJson)
env.vesicle
type(env.vesicle)
SingleObservation(**env.vesicle.toDict)
env.vesicle.toObject()
SingleObservation(**env.vesicle.toDict) == env.vesicle.toObject()
env.vesicle.toJson == obs.toJson
env.toJson == msg.toJson
exit()
