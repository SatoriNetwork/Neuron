#!/bin/sh
#nohup
cd /Satori/Neuron/WebRTC && python signaling_server.py &
tail -f /dev/null
