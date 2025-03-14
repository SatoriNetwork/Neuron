#!/bin/bash

# Uncomment if IPFS is required
# ipfs init
# ipfs daemon &

# Check if config.yaml has headless set to True
HEADLESS=$(python headless_check.py)

if [ "$HEADLESS" = "True" ]; then
    echo "Running in headless mode"
    python headless.py
else
    # Start required background processes
    nohup python /Satori/Neuron/satorineuron/web/data.py > data.log 2>&1 &
    nohup python /Satori/Engine/satoriengine/veda/enginerun.py > enginerun.log 2>&1 &

    # Run main application
    python app.py
fi
