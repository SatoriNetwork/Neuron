from aiortc import RTCPeerConnection

pc = RTCPeerConnection()

# Adding multiple STUN servers for redundancy
pc.addIceCandidate({
    'urls': ['stun:stun.l.google.com:19302']
})
