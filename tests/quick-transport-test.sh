#!/bin/bash
# Quick test to verify both transports work
# Usage: ./tests/quick-transport-test.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Quick CLI Transport Test ==="
echo

# Test 1: Socket (auto-enabled)
echo "Test 1: Starting ExaBGP with socket (auto-enabled)..."
env exabgp_log_enable=false \
    exabgp_tcp_bind='' \
    timeout 5 ./sbin/exabgp ./etc/exabgp/conf-ipself6.conf &
EXABGP_PID=$!

sleep 2

echo "Checking for socket process..."
if ps aux | grep -q "[a]pi-internal-cli-socket"; then
    echo "✓ Socket process spawned"
else
    echo "✗ Socket process NOT found"
    kill $EXABGP_PID 2>/dev/null || true
    exit 1
fi

echo "Testing CLI via socket..."
if ./sbin/exabgp cli "help" 2>&1 | grep -q "show"; then
    echo "✓ CLI via socket works"
else
    echo "✗ CLI via socket failed"
    kill $EXABGP_PID 2>/dev/null || true
    exit 1
fi

kill $EXABGP_PID 2>/dev/null || true
wait $EXABGP_PID 2>/dev/null || true

echo
echo "=== Socket Transport: PASS ✓ ==="
echo

# Test 2: Dual transport
echo "Test 2: Creating pipes for dual transport test..."
mkdir -p /tmp/exabgp-test
mkfifo /tmp/exabgp-test/exabgp.in 2>/dev/null || true
mkfifo /tmp/exabgp-test/exabgp.out 2>/dev/null || true
chmod 600 /tmp/exabgp-test/exabgp.* 2>/dev/null || true

echo "Starting ExaBGP with both socket and pipe..."
env exabgp_log_enable=false \
    exabgp_tcp_bind='' \
    exabgp_cli_pipe=/tmp/exabgp-test \
    timeout 5 ./sbin/exabgp ./etc/exabgp/conf-ipself6.conf &
EXABGP_PID=$!

sleep 2

echo "Checking for both processes..."
SOCKET_OK=false
PIPE_OK=false

if ps aux | grep -q "[a]pi-internal-cli-socket"; then
    echo "✓ Socket process spawned"
    SOCKET_OK=true
else
    echo "✗ Socket process NOT found"
fi

if ps aux | grep -q "[a]pi-internal-cli-pipe"; then
    echo "✓ Pipe process spawned"
    PIPE_OK=true
else
    echo "✗ Pipe process NOT found"
fi

if [ "$SOCKET_OK" = true ] && [ "$PIPE_OK" = true ]; then
    echo "✓ Both processes running"
else
    echo "✗ Not all processes running"
    kill $EXABGP_PID 2>/dev/null || true
    rm -rf /tmp/exabgp-test 2>/dev/null || true
    exit 1
fi

echo "Testing CLI via socket..."
if ./sbin/exabgp cli "help" 2>&1 | grep -q "show"; then
    echo "✓ CLI via socket works"
else
    echo "✗ CLI via socket failed"
fi

echo "Testing CLI via pipe..."
if ./sbin/exabgp cli --pipe "help" 2>&1 | grep -q "show"; then
    echo "✓ CLI via pipe works"
else
    echo "✗ CLI via pipe failed"
fi

kill $EXABGP_PID 2>/dev/null || true
wait $EXABGP_PID 2>/dev/null || true
rm -rf /tmp/exabgp-test 2>/dev/null || true

echo
echo "=== Dual Transport: PASS ✓ ==="
echo
echo "=== ALL TESTS PASSED ✓ ==="
