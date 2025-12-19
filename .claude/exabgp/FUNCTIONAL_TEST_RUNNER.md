# Functional Test Runner Architecture

Complete documentation of `qa/bin/functional` - the ExaBGP functional test runner.

**File:** `qa/bin/functional` (~2902 lines)

---

## Overview

The functional test runner orchestrates three types of tests:
1. **Encoding tests** - Validate BGP message encoding (17 tests)
2. **Decoding tests** - Validate BGP message decoding (11 tests)
3. **Parsing tests** - Validate configuration file parsing (35 tests)

---

## Core Classes

### 1. `Exec` (lines 470-663)

Process execution wrapper with robust cleanup.

```python
class Exec:
    code: int = -1           # Exit code
    stdout: bytes = b''      # Captured stdout
    stderr: bytes = b''      # Captured stderr
    _process: Popen | None   # Subprocess handle

    def run(command: List[str], env: Dict | None) -> Exec
    def ready() -> bool                    # Check if process finished
    def collect() -> None                  # Collect stdout/stderr
    def terminate(collect: bool) -> None   # Kill process tree
```

**Key features:**
- Uses `subprocess.Popen` with `start_new_session=True` for process group isolation
- `psutil` for reliable process tree cleanup (SIGTERM then SIGKILL)
- 15-second timeout on `communicate()` to collect output
- Retry logic for stubborn processes

### 2. `State` Enum (line 665)

Test state machine:
```python
State = Enum('State', 'NONE STARTING RUNNING FAIL SUCCESS SKIP TIMEOUT')
```

Transitions:
```
SKIP ─► NONE ─► STARTING ─► RUNNING ─► SUCCESS
                                   └─► FAIL
                                   └─► TIMEOUT
```

### 3. `Record` (lines 668-746)

Test metadata and state tracking.

```python
class Record:
    nick: str              # Short ID (0-9, A-Z, a-z, Greek letters)
    name: str              # Test name (e.g., "api-announce")
    conf: Dict[str, Any]   # Test configuration
    files: List[str]       # Associated files
    state: State           # Current state
    start_time: float | None
    timeout: float = 999999.0

    def setup() -> None      # Advance NONE→STARTING→RUNNING
    def result(success: bool) -> bool
    def has_timed_out() -> bool
```

**Nick assignment:** Sequential from listing `0123456789ABC...αβγδ...`

### 4. `Tests` Base Class (lines 749-1041)

Test collection management with common functionality.

```python
class Tests:
    _by_nick: Dict[str, Record]  # Nick → Test mapping
    _ordered: List[str]          # Ordered nick list
    _start_time: float | None    # Test suite start
    _max_timeout: int            # Global timeout

    def new(name: str) -> Record
    def enable_by_nick(nick: str) -> bool
    def enable_all() / disable_all()
    def selected() -> List[Record]   # Active tests
    def display()                     # Live status line
    def summary()                     # Final results
    def _run_event_loop(timeout, running) -> bool
```

**Display format:**
```
elapsed 5s timeout [5/60] daemons 72 clients 72 passed 50 failed 2 [A, B] pending 20
```

### 5. `EncodingTests` (lines 1465-2080)

BGP message encoding validation.

```python
class EncodingTests(Tests):
    class Test(Record, Exec):
        _check: bytes = b'successful'

        def success() -> bool:
            return code == 0 and _check in (stdout or stderr)

    # Configuration structure (EncodingConf TypedDict):
    # - confs: List[str]  - Config file paths
    # - ci: str           - Path to .ci file
    # - msg: str          - Path to .msg file
    # - port: int         - TCP port

    def client(nick) -> str       # Generate client command
    def server(nick) -> str       # Generate server command
    def run_selected(timeout, save_dir, verbose, debug_tests, quiet) -> bool
```

**Encoding test flow:**
1. Start server: `./qa/sbin/bgp --view <test.msg> --port <port>`
2. Start client: `env exabgp_tcp_port=<port> ./sbin/exabgp -d -p <config>`
3. ExaBGP spawns API process from config
4. API process sends commands via stdout
5. ExaBGP encodes routes to BGP UPDATE messages
6. Server compares received bytes with expected `.msg` file
7. Server prints "successful" if all messages match

### 6. `DecodingTests` (lines 2083-2220)

BGP message decoding validation.

```python
class DecodingTests(Tests):
    class Test(Record, Exec):
        def _cleanup(decoded: Dict) -> Dict:
            # Remove dynamic fields: exabgp, host, pid, ppid, time, version

        def success() -> bool:
            decoded = json.loads(stdout)
            return _cleanup(decoded) == conf['json']

    # Configuration structure (DecodingConf TypedDict):
    # - type: str     - 'open', 'update', 'nlri'
    # - family: str   - 'ipv4 unicast', etc.
    # - packet: str   - Hex packet data
    # - json: Dict    - Expected decoded JSON
```

**Decoding test flow:**
1. Run: `./sbin/exabgp decode [-f <family>] --<type> <hex>`
2. Parse JSON output
3. Remove dynamic fields (pid, time, etc.)
4. Compare with expected JSON from test file

### 7. `ParsingTests` (lines 2223-2389)

Configuration file validation.

```python
class ParsingTests(Tests):
    class Test(Record, Exec):
        def success() -> bool:
            return code == 0

    # Configuration structure (ParsingConf TypedDict):
    # - fname: str  - Config file path
```

**Parsing test flow:**
1. Run: `./sbin/exabgp configuration validate -nrv <config>`
2. Check exit code is 0

---

## Test File Formats

### Encoding Tests (qa/encoding/)

**`.ci` file:** Single line with config filename(s)
```
api-announce.conf
```

**`.msg` file:** Expected BGP messages in hex
```
option:tcp_connections:2
1:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:001702:00000000
1:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:003802:0000001C...
```

Format: `<conn>:raw:<marker>:<length><type>:<payload>`
- `conn`: Connection number (1, 2, A1, B1, etc.)
- `marker`: 16-byte BGP marker (FFFF...)
- `length`: 2-byte message length
- `type`: 2-byte message type (02 = UPDATE)
- `payload`: Message content

**`.conf` file:** ExaBGP configuration with process definition
```
process add-remove {
    run ./run/api-announce.run;
    encoder json;
}

neighbor 127.0.0.1 {
    ...
    api { processes [ add-remove ]; }
}
```

**`.run` file:** Python script in `etc/exabgp/run/`
```python
#!/usr/bin/env python3
import sys, time

def flush(msg):
    sys.stdout.write(msg)
    sys.stdout.flush()

# Send commands to ExaBGP via stdout
flush('announce route 1.1.0.0/24 next-hop 101.1.101.1\n')

# Wait for ACK (JSON or text format)
# done | error | shutdown
```

### Decoding Tests (qa/decoding/)

Single file per test:
```
update ipv4 unicast
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF003C02...
{ "exabgp": "5.0.0", "type": "update", ... }
```

Line 1: Message type and family
Line 2: Hex packet
Line 3: Expected JSON

---

## CLI Interface

### Subcommands

```bash
./qa/bin/functional encoding [options] [test...]
./qa/bin/functional decoding [options] [test...]
./qa/bin/functional parsing [options] [test...]
```

### Common Options

| Option | Description |
|--------|-------------|
| `--list` | List all tests with nick and name |
| `--short-list` | List test nicks only (space separated) |
| `--edit <nick>` | Open test files in $EDITOR |
| `--dry` | Show commands without executing |
| `--timeout N` | Total timeout in seconds (default: 20) |
| `--verbose, -v` | Show output for each test |
| `--debug, -d <nick>` | Run all tests, verbose only for specified |
| `--quiet, -q` | Single line on success, verbose on failure |
| `<nick>` | Run specific test(s) by nick |

### Encoding-Specific Options

| Option | Description |
|--------|-------------|
| `--server <nick>` | Start server only (for manual debugging) |
| `--client <nick>` | Start client only (for manual debugging) |
| `--port N` | Base port number (default: 1790) |
| `--save <dir>` | Save run logs for debugging |
| `--stress N` | Run test N times, report statistics |

### Examples

```bash
# Run all encoding tests
./qa/bin/functional encoding

# Run specific test
./qa/bin/functional encoding A

# List tests
./qa/bin/functional encoding --list

# Debug single test in two terminals
./qa/bin/functional encoding --server A   # Terminal 1
./qa/bin/functional encoding --client A   # Terminal 2

# Stress test
./qa/bin/functional encoding A --stress 10

# Quiet mode
./qa/bin/functional encoding -q
```

---

## Environment Variables

Set by test runner for ExaBGP:

```bash
exabgp_log_enable=false
exabgp_api_version=4          # Use v4 API (text encoder) for existing tests
exabgp_tcp_port=<port>
exabgp_tcp_connections=<N>
exabgp_api_cli=false
exabgp_debug_rotate=true
exabgp_debug_configuration=true
exabgp_api_socketname=exabgp-test-<port>
```

---

## Process Cleanup

The test runner uses multiple cleanup strategies:

1. **psutil tree kill:** Find all descendant processes and SIGTERM then SIGKILL
2. **Process group kill:** `os.killpg(pgid, SIGKILL)` with retry logic
3. **Stale process cleanup:** Kill leftover processes before test run
4. **Signal handlers:** Catch SIGTERM/SIGINT for graceful cleanup

Patterns matched for cleanup:
- `qa/sbin/bgp` - Test servers
- `sbin/exabgp` - ExaBGP instances
- `src/exabgp/application/main` - Python module runs
- `run/api-` - API test scripts

---

## Adding New Test Types

To add a new test type (e.g., `APITests`):

1. **Create test class:**
```python
class APITests(Tests):
    class Test(Record, Exec):
        def success(self) -> bool:
            # Define success criteria
            pass

    def __init__(self):
        super().__init__(self.Test)
        # Load tests from qa/api/

    def run_selected(self, timeout, ...) -> bool:
        # Execute tests
        pass
```

2. **Register in main:**
```python
api = APITests()
add_test(subparser, 'api', api, ['list', 'dry', 'timeout', ...])
```

3. **Create test files** in appropriate directories

---

## Success Criteria by Test Type

| Type | Success Condition |
|------|-------------------|
| Encoding | `exit_code == 0 AND b'successful' in output` |
| Decoding | `decoded_json == expected_json` (after cleanup) |
| Parsing | `exit_code == 0` |

---

## Key Functions

### `add_test()` (lines 2474-2625)

Factory function that creates subparser and callback for a test type.

```python
def add_test(
    subparser: _SubParsersAction,
    name: str,           # 'encoding', 'decoding', 'parsing'
    tests: Tests,        # Test class instance
    extra: List[str],    # Options to enable
) -> None
```

### `run_stress_test()` (lines 2392-2471)

Run single test N times and report statistics.

### `cleanup_stale_processes()` (lines 366-467)

Pre-flight cleanup of leftover processes from previous runs.

### `check_concurrent_functional()` (lines 330-363)

Detect if another test runner instance is running.

---

**Updated:** 2025-12-19
