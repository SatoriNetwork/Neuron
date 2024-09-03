#!/bin/bash
#ipfs init;
#ipfs daemon &

# Check if config.yaml has headless set to True
HEADLESS=$(python headless_check.py)

if [ "$HEADLESS" = "True" ]; then
    echo "Running in headless mode"
    python headless.py
else
    python app.py
fi
