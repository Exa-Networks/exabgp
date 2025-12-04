# ExaBGP CI Testing Guide

## ⚠️ CRITICAL REQUIREMENTS ⚠️

**YOU MUST RUN ALL TESTS BEFORE DECLARING CODE FIXED OR READY**

Never tell the user that code is "fixed", "ready", "working", or "complete" unless you have run ALL of the following:

1. ✅ `ruff format src && ruff check src` - MUST pass with no errors
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/` - ALL unit tests MUST pass
3. ✅ `./qa/bin/functional encoding <test_id>` - MUST pass for affected tests

**MEMORIZE THIS:** If you make code changes, you MUST run these tests BEFORE claiming success.

## Overview
This guide documents the complete CI testing requirements for ExaBGP. Before declaring code ready for merging, ALL tests described here must pass.

## Test Categories

### 1. Linting (Python 3.12)
**Workflow:** `.github/workflows/linting.yml`

#### Commands to run:
```bash
# Install dependencies
uv sync

# Run flake8 (critical errors only)
uv run flake8 . --max-line-length 120 \
  --exclude src/exabgp/vendoring/ --exclude build/ --exclude site-packages \
  --count --select=E9,F63,F7,F82 --show-source --statistics

# Run ruff (format then check)
uv run ruff format src
uv run ruff check src
```

**What it checks:**
- E9: Runtime errors (syntax errors, etc.)
- F63: Invalid print statement
- F7: Syntax errors in type comments
- F82: Undefined names

---

### 2. Unit Testing (Python 3.8-3.12)
**Workflow:** `.github/workflows/unit-testing.yml`

#### Commands to run:
```bash
# Install dependencies
uv sync

# Run unit tests with coverage (now uses standard test_*.py naming)
env exabgp_log_enable=false uv run pytest --cov --cov-reset ./tests/unit/test_*.py ./tests/fuzz/test_*.py
```

**Test files (using standard pytest naming convention):**
- All files matching `tests/unit/test_*.py` pattern
- All files matching `tests/fuzz/test_*.py` pattern
- Includes comprehensive test coverage for BGP messages, attributes, NLRI types, and fuzzing

---

### 3. Functional Testing (Python 3.8-3.12)
**Workflow:** `.github/workflows/functional-testing.yml`

#### Commands to run:
```bash
# Install dependencies
uv sync

# 1. Configuration/Parsing tests
./qa/bin/functional parsing

# 2. Encoding tests (run SEQUENTIALLY)
for test in $(./qa/bin/functional encoding --short-list); do
  echo "Running test: $test"
  ./qa/bin/functional encoding "$test"
done

# 3. Decoding tests
./qa/bin/functional decoding
```

**Important:** Encoding tests MUST be run sequentially, not in parallel!

---

### 4. Legacy Functional Testing

#### Python 3.6 (ubuntu-20.04)
**Workflow:** `.github/workflows/functional-3.6.yml`

```bash
# Install dependencies
uv sync

# Set user
export EXABGP_DAEMON_USER=$(whoami)

# Run all tests
./qa/bin/functional-3.6 all
```

---

## Test Infrastructure Details

### Functional Test Script
**Location:** `qa/bin/functional`

#### Test Types:

**1. Parsing Tests:**
- Validates configuration files in `etc/exabgp/*.conf`
- Uses: `exabgp configuration validate -nrv <config_file>`
- All config files must parse without errors

**2. Encoding Tests:**
- Located in: `qa/encoding/*.ci`
- Tests BGP message encoding
- Runs ExaBGP with specific configs and validates output
- Tests communication between ExaBGP client and test BGP server
- Expected output: `successful` in stdout/stderr

**3. Decoding Tests:**
- Located in: `qa/decoding/*`
- Tests BGP message decoding
- Validates JSON output matches expected format
- Uses: `exabgp decode --<type> <packet>`

### Available Test Commands

```bash
# List all encoding tests
./qa/bin/functional encoding --list

# Get test identifiers (for CI)
./qa/bin/functional encoding --short-list

# List all decoding tests
./qa/bin/functional decoding --list

# List all parsing tests
./qa/bin/functional parsing --list

# Run specific test
./qa/bin/functional encoding <test_id>
./qa/bin/functional decoding <test_id>
./qa/bin/functional parsing <test_id>

# Show what a test would run (dry run)
./qa/bin/functional encoding --dry

# Debug a specific test
./qa/bin/functional encoding --client <test_id>
./qa/bin/functional encoding --server <test_id>
```

---

## Pre-Merge Checklist

⚠️ **MANDATORY - DO NOT SKIP ANY ITEMS** ⚠️

Before declaring code "fixed", "ready", "working", or "complete", you MUST verify ALL of the following:

- [ ] **Linting passes** on Python 3.12
  - [ ] flake8 shows no critical errors
  - [ ] ruff format and ruff check pass

- [ ] **Unit tests pass** on Python 3.8, 3.9, 3.10, 3.11, 3.12
  - [ ] All pytest tests pass
  - [ ] Coverage report generated

- [ ] **Functional tests pass** on Python 3.8-3.12
  - [ ] Parsing tests pass
  - [ ] All encoding tests pass (run sequentially)
  - [ ] All decoding tests pass

- [ ] **Legacy tests pass**
  - [ ] Python 3.6 functional tests pass

---

## Common Issues and Debugging

### Encoding Test Failures
If encoding tests fail:
1. Check the test configuration: `./qa/bin/functional encoding --list`
2. Run server and client separately to see actual output:
   ```bash
   # In terminal 1 (start FIRST):
   ./qa/bin/functional encoding --server <test_id>

   # In terminal 2 (start SECOND):
   ./qa/bin/functional encoding --client <test_id>
   ```
3. **For systematic debugging:** See `.claude/FUNCTIONAL_TEST_DEBUGGING_GUIDE.md`
   - Step-by-step process
   - Output interpretation
   - Troubleshooting common issues
   - Advanced techniques (packet capture, logging)

### Decoding Test Failures
If decoding tests fail:
1. Compare expected JSON vs actual output
2. Check the test file in `qa/decoding/` for expected format

### Parsing Test Failures
If parsing tests fail:
1. Check configuration syntax in `etc/exabgp/*.conf`
2. Run manually: `./sbin/exabgp configuration validate -nrv etc/exabgp/<config>.conf`

---

## Dependencies

### QA Requirements (`qa/requirements.txt`):
- ruff
- flake8
- coveralls
- nose
- psutil
- pytest
- pytest-cov

### Runtime Requirements:
- Python 3.8+ (main support)
- Python 3.6 (legacy support)
- psutil (for functional tests)

---

## CI Triggers

All workflows trigger on:
- **Push** to branches: `main`, `4.2`, `3.4`
- **Pull Request** to: `main`

---

## Quick Test Commands

### Minimal local testing:
```bash
# Linting
uv run flake8 . --max-line-length 120 --exclude src/exabgp/vendoring/ --exclude build/ --exclude site-packages --count --select=E9,F63,F7,F82 --show-source --statistics
uv run ruff format src && uv run ruff check src

# Unit tests
env exabgp_log_enable=false uv run pytest --cov --cov-reset ./tests/*_test.py

# Functional tests
./qa/bin/functional parsing
for test in $(./qa/bin/functional encoding --short-list); do ./qa/bin/functional encoding "$test"; done
./qa/bin/functional decoding
```

### Full CI simulation:
```bash
# Run all tests (Python 3.12+ required)
uv run pytest --cov --cov-reset ./tests/*_test.py
./qa/bin/functional parsing
for test in $(./qa/bin/functional encoding --short-list); do
  ./qa/bin/functional encoding "$test"
done
./qa/bin/functional decoding
```

---

## Notes

1. **Encoding tests must run sequentially** - They use network ports and can conflict if run in parallel
2. **Functional tests are comprehensive** - They test actual BGP protocol behavior, not just unit functionality
3. **Legacy support is important** - Python 3.6 tests ensure backward compatibility
4. **Test timeout is 60 seconds by default** - Configurable with `--timeout` flag

---

## Recent Changes

- **2024-11**: Added `--short-list` option to functional script for cleaner CI integration
- **2024-11**: Changed encoding tests to run sequentially instead of in parallel to fix CI flakiness
