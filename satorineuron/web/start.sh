#!/bin/bash
#ipfs init;
#ipfs daemon &

# Check if config.yaml has headless set to True
HEADLESS=$(python headless_check.py)

if [ "$HEADLESS" = "True" ]; then
    echo "Running headless.py"
    python headless.py
else
    echo "Running Neuron.py"
    python app.py
fi
