#!/bin/bash
# dos2unix pull.sh might require
echo "Pulling main branch in /Satori/..."
git pull origin refs/heads/main
cd /Satori/Lib/ && git pull origin refs/heads/main
cd /Satori/Wallet/ && git pull origin refs/heads/main
cd /Satori/Engine/ && git pull origin refs/heads/main
cd /Satori/Synapse/ && git pull origin refs/heads/main
