#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=================================================="
echo "🐳 Starting SPOT Tracker Flask Container Services..."
echo "=================================================="

# Start the background scraping daemon in the background
# It will read the env variables and run every POLL_INTERVAL seconds
echo "Starting 24/7 background scraping daemon..."
python daemon.py &

# Start the Flask web dashboard in the foreground on port 5000
# Using 'exec' to replace the shell process so OS termination signals are received cleanly
echo "Starting Flask web dashboard on port 5000..."
exec python app.py
