#!/bin/bash
# Get the directory where the script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=================================================="
echo "Starting Lenny's Podcast Transcript Viewer (refactored)..."
echo "Server URL: http://127.0.0.1:5001"
echo "Press Ctrl+C to stop the server."
echo "=================================================="

# Check if required packages are installed (simple check)
if ! python3 -c "import flask" &> /dev/null; then
    echo "Installing dependencies..."
    pip install flask flask-cors openai beautifulsoup4 requests
fi

python3 src/api/server.py
