#! /bin/bash
echo "Satori Neuron Starting..."
echo ""
echo "WARNING! Satori did not start correctly."
echo ""
echo "TO FIX: Please start the Satori Neuron by clicking on the desktop icon or restarting your entire machine."
echo ""
exec "$@"
python imageStart.py
