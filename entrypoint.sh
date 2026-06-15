#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=================================================="
echo "🐳 Starting SPOT Tracker Container Services..."
echo "=================================================="

# Start the background scraping daemon in the background
# It will read the env variables and run every POLL_INTERVAL seconds
echo "Starting 24/7 background scraping daemon..."
python daemon.py &

# Start the Streamlit frontend dashboard in the foreground
# Using 'exec' to replace the shell process so OS termination signals are received cleanly
echo "Starting Streamlit dashboard on port 8501..."
exec streamlit run app.py --server.port 8501 --server.address 0.0.0.0
