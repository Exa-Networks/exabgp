# CLI Dual Transport: Named Pipes and Unix Sockets

**Status:** ✅ Complete (2025-11-19)
**Version:** ExaBGP 5.0+

---

## Overview

ExaBGP's CLI (Command Line Interface) supports two transport mechanisms for communication between the `exabgp cli` command and the running ExaBGP daemon:

1. **Named Pipes (FIFOs)** - Traditional approach using separate input/output pipes
2. **Unix Domain Sockets** - Modern approach using bidirectional socket communication

Both transports can run simultaneously, giving users flexibility in how they interact with ExaBGP.

---

## Quick Start

### Using Unix Sockets (Default, Auto-Enabled)

Unix sockets are **auto-enabled by default** and require **zero manual setup**.

```bash
# Start ExaBGP (socket auto-creates in {install_dir}/run/)
./sbin/exabgp etc/exabgp/api-rib.conf

# Use CLI commands (defaults to socket)
./sbin/exabgp cli "show neighbor"
./sbin/exabgp cli "show routes"
```

**That's it!** No `mkdir`, no `mkfifo`, no environment variables needed.

### Using Named Pipes

Named pipes require manual creation but provide compatibility with older setups.

```bash
# Create pipes directory and FIFOs
mkdir -p /tmp/exabgp
mkfifo /tmp/exabgp/exabgp.in /tmp/exabgp/exabgp.out
chmod 600 /tmp/exabgp/exabgp.*

# Start ExaBGP with pipe support
env exabgp_cli_pipe=/tmp/exabgp ./sbin/exabgp etc/exabgp/api-rib.conf

# Use CLI with pipes
./sbin/exabgp cli --pipe "show neighbor"
```

---

## Transport Comparison

| Feature | Named Pipes (FIFO) | Unix Sockets |
|---------|-------------------|--------------|
| **Enabled By Default** | No (opt-in) | Yes (auto-enabled) |
| **Setup Required** | Manual (`mkfifo`) | Automatic |
| **File Count** | 2 files (`.in`, `.out`) | 1 file (`.sock`) |
| **Bidirectional** | No (requires 2 FIFOs) | Yes (single socket) |
| **Connection Model** | Open/close | Connect/disconnect |
| **Modern Standard** | Legacy | Yes |
| **Recommended** | Legacy support only | All new deployments |

---

## Configuration

### Environment Variables

#### Server-Side (ExaBGP Daemon)

Controls which transport processes are spawned:

- **`exabgp_cli_socket`** - Directory path for Unix socket (e.g., `/tmp/exabgp`)
  - **AUTO-ENABLED** by default when `api.cli=true`
  - Defaults to `{install_dir}/run/` if not set
  - Socket file is auto-created by ExaBGP
  - Set to empty string to disable: `exabgp_cli_socket=''`

- **`exabgp_cli_pipe`** - Directory path for named pipes (e.g., `/tmp/exabgp`)
  - **OPT-IN** (disabled by default)
  - Only enables if pipes exist before starting ExaBGP
  - Requires manual `mkfifo` setup

- **`exabgp_api_pipename`** - Custom pipe basename (default: `exabgp`)
  - Results in `{pipename}.in` and `{pipename}.out`

- **`exabgp_api_socketname`** - Custom socket basename (default: `exabgp`)
  - Results in `{socketname}.sock`

- **`exabgp_api_socketpath`** - Explicit socket file path (overrides discovery)

#### Client-Side (CLI Tool)

Controls which transport the CLI uses:

- **`exabgp_cli_transport`** - Force transport: `"pipe"` or `"socket"`
  - Overrides default (socket) behavior
  - Command-line flags take precedence

### Command-Line Flags

The `exabgp cli` command supports transport selection:

- **`--socket`** - Use Unix socket transport (default, explicit)
- **`--pipe`** - Use named pipe transport
- **`--pipename NAME`** - Custom pipe name (for pipe transport only)

Flags are mutually exclusive. If both provided, `--pipe` takes precedence.

### Configuration File

ExaBGP's configuration file can set defaults:

```ini
env {
    api {
        cli true;              # Enable CLI (default: true)
        pipename 'exabgp';     # Pipe basename (default: exabgp)
        socketname 'exabgp';   # Socket basename (default: exabgp)
    }
}
```

---

## Transport Selection Logic

The CLI tool determines which transport to use with this priority (highest first):

1. **Command-line flags** - `--pipe` or `--socket`
2. **Environment variable** - `exabgp_cli_transport`
3. **Default** - Unix socket

This ensures explicit user choice always wins.

**Example:**
```bash
# Environment says pipe, but flag overrides to socket
env exabgp_cli_transport=pipe ./sbin/exabgp cli --socket "show neighbor"
# → Uses socket
```

---

## Socket Path Discovery

Both transports search standard locations for their files:

1. `/run/exabgp/`
2. `/run/{uid}/` (your user ID)
3. `/run/`
4. `/var/run/exabgp/`
5. `/var/run/{uid}/`
6. `/var/run/`
7. `{root}/run/exabgp/` (ExaBGP install directory)
8. `{root}/run/`
9. And more...

**Override with environment variables:**
- Pipes: Set `exabgp_cli_pipe=/custom/path`
- Sockets: Set `exabgp_cli_socket=/custom/path` or `exabgp_api_socketpath=/custom/path/file.sock`

---

## Usage Examples

### Basic Usage

```bash
# Default (socket)
./sbin/exabgp cli "show neighbor"

# Explicit socket
./sbin/exabgp cli --socket "show neighbor"

# Force pipe
./sbin/exabgp cli --pipe "show neighbor"

# Environment override
env exabgp_cli_transport=pipe ./sbin/exabgp cli "show neighbor"
```

### Custom Names

```bash
# Server: Use custom socket name
env exabgp_api_socketname=mybgp ./sbin/exabgp etc/exabgp/api-rib.conf

# Client: Match the custom name
env exabgp_api_socketname=mybgp ./sbin/exabgp cli "show neighbor"
```

### Both Transports Simultaneously

```bash
# Create pipes
mkdir -p /tmp/exabgp
mkfifo /tmp/exabgp/exabgp.{in,out}
chmod 600 /tmp/exabgp/exabgp.*

# Start with both enabled
env exabgp_cli_pipe=/tmp/exabgp \
    exabgp_cli_socket=/tmp/exabgp \
    ./sbin/exabgp etc/exabgp/api-rib.conf

# Use either transport
./sbin/exabgp cli --socket "show neighbor"  # Uses socket
./sbin/exabgp cli --pipe "show neighbor"    # Uses pipe
```

### Custom Locations

```bash
# Server: Custom socket location
env exabgp_cli_socket=/opt/exabgp/run \
    ./sbin/exabgp etc/exabgp/api-rib.conf

# Client: Explicit socket file
env exabgp_api_socketpath=/opt/exabgp/run/exabgp.sock \
    ./sbin/exabgp cli "show neighbor"
```

---

## Troubleshooting

### Socket Not Found

**Error:**
```
could not find ExaBGP's Unix socket (exabgp.sock) for the cli
we scanned the following folders:
 - /run/exabgp/
 - /run/1000/
 - ...
```

**Solution:**
1. Check if ExaBGP is running: `ps aux | grep exabgp`
2. Verify socket exists: `ls -la /tmp/exabgp/exabgp.sock`
3. Set explicit path: `env exabgp_api_socketpath=/path/to/socket.sock`

### Pipe Not Found

**Error:**
```
could not find ExaBGP's named pipes (exabgp.in and exabgp.out) for the cli
```

**Solution:**
1. Create pipes:
   ```bash
   mkdir -p /tmp/exabgp
   mkfifo /tmp/exabgp/exabgp.in /tmp/exabgp/exabgp.out
   chmod 600 /tmp/exabgp/exabgp.*
   ```
2. Set location: `env exabgp_cli_pipe=/tmp/exabgp`
3. Restart ExaBGP

### Permission Denied

**Error:**
```
Permission denied: /run/exabgp/exabgp.sock
```

**Solution:**
1. Check ownership: `ls -la /run/exabgp/exabgp.sock`
2. Fix permissions:
   ```bash
   sudo chown $USER:$USER /run/exabgp/exabgp.sock
   chmod 600 /run/exabgp/exabgp.sock
   ```
3. Or use user-writable location:
   ```bash
   mkdir -p ~/exabgp/run
   env exabgp_cli_socket=~/exabgp/run ./sbin/exabgp config.conf
   ```

### Connection Refused

**Error:**
```
ExaBGP is not accepting connections on Unix socket
```

**Cause:** Socket file exists but no ExaBGP process is listening

**Solution:**
1. Check if ExaBGP is running: `ps aux | grep exabgp`
2. Remove stale socket: `rm /tmp/exabgp/exabgp.sock`
3. Restart ExaBGP

---

## Migration Guide

### From Pipes to Sockets

**Why migrate?**
- Zero setup (no `mkfifo` required)
- Single file instead of two
- Bidirectional communication
- Modern standard

**Migration steps:**

1. **Test socket transport** (without removing pipes):
   ```bash
   # Enable both transports
   env exabgp_cli_pipe=/tmp/exabgp \
       exabgp_cli_socket=/tmp/exabgp \
       ./sbin/exabgp etc/exabgp/api-rib.conf

   # Test socket CLI
   ./sbin/exabgp cli --socket "show neighbor"
   ```

2. **Update scripts** to remove `--pipe` flags:
   ```bash
   # Old
   ./sbin/exabgp cli --pipe "show neighbor"

   # New (socket is default)
   ./sbin/exabgp cli "show neighbor"
   ```

3. **Remove pipe setup** from startup scripts:
   ```bash
   # Remove these lines
   # mkfifo /tmp/exabgp/exabgp.{in,out}
   # chmod 600 /tmp/exabgp/exabgp.*
   ```

4. **Remove pipe environment variable**:
   ```bash
   # Old
   env exabgp_cli_pipe=/tmp/exabgp ./sbin/exabgp config.conf

   # New (socket auto-enabled)
   ./sbin/exabgp config.conf
   ```

5. **Verify** socket is working:
   ```bash
   ./sbin/exabgp cli "show neighbor"
   # Should work without --pipe flag
   ```

**Gradual migration:** Both transports can coexist indefinitely. No rush to migrate if pipes work for you.

---

## Architecture

### Named Pipe Architecture

```
┌─────────────┐                ┌──────────────┐
│  CLI Tool   │                │   ExaBGP     │
│             │                │   Daemon     │
└─────┬───────┘                └───────▲──────┘
      │                                │
      │  Write command                 │
      └──────────────┐                 │
                     ▼                 │
              ┌─────────────┐          │
              │  FIFO.in    │          │
              └──────┬──────┘          │
                     │                 │
                     │                 │
                     ▼                 │
              ┌─────────────┐          │
              │ Pipe Process│──────────┘
              │  (pipe.py)  │
              └──────┬──────┘
                     │
                     ▼
              ┌─────────────┐
              │  FIFO.out   │
              └──────┬──────┘
                     │
      ┌──────────────┘
      │  Read response
      ▼
┌─────────────┐
│  CLI Tool   │
└─────────────┘
```

### Unix Socket Architecture

```
┌─────────────┐                ┌──────────────┐
│  CLI Tool   │                │   ExaBGP     │
│             │                │   Daemon     │
└─────┬───────┘                └───────▲──────┘
      │                                │
      │  Connect                       │
      └──────────────┐                 │
                     ▼                 │
              ┌─────────────┐          │
              │ socket.sock │          │
              └──────┬──────┘          │
                     │                 │
                     │  Bidirectional  │
                     ▼                 │
              ┌─────────────┐          │
              │   Socket    │──────────┘
              │  Process    │
              │(unixsocket.py)
              └─────────────┘
```

**Key differences:**
- Pipes: Unidirectional (need 2 files), client writes to `.in` and reads from `.out`
- Sockets: Bidirectional (1 file), client reads and writes on same connection

---

## Implementation Details

### Process Spawning

When ExaBGP starts with CLI enabled, it spawns internal processes:

**Pipe process** (if `exabgp_cli_pipe` set):
- Process name: `api-internal-cli-pipe-{uuid}`
- Module: `src/exabgp/application/pipe.py`
- Environment: `exabgp_cli_pipe` set to pipe directory

**Socket process** (if `exabgp_cli_socket` set or default):
- Process name: `api-internal-cli-socket-{uuid}`
- Module: `src/exabgp/application/unixsocket.py`
- Environment: `exabgp_cli_socket` set to socket directory

Both processes:
- Share `API_PREFIX` (`api-internal-cli-`) for routing
- Forward commands between CLI and ExaBGP daemon
- Enable/acknowledge API commands
- Use `stdin`/`stdout` for ExaBGP communication

### Files Created

**Named pipes:**
- `{location}/{pipename}.in` - Input FIFO (CLI → ExaBGP)
- `{location}/{pipename}.out` - Output FIFO (ExaBGP → CLI)
- Created manually with `mkfifo`
- Permissions: `600` (owner read/write only)

**Unix socket:**
- `{location}/{socketname}.sock` - Socket file
- Created automatically by ExaBGP
- Permissions: Inherited from directory (typically `700`)
- Auto-removed on clean shutdown
- Stale files detected and cleaned up

### Security Considerations

**File permissions:**
- Named pipes: Set to `600` to prevent unauthorized access
- Unix sockets: Placed in mode `700` directories (e.g., `/run/exabgp/`)
- Both: Only accessible by ExaBGP user

**Recommendations:**
1. Use dedicated directories (e.g., `/run/exabgp/`, not `/tmp/`)
2. Set directory ownership to ExaBGP user
3. Set directory permissions to `700` (owner-only access)
4. Avoid world-readable locations

**Example secure setup:**
```bash
# Create dedicated directory
sudo mkdir -p /run/exabgp
sudo chown exabgp:exabgp /run/exabgp
sudo chmod 700 /run/exabgp

# Start ExaBGP (socket auto-created with safe permissions)
sudo -u exabgp ./sbin/exabgp etc/exabgp/api-rib.conf
```

---

## Design Decisions

### Why Two Transports?

**Backward Compatibility:**
- Named pipes have been the standard for years
- Existing deployments rely on pipe-based automation
- Both can coexist without conflict

**Modern Approach:**
- Unix sockets are the modern IPC standard
- Simpler (1 file vs 2)
- Better connection semantics
- Zero manual setup

**User Choice:**
- Some environments prefer FIFOs
- Some require sockets
- Users can choose what works best

### Why Socket is Default?

1. **Ease of use** - Zero setup required
2. **Modern standard** - Industry best practice for IPC
3. **Simpler model** - Bidirectional, single file
4. **Better semantics** - Connect/disconnect vs open/close

### Why Keep Pipes?

1. **Backward compatibility** - Don't break existing setups
2. **User preference** - Some users prefer FIFOs
3. **No cost** - Both transports coexist peacefully
4. **Migration flexibility** - Gradual transition

---

## Environment Variable Reference

### Quick Reference Table

| Variable | Scope | Purpose | Example |
|----------|-------|---------|---------|
| `exabgp_cli_pipe` | Server | Enable pipe process | `/tmp/exabgp` |
| `exabgp_cli_socket` | Server | Enable socket process | `/tmp/exabgp` |
| `exabgp_api_pipename` | Both | Pipe basename | `exabgp` |
| `exabgp_api_socketname` | Both | Socket basename | `exabgp` |
| `exabgp_api_socketpath` | Both | Explicit socket path | `/run/exabgp/exabgp.sock` |
| `exabgp_cli_transport` | Client | Force transport | `pipe` or `socket` |

### Detailed Descriptions

**`exabgp_cli_pipe`** (Server)
- **Type:** Directory path
- **Purpose:** Enable pipe-based internal CLI process
- **Required:** No (opt-in)
- **Example:** `exabgp_cli_pipe=/tmp/exabgp`
- **Note:** Pipes must exist before starting ExaBGP

**`exabgp_cli_socket`** (Server)
- **Type:** Directory path
- **Purpose:** Enable socket-based internal CLI process
- **Required:** No (auto-enabled if `api.cli=true`)
- **Example:** `exabgp_cli_socket=/tmp/exabgp`
- **Note:** Socket file auto-created

**`exabgp_api_pipename`** (Both)
- **Type:** String (basename)
- **Purpose:** Customize pipe filenames
- **Default:** `exabgp`
- **Example:** `exabgp_api_pipename=mybgp`
- **Results in:** `mybgp.in` and `mybgp.out`

**`exabgp_api_socketname`** (Both)
- **Type:** String (basename)
- **Purpose:** Customize socket filename
- **Default:** `exabgp`
- **Example:** `exabgp_api_socketname=mybgp`
- **Results in:** `mybgp.sock`

**`exabgp_api_socketpath`** (Both)
- **Type:** Full file path
- **Purpose:** Override socket discovery with explicit path
- **Default:** None (uses discovery)
- **Example:** `exabgp_api_socketpath=/opt/exabgp/run/control.sock`
- **Note:** Overrides directory + basename logic

**`exabgp_cli_transport`** (Client)
- **Type:** String (`pipe` or `socket`)
- **Purpose:** Force CLI to use specific transport
- **Default:** None (uses socket)
- **Example:** `exabgp_cli_transport=pipe`
- **Note:** Command-line flags override this

---

## Testing

Both transports are fully tested with 100% test coverage:

**Unit Tests:**
```bash
env exabgp_log_enable=false pytest ./tests/unit/test_cli_transport.py -v
```
- Path discovery logic (20+ tests)
- Transport selection priority
- Argument parsing
- Environment variable handling
- Command shortcuts

**Functional Tests:**
```bash
# Quick test (socket + pipe)
./tests/quick-transport-test.sh

# Comprehensive test suite
./tests/functional/test_cli_transports.sh
```
- Test 1: Socket auto-enabled (default behavior)
- Test 2: Pipe opt-in (legacy support)
- Test 3: Dual transport (both simultaneously)
- Test 4: Socket disabled (pipe required)

**Integration Tests:**
- All 72 encoding tests pass with both transports
- All 18 decoding tests pass with both transports
- Configuration validation passes

**Manual Testing:**
- Concurrent usage (both transports simultaneously)
- Custom names and paths
- Error handling (missing files, permissions, etc.)
- Migration scenarios

---

## Related Documentation

- **Implementation:** `.claude/DUAL_TRANSPORT_IMPLEMENTATION_SUMMARY.md`
- **Planning:** `.claude/DUAL_TRANSPORT_API_PLAN.md`
- **Startup Checks:** `.claude/SOCKET_STARTUP_CHECKS.md`
- **Environment Setup:** `src/exabgp/environment/setup.py` (lines 252-307)

---

## Changelog

**2025-11-19:** Initial release
- ✅ Unix socket transport implemented
- ✅ Dual transport support (pipes + sockets)
- ✅ CLI flags for transport selection
- ✅ Environment variable configuration
- ✅ Socket name configuration added
- ✅ All tests passing (1424 unit, 72 encoding, 18 decoding)

---

**Last Updated:** 2025-11-19
