from satorilib.concepts import StreamId
import pandas as pd


def processRelayCsv(start: 'StartupDag'):
    # from satorineuron.init.start import getStart
    # start = getStart()
    df = pd.read_csv('/Satori/Neuron/uploaded/datastreams.csv')
    statuses = []
    for _, row in df.iterrows():
        # msg, status = _acceptRelaySubmissionMock(start, data=row.to_dict())
        msg, status = acceptRelaySubmission(start, data=row.to_dict())
        statuses.append(status)
        start.workingUpdates.on_next(
            f"{row['stream']}{row['target']} - {'success' if status == 200 else msg}")
    failures = [str(i) for i, s in enumerate(statuses) if s != 200]
    if len(failures) == 0:
        return 'all succeeded', 200
    elif len(failures) == len(statuses):
        return 'all failed', 500
    return f'rows {",".join(failures)} failed', 200


def _acceptRelaySubmissionMock(start: 'StartupDag', data: dict):
    import time
    time.sleep(5)
    return 'Success: ', 200


def acceptRelaySubmission(start: 'StartupDag', data: dict):
    if not start.relayValidation.valid_relay(data):
        return 'Invalid payload. here is an example: {"source": "satori", "name": "nameOfSomeAPI", "target": "optional", "data": 420}', 400
    if not start.relayValidation.stream_claimed(
        name=data.get('name'),
        target=data.get('target')
    ):
        save = start.relayValidation.register_stream(
            data=data)
        if save == False:
            return 'Unable to register stream with server', 500
        # get pubkey, recreate connection...
        start.checkin()
        start.pubsubConnect()
    # ...pass data onto pubsub
    start.pubsub.publish(
        topic=StreamId(
            source=data.get('source', 'satori'),
            author=start.wallet.publicKey,
            stream=data.get('name'),
            target=data.get('target')).topic(),
        data=data.get('data'))
    return 'Success: ', 200
