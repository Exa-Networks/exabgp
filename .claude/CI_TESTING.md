# CI Testing Guide

**MANDATORY - Run ALL tests before declaring code ready.**

---

## Required Test Sequence

```bash
# 1. Linting
ruff format src && ruff check src

# 2. Unit tests
env exabgp_log_enable=false pytest ./tests/unit/

# 3. Functional tests
./qa/bin/functional encoding <test_id>
```

---

## Test Details

### Linting
```bash
ruff format src        # Format (single quotes, 120 char)
ruff check src         # Check errors
```
**Must show:** "All checks passed!"

### Unit Tests
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Must show:** "1376 passed" with 0 failures

### Functional Tests
```bash
# List available tests
./qa/bin/functional encoding --short-list

# Run specific test
./qa/bin/functional encoding <letter>

# Run all (sequential, not parallel)
for test in $(./qa/bin/functional encoding --short-list); do
  ./qa/bin/functional encoding "$test"
done
```

**What it does:** Spawns 72 ExaBGP client/server pairs, tests real BGP message exchange
**File descriptors:** Tool automatically sets ulimit if needed
**Success:** All tests ✓, completes in <60s
**Timeout:** 20s per test - timeouts indicate encoding/decoding bugs

**Test results:**
- ✓ Passed
- ✖ Failed
- ⏱ Timed out (encoding/decoding bug)
- ○ Skipped

### Other Tests
```bash
./qa/bin/functional parsing   # Config file parsing
./qa/bin/functional decoding  # Message decoding
./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf  # Config validation
```

---

## Pre-Commit Checklist

- [ ] `ruff format src && ruff check src` ✅
- [ ] `pytest ./tests/unit/` - 1376 passed ✅
- [ ] `./qa/bin/functional encoding <test>` ✅
- [ ] `git status` reviewed
- [ ] User approval obtained

**If ANY unchecked: DO NOT COMMIT**

---

## Debugging

### Encoding Test Failures
```bash
# Run server and client separately
./qa/bin/functional encoding --server <test_id>
./qa/bin/functional encoding --client <test_id>
```

### Port Conflicts
```bash
killall -9 python  # Clear leftover test processes
```

---

## CI Workflows

**All must pass:**
- Linting (Python 3.12)
- Unit tests (Python 3.8-3.12)
- Functional tests (Python 3.8-3.12)
- Legacy tests (Python 3.6)

---

**Updated:** 2025-11-16
**See:** `.claude/archive/docs/` for detailed guides
