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
    nohup python app.py > app.log 2>&1 &
    nohup python data.py > data.log 2>&1 &
    nohup python /Satori/Engine/satoriengine/veda/enginerun.py > enginerun.log 2>&1 &
    # Run main application in background

    # Keep container alive with infinite loop
    echo "Main processes started, keeping container alive..."
    while true; do
        # Check if processes are still running
        if ! pgrep -f "python app.py" > /dev/null; then
            echo "Main app.py process died, restarting..."
            nohup python app.py > app.log 2>&1 &
        fi

        if ! pgrep -f "python data.py" > /dev/null; then
            echo "data.py process died, restarting..."
            nohup python data.py > data.log 2>&1 &
        fi

        if ! pgrep -f "python /Satori/Engine/satoriengine/veda/enginerun.py" > /dev/null; then
            echo "enginerun.py process died, restarting..."
            nohup python /Satori/Engine/satoriengine/veda/enginerun.py > enginerun.log 2>&1 &
        fi

        # Sleep for 5 minutes before checking again
        sleep 300
    done
fi