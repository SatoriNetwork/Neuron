#!/bin/bash
# dos2unix pull.sh might require
echo "Pulling main branch in /Satori/..."
git pull #origin refs/heads/main
cd /Satori/Lib/ && git pull
cd /Satori/Wallet/ && git pull
cd /Satori/Engine/ && git pull
cd /Satori/Synapse/ && git pull
