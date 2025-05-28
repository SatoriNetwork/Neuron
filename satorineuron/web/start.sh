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
    check_processes() {
        local dead_processes=()
        local timestamp=$(date)
        
        # Check each process individually
        if ! pgrep -f "python satori.py" > /dev/null; then
            dead_processes+=("satori.py")
        fi
        
        if ! pgrep -f "python data.py" > /dev/null; then
            dead_processes+=("data.py")
        fi
        
        if ! pgrep -f "python /Satori/Engine/satoriengine/veda/engine.py" > /dev/null; then
            dead_processes+=("engine.py")
        fi
        
        # Report which processes died
        if [ ${#dead_processes[@]} -gt 0 ]; then
            echo "[$timestamp] Dead processes detected: ${dead_processes[*]}"
            return 1  # Indicates processes are dead
        else
            return 0  # All processes are alive
        fi
    }

    # Function to handle different exit codes
    handle_exit_code() {
        local exit_code=$1
        local timestamp=$(date)
        
        echo "Processing exit code $exit_code at $timestamp"
        
        case $exit_code in
            0)
                echo "Shutdown requested (exit code 0)"
                # Create shutdown flag
                touch /tmp/shutdown_requested
                # Stop all processes gracefully
                pkill -TERM -f "python data.py" || true
                sleep 1
                pkill -9 -f "python data.py" || true

                pkill -TERM -f "python satori.py" || true
                sleep 1
                pkill -9 -f "python satori.py" || true

                pkill -TERM -f "python /Satori/Engine/satoriengine/veda/engine.py" || true
                sleep 1
                pkill -9 -f "python /Satori/Engine/satoriengine/veda/engine.py" || true
                
                # Wait a bit for graceful shutdown
                sleep 10
                
                # Exit the container as requested
                exit 0
                ;;
            1)
                echo "Container restart requested (exit code 1) - restarting all processes"
                # Full restart as requested
                restart_all_processes
                sleep 5
                ;;
            2)
                echo "Neuron Application restart requested (exit code 2)"
                pkill -f "python satori.py" || true
                sleep 1
                pkill -9 -f "python satori.py" || true
                sleep 5
                nohup python satori.py > app.log 2>&1 &
                ;;
            3)
                echo "Satori app restart (exit code 3) - this should be handled internally by Python"
                # This is handled by your Python monitorAndRestartSatori loop
                # No action needed from bash script
                ;;
            *)
                echo "Unexpected exit code $exit_code - performing default restart"
                sleep 15
                restart_all_processes
                ;;
        esac
    }
    
    # Function to restart all processes
    restart_all_processes() {
        echo "Restarting all processes at $(date)..."
        
        # Kill existing processes
        pkill -f "python satori.py" || true
        sleep 1
        pkill -9 -f "python satori.py" || true

        pkill -f "python data.py" || true
        sleep 1
        pkill -9 -f "python data.py" || true

        pkill -f "python /Satori/Engine/satoriengine/veda/engine.py" || true
        sleep 1
        pkill -9 -f "python /Satori/Engine/satoriengine/veda/engine.py" || true
        
        # Kill existing log monitors
        pkill -f "tail -f app.log" || true
        
        # Give processes time to shut down
        sleep 10
        
        # Start all processes
        nohup python data.py > data.log 2>&1 &
        nohup python satori.py > app.log 2>&1 &
        nohup python /Satori/Engine/satoriengine/veda/engine.py > engine.log 2>&1 &
        
        echo "All processes restarted at $(date)"
        
        # Restart log monitoring
        start_log_monitoring
    }
    
    start_log_monitoring() {
        # Monitor app.log for exit codes
        tail -f app.log | while read line; do
            if [[ "$line" =~ Satori\ exited\ with\ code\ ([0-9]+)\. ]]; then
                exit_code="${BASH_REMATCH[1]}"
                echo "Exit code detected in app.log: $exit_code"
                handle_exit_code "$exit_code"
            fi
        done &
        
        # You can also monitor other logs if needed
        # tail -f data.log | while read line; do
        #     # Handle data.py specific messages
        # done &
    }
    
    start_all_processes() {
        echo "Starting all processes at $(date)..."

        nohup python satori.py > app.log 2>&1 &
        nohup python data.py > data.log 2>&1 &
        nohup python /Satori/Engine/satoriengine/veda/engine.py > engine.log 2>&1 &
        
        start_log_monitoring
    }
    
    # Start processes for the first time
    start_all_processes
    
    # Keep container alive with infinite loop
    echo "Main processes started, keeping container alive at $(date)..."
    while true; do
        # Check for shutdown flag first
        if [ -f /tmp/shutdown_requested ]; then
            echo "Shutdown flag detected, stopping monitoring loop"
            exit 0
        fi
        # Check if any of the three processes are not running
        if ! check_processes; then
            restart_all_processes
        fi
        
        # Sleep for 5 minutes before checking again
        sleep 300
    done
fi