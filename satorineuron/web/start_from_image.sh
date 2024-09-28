#!/bin/bash

echo "Satori Neuron Starting..."

# Check if WireGuard is installed and configured
if command -v wg-quick &> /dev/null && [ -f "/etc/wireguard/wg0.conf" ]; then
    echo "Starting WireGuard..."
    wg-quick up wg0
    if [ $? -eq 0 ]; then
        echo "WireGuard started successfully."
    else
        echo "Failed to start WireGuard. Continuing without it."
    fi
else
    echo "WireGuard is not installed or configured. Skipping WireGuard setup."
fi

echo ""
echo "WARNING! If Satori did not start correctly, please follow these steps:"
echo "1. Click on the desktop icon to restart Satori Neuron."
echo "2. If the issue persists, restart your entire machine."
echo ""

# Execute any additional commands passed to the script
exec "$@"

# Start the Python script
python imageStart.py