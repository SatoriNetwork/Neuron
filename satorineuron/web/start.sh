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
    # Function to start all three processes
    start_all_processes() {
        echo "Starting all processes at $(date)..."
        # Kill existing processes if running - the "|| true" prevents errors if process not found
        pkill -f "python app.py" || true
        pkill -f "python data.py" || true
        pkill -f "python /Satori/Engine/satoriengine/veda/enginerun.py" || true
        
        # Give processes time to shut down
        sleep 5
        
        # Start all processes
        nohup python app.py > app.log 2>&1 &
        nohup python data.py > data.log 2>&1 &
        nohup python /Satori/Engine/satoriengine/veda/enginerun.py > enginerun.log 2>&1 &
        
        echo "All processes restarted at $(date)"
    }
    
    # Start processes for the first time
    start_all_processes
    
    # Keep container alive with infinite loop
    echo "Main processes started, keeping container alive at $(date)..."
    while true; do
        # Check if any of the three processes are not running
        if ! pgrep -f "python app.py" > /dev/null || ! pgrep -f "python data.py" > /dev/null || ! pgrep -f "python /Satori/Engine/satoriengine/veda/enginerun.py" > /dev/null; then
            echo "One of the main processes died at $(date), restarting all processes..."
            start_all_processes
        fi
        
        # Sleep for 5 minutes before checking again
        sleep 300
    done
fi