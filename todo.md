# ExaBGP Quality Improvement TODO

**Generated:** 2025-11-24
**Updated:** 2025-11-24 (peer.py XXX/FIXME resolved)
**Stats:** 348 Python files, 54,991 LOC, 52 test files

---

## High Priority

### Exception Handling - COMPLETE

**Original count:** 53 `except Exception:` cases
**Fixed:** 31 cases replaced with specific exceptions
**Kept broad:** 22 cases (appropriate for top-level handlers, readline safety, callbacks)

#### COMPLETED:
- [x] Phase 0: Created 11 exception classes + 2 test files
  - ProcessError subclasses in `reactor/api/processes.py`
  - CLIError hierarchy in NEW `application/error.py`
  - ParsingError subclasses in `configuration/core/error.py`
  - Tests in `tests/unit/test_exception_handling.py`, `tests/unit/configuration/test_parser_exceptions.py`
- [x] Phase 1: 6 low-risk parsing changes (peer.py, neighbor/parser.py, flow/parser.py, json.py)
- [x] Phase 2: 5 configuration/check.py changes
- [x] Phase 3: 7 processes.py async cleanup changes
- [x] Phase 4: Application layer (unixsocket.py, cli.py, pipe.py)
  - unixsocket.py: 9 → `OSError` (1 kept as top-level handler)
  - cli.py: 11 → specific (10 kept for readline safety, callbacks, top-level)
  - pipe.py: 1 → `OSError` (1 kept as top-level handler)
- [x] Phase 5: Peripheral (run.py, flow.py, server.py)
  - run.py: 4 → `OSError` (1 kept as batch wrapper)
  - flow.py: 3 → `OSError`/`subprocess.SubprocessError` (1 kept as exit handler)
  - server.py: 1 → `OSError` (1 kept as Reactor crash handler)
- [x] Phase 6: High-risk reactor/loop.py
  - loop.py: 2 → `OSError`/`asyncio.CancelledError` (1 kept for task.result())

#### SKIPPED (appropriate):
- Vendored files (objgraph.py, profiler.py, gcdump.py)
- Top-level crash handlers that need to catch everything
- Readline completion (must not crash)
- User-provided callbacks (can raise anything)

**Verification:** `./qa/bin/test_everything` - ALL 8 SUITES PASS

### Large File Refactoring

- [x] **port.py (4,982 → 89 lines)** - `src/exabgp/protocol/ip/port.py` ✅ DONE
  - [x] Extracted port names dictionary to `port_data.json` (4,931 lines)
  - [x] Removed dead code
  - [x] Clean Port class with lazy loading

- [x] **cli.py (2,595 → 1,940 lines)** - `src/exabgp/application/cli.py` ✅ PARTIAL
  - [x] Extracted Colors class to `cli/colors.py` (57 lines)
  - [x] Extracted PersistentSocketConnection to `cli/persistent_connection.py` (609 lines)
  - [ ] Split command execution from REPL handling (future)

- [ ] **peer.py (1,289 lines)** - `src/exabgp/reactor/peer.py` ✅ XXX/FIXME DONE
  - [x] Address XXX/FIXME comments at lines 437, 604-605, 703, 1115, 1151
    - Removed stale ord/chr comment (line 437) - migration complete
    - Updated ProcessError comment (lines 604-606) - documented broken() handling
    - Updated proto comment (line 703) - documented peer/protocol separation
    - Updated process restart comments (lines 1115, 1151) - documented respawning
    - Kept UnicodeDecodeError defensive code (lines 184-188) - needed for raw network data
  - [ ] Extract state transition logic (future)
  - [ ] Improve exception handling patterns (future)

### Type Safety (491 type ignores)

- [ ] Audit and fix type annotation issues instead of suppressing
- [ ] Start with modules having >20 type ignore comments
- [ ] Add mypy configuration for stricter typing
- [ ] Add `py.typed` marker file for PEP 561 compliance

### Security

- [ ] Audit `eval/exec/compile` usage in:
  - [ ] `src/exabgp/configuration/neighbor/parser.py`
  - [ ] `src/exabgp/cli/validator.py`
  - [ ] `src/exabgp/cli/completer.py`
  - [ ] `src/exabgp/environment/parsing.py`
- [ ] Replace with safer alternatives (ast.literal_eval)
- [ ] Add input validation layer in configuration parsers
- [ ] Sanitize error messages for external-facing APIs

---

## Medium Priority

### Test Coverage Gaps

- [ ] Add tests for reactor components:
  - [ ] `src/exabgp/reactor/protocol.py` (795 lines)
  - [ ] `src/exabgp/reactor/loop.py` (821 lines)
  - [ ] `src/exabgp/reactor/network/connection.py` (395 lines)
- [ ] Add configuration validation tests for malformed configs
- [ ] Add API response tests for `src/exabgp/reactor/api/response/json.py`
- [ ] Add property-based tests using hypothesis

### Architecture

- [ ] Eliminate circular dependencies:
  - [ ] `src/exabgp/bgp/fsm.py` ↔ `src/exabgp/reactor/peer.py`
  - [ ] `src/exabgp/bgp/message/update/__init__.py` (deferred Response import)
- [ ] Decouple reactor from configuration parsing details
- [ ] Document async migration roadmap

### Global State (8 files)

- [ ] Refactor global statements to class/instance attributes:
  - [ ] `src/exabgp/util/dns.py`
  - [ ] `src/exabgp/bgp/neighbor.py`
  - [ ] `src/exabgp/reactor/api/` (3 files)
  - [ ] `src/exabgp/environment/environment.py`
  - [ ] `src/exabgp/cli/main.py`

### Documentation

- [ ] Add module docstrings to ~200 files lacking documentation
- [ ] Priority files:
  - [ ] `src/exabgp/reactor/protocol.py`
  - [ ] `src/exabgp/reactor/network/connection.py`
  - [ ] `src/exabgp/bgp/message/update/nlri/flow.py`
- [ ] Add method documentation for public APIs
- [ ] Create `.claude/exabgp/ASYNC_ARCHITECTURE.md`

---

## Low Priority / Quick Wins

### Code Cleanup

- [ ] Replace 90 `print()` calls with logger calls
- [ ] Standardize string formatting to f-strings
- [ ] Remove commented-out code
- [ ] Add named constants for magic numbers

### Type Annotations

- [ ] Add return type annotations to 140 files missing them
- [ ] Document type annotation requirements in CODING_STANDARDS.md

---

## Summary Table

| Priority | Issue | Files | Complexity | Impact | Status |
|----------|-------|-------|-----------|--------|--------|
| 1 | Exception handling | Across codebase | Low | High | **DONE** |
| 2 | Refactor port.py (4982 → 89 lines) | `protocol/ip/port.py` | Low | High | **DONE** |
| 3 | Add missing return type annotations | 140 files | Medium | High | TODO |
| 4 | Split cli.py (2595 → 1940 lines) | `application/cli.py` | High | High | **PARTIAL** |
| 5 | Eliminate circular dependencies | `bgp/fsm.py`, `reactor/api/` | High | Medium | TODO |
| 6 | Add test coverage for reactor | `tests/unit/` | Medium | Medium | TODO |
| 7 | Replace 90 print() calls | Across codebase | Low | Medium | TODO |
| 8 | Add module docstrings | 200 files | Low | Medium | TODO |
| 9 | Add input validation layer | `configuration/` | Medium | High | TODO |

---

## Strengths (No Action Required)

- Well-organized module structure (clear separation of bgp/, reactor/, configuration/)
- Comprehensive test suite (52 test files, 72 functional tests)
- Dual async/generator mode flexibility
- Registry pattern for extensibility (Message, NLRI, Attribute registration)
- Good type hints in 203 files (58%)
