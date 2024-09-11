#!/bin/sh
#nohup
cd /Satori/Neuron/WebRTC && python signalling_server.py &
tail -f /dev/null
