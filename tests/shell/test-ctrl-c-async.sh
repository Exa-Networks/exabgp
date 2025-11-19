#!/bin/bash
# Test that async mode handles Ctrl+C gracefully

set -e

echo "Starting ExaBGP in async mode..."
env exabgp_reactor_asyncio=true exabgp_log_enable=false ./sbin/exabgp etc/exabgp/api-rib.conf &
PID=$!

echo "ExaBGP PID: $PID"
sleep 2

echo "Sending SIGINT (Ctrl+C) to ExaBGP..."
kill -INT $PID

# Wait for process to exit
if wait $PID 2>/dev/null; then
    EXIT_CODE=$?
else
    EXIT_CODE=$?
fi

echo "ExaBGP exited with code: $EXIT_CODE"

# Check if exit was clean (0 = normal exit)
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ SUCCESS: ExaBGP handled Ctrl+C gracefully"
    exit 0
else
    echo "❌ FAIL: ExaBGP exited with non-zero code: $EXIT_CODE"
    exit 1
fi
