import uuid


def generateUUID(data: dict) -> uuid:
    namespace = uuid.NAMESPACE_DNS
    combined = ':'.join(str(v) for v in data.values())
    return uuid.uuid5(namespace, combined)


# Usage
# stream_identifier = {
#     "source": "OpenWeatherMap API",
#     "author": "034f57b8421b40575149d2be03d4d27bfc7e345b5ef8f478995ae2970f9a3e4e9d",
#     "stream": "Tokyo_pressure",
#     "target": "result.pressure",
# }
# result = generate_uuid(stream_identifier)
# print(result)
# '3f6d8b21-eb66-57c5-8315-3094c0fb7739'
