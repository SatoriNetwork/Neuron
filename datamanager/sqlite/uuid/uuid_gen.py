import uuid

def generate_uuid(author: str, stream: str) -> uuid:
    namespace = uuid.NAMESPACE_DNS
    combined = f"{author}:{stream}"
    return uuid.uuid5(namespace, combined)

# Usage
# author = "03616262b0241e62f2971b59bb4685485a632c16cc6acae34449910781fd7057c2"
# stream = "ICE.USD.10mins_p"
# result = generate_uuid(author, stream)
# print(result)