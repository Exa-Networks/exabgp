# Functional Tests

End-to-end functional tests for ExaBGP.

---

## CLI Transport Tests

**File:** `test_cli_transports.sh`

Tests socket and pipe transports work correctly:

```bash
# Run all transport tests
./tests/functional/test_cli_transports.sh
```

**What it tests:**
- Socket auto-enabled (default)
- Pipe opt-in (legacy)
- Both transports simultaneously
- Socket disabled fallback

**Duration:** ~30 seconds

**See:** `docs/projects/cli-dual-transport/testing.md` for details

---

## Quick Test

**File:** `../quick-transport-test.sh`

Fast sanity check:

```bash
# Quick test
./tests/quick-transport-test.sh
```

**Duration:** ~10 seconds

---

## Requirements

- ExaBGP installed
- Bash
- `mkfifo` command
- `pkill` command
- Write permissions in `/tmp`

---

**Last Updated:** 2025-11-19
