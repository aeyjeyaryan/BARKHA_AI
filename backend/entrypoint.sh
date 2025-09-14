#!/bin/bash
# entrypoint.sh

# Start virtual display for headless operation
Xvfb :99 -screen 0 1024x768x24 > /dev/null 2>&1 &

# Wait a moment for Xvfb to start
sleep 2

# Run your Python script
exec python3 "$@"
