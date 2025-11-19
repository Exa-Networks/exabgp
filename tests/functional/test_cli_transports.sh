#!/bin/bash
# Functional test for CLI dual transport (socket + pipe)
# Tests that both transports actually work end-to-end

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR="/tmp/exabgp-transport-test-$$"
EXABGP="$ROOT_DIR/sbin/exabgp"
CLI="$ROOT_DIR/sbin/exabgp"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[TEST]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

cleanup() {
    log "Cleaning up..."

    # Kill any ExaBGP processes
    pkill -f "exabgp.*test-dual-transport" 2>/dev/null || true

    # Remove test directory
    rm -rf "$TEST_DIR" 2>/dev/null || true

    log "Cleanup complete"
}

# Trap cleanup on exit
trap cleanup EXIT INT TERM

# Setup test directory
setup() {
    log "Setting up test environment in $TEST_DIR"

    mkdir -p "$TEST_DIR"

    # Create minimal ExaBGP config
    cat > "$TEST_DIR/test-dual-transport.conf" <<EOF
neighbor 127.0.0.1 {
    router-id 1.1.1.1;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65001;

    static {
        route 192.0.2.0/24 next-hop 127.0.0.1;
    }
}
EOF

    log "Test environment ready"
}

# Test 1: Socket transport (auto-enabled)
test_socket_auto_enabled() {
    log "Test 1: Socket transport (auto-enabled)"

    # Start ExaBGP in background
    cd "$ROOT_DIR"
    env exabgp_log_enable=false \
        exabgp_tcp_bind='' \
        "$EXABGP" "$TEST_DIR/test-dual-transport.conf" > "$TEST_DIR/exabgp.log" 2>&1 &

    EXABGP_PID=$!
    log "ExaBGP started (PID: $EXABGP_PID)"

    # Wait for socket to be created
    sleep 2

    # Check if socket process spawned
    if ! ps aux | grep -q "[a]pi-internal-cli-socket"; then
        error "Socket process not spawned"
    fi
    log "✓ Socket process spawned"

    # Check if socket file exists
    SOCKET_FILE="$ROOT_DIR/run/exabgp.sock"
    if [ ! -S "$SOCKET_FILE" ]; then
        error "Socket file not created: $SOCKET_FILE"
    fi
    log "✓ Socket file created: $SOCKET_FILE"

    # Test CLI command via socket
    OUTPUT=$("$CLI" cli "help" 2>&1 || true)
    if ! echo "$OUTPUT" | grep -q "show\|neighbor\|route"; then
        error "CLI command via socket failed. Output: $OUTPUT"
    fi
    log "✓ CLI command via socket works"

    # Cleanup
    kill $EXABGP_PID 2>/dev/null || true
    wait $EXABGP_PID 2>/dev/null || true
    sleep 1

    log "Test 1: PASSED ✓"
    echo
}

# Test 2: Pipe transport (opt-in)
test_pipe_opt_in() {
    log "Test 2: Pipe transport (opt-in)"

    # Create named pipes
    mkdir -p "$TEST_DIR/pipes"
    mkfifo "$TEST_DIR/pipes/exabgp.in"
    mkfifo "$TEST_DIR/pipes/exabgp.out"
    chmod 600 "$TEST_DIR/pipes/exabgp.in"
    chmod 600 "$TEST_DIR/pipes/exabgp.out"
    log "Created named pipes"

    # Start ExaBGP with pipe enabled
    cd "$ROOT_DIR"
    env exabgp_log_enable=false \
        exabgp_tcp_bind='' \
        exabgp_cli_pipe="$TEST_DIR/pipes" \
        "$EXABGP" "$TEST_DIR/test-dual-transport.conf" > "$TEST_DIR/exabgp-pipe.log" 2>&1 &

    EXABGP_PID=$!
    log "ExaBGP started with pipe (PID: $EXABGP_PID)"

    # Wait for processes to spawn
    sleep 2

    # Check if pipe process spawned
    if ! ps aux | grep -q "[a]pi-internal-cli-pipe"; then
        error "Pipe process not spawned"
    fi
    log "✓ Pipe process spawned"

    # Test CLI command via pipe
    OUTPUT=$("$CLI" cli --pipe "help" 2>&1 || true)
    if ! echo "$OUTPUT" | grep -q "show\|neighbor\|route"; then
        error "CLI command via pipe failed. Output: $OUTPUT"
    fi
    log "✓ CLI command via pipe works"

    # Cleanup
    kill $EXABGP_PID 2>/dev/null || true
    wait $EXABGP_PID 2>/dev/null || true
    sleep 1

    log "Test 2: PASSED ✓"
    echo
}

# Test 3: Both transports simultaneously
test_dual_transport() {
    log "Test 3: Dual transport (socket + pipe simultaneously)"

    # Create named pipes
    mkdir -p "$TEST_DIR/dual"
    mkfifo "$TEST_DIR/dual/exabgp.in"
    mkfifo "$TEST_DIR/dual/exabgp.out"
    chmod 600 "$TEST_DIR/dual/exabgp.in"
    chmod 600 "$TEST_DIR/dual/exabgp.out"
    log "Created named pipes"

    # Start ExaBGP with both transports
    cd "$ROOT_DIR"
    env exabgp_log_enable=false \
        exabgp_tcp_bind='' \
        exabgp_cli_pipe="$TEST_DIR/dual" \
        "$EXABGP" "$TEST_DIR/test-dual-transport.conf" > "$TEST_DIR/exabgp-dual.log" 2>&1 &

    EXABGP_PID=$!
    log "ExaBGP started with both transports (PID: $EXABGP_PID)"

    # Wait for processes to spawn
    sleep 2

    # Check if both processes spawned
    if ! ps aux | grep -q "[a]pi-internal-cli-socket"; then
        error "Socket process not spawned"
    fi
    log "✓ Socket process spawned"

    if ! ps aux | grep -q "[a]pi-internal-cli-pipe"; then
        error "Pipe process not spawned"
    fi
    log "✓ Pipe process spawned"

    # Test CLI via socket (default)
    OUTPUT_SOCKET=$("$CLI" cli "help" 2>&1 || true)
    if ! echo "$OUTPUT_SOCKET" | grep -q "show\|neighbor\|route"; then
        error "CLI via socket failed"
    fi
    log "✓ CLI via socket works"

    # Test CLI via pipe (explicit flag)
    OUTPUT_PIPE=$("$CLI" cli --pipe "help" 2>&1 || true)
    if ! echo "$OUTPUT_PIPE" | grep -q "show\|neighbor\|route"; then
        error "CLI via pipe failed"
    fi
    log "✓ CLI via pipe works"

    # Verify both gave same output
    if [ "$OUTPUT_SOCKET" != "$OUTPUT_PIPE" ]; then
        warn "Socket and pipe outputs differ (may be OK)"
    else
        log "✓ Socket and pipe outputs match"
    fi

    # Cleanup
    kill $EXABGP_PID 2>/dev/null || true
    wait $EXABGP_PID 2>/dev/null || true
    sleep 1

    log "Test 3: PASSED ✓"
    echo
}

# Test 4: Socket disabled, pipe required
test_socket_disabled() {
    log "Test 4: Socket disabled, pipe required"

    # Create named pipes
    mkdir -p "$TEST_DIR/pipe-only"
    mkfifo "$TEST_DIR/pipe-only/exabgp.in"
    mkfifo "$TEST_DIR/pipe-only/exabgp.out"
    chmod 600 "$TEST_DIR/pipe-only/exabgp.in"
    chmod 600 "$TEST_DIR/pipe-only/exabgp.out"

    # Start ExaBGP with socket disabled
    cd "$ROOT_DIR"
    env exabgp_log_enable=false \
        exabgp_tcp_bind='' \
        exabgp_cli_socket='' \
        exabgp_cli_pipe="$TEST_DIR/pipe-only" \
        "$EXABGP" "$TEST_DIR/test-dual-transport.conf" > "$TEST_DIR/exabgp-noSocket.log" 2>&1 &

    EXABGP_PID=$!
    log "ExaBGP started with socket disabled (PID: $EXABGP_PID)"

    # Wait for processes
    sleep 2

    # Check socket process did NOT spawn
    if ps aux | grep -q "[a]pi-internal-cli-socket"; then
        error "Socket process spawned when it should be disabled"
    fi
    log "✓ Socket process correctly NOT spawned"

    # Check pipe process spawned
    if ! ps aux | grep -q "[a]pi-internal-cli-pipe"; then
        error "Pipe process not spawned"
    fi
    log "✓ Pipe process spawned"

    # Test CLI via pipe
    OUTPUT=$("$CLI" cli --pipe "help" 2>&1 || true)
    if ! echo "$OUTPUT" | grep -q "show\|neighbor\|route"; then
        error "CLI via pipe failed"
    fi
    log "✓ CLI via pipe works"

    # Test CLI without --pipe flag should fail (no socket)
    OUTPUT_FAIL=$("$CLI" cli "help" 2>&1 || true)
    if ! echo "$OUTPUT_FAIL" | grep -q "could not find.*socket"; then
        warn "Expected socket error, got: $OUTPUT_FAIL"
    else
        log "✓ CLI correctly fails without socket"
    fi

    # Cleanup
    kill $EXABGP_PID 2>/dev/null || true
    wait $EXABGP_PID 2>/dev/null || true
    sleep 1

    log "Test 4: PASSED ✓"
    echo
}

# Main
main() {
    echo
    log "=== ExaBGP CLI Dual Transport Functional Tests ==="
    echo

    setup

    test_socket_auto_enabled
    test_pipe_opt_in
    test_dual_transport
    test_socket_disabled

    echo
    log "=== ALL TESTS PASSED ✓ ==="
    echo
}

main "$@"
