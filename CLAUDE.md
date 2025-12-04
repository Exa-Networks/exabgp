# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working with this repository.

---

## 🚨 SESSION START PROTOCOL - READ FIRST 🚨

**CRITICAL: These are ACTIVE RULES, not reference docs. You MUST apply them to EVERY response.**

### MANDATORY FIRST ACTION

**Read `.claude/ESSENTIAL_PROTOCOLS.md` (~5 KB)**

This single file contains ALL core rules:
- Verification before claiming
- Communication style
- Testing requirements
- Coding standards essentials
- Session start workflow
- Contextual protocol loading guide

**Token savings:** 86% reduction (5 KB vs 37 KB)

### Contextual Loading

**After reading ESSENTIAL_PROTOCOLS.md, load additional protocols based on task:**

| Task Type | Load Protocol |
|-----------|---------------|
| Git work (commit/push) | GIT_VERIFICATION_PROTOCOL.md |
| Refactoring code | MANDATORY_REFACTORING_PROTOCOL.md |
| Test failures | FUNCTIONAL_TEST_DEBUGGING_GUIDE.md |
| Error recovery | ERROR_RECOVERY_PROTOCOL.md |
| Creating docs | DOCUMENTATION_PLACEMENT_GUIDE.md |

**Decision tree:** See `.claude/README.md` "What Do You Want to Do?" section

**IMMEDIATELY AFTER reading protocols, EXECUTE these commands (not later - NOW):**

```bash
# 1. Git state check
git status && git diff && git diff --staged

# 2. Backport review - MANDATORY AT SESSION START IF THE .claude/BACKPORT.md is older than a week
LAST_HASH=$(grep "Last reviewed commit" .claude/BACKPORT.md | awk '{print $NF}')
echo "=== Commits since last backport review ($LAST_HASH) ==="
git log $LAST_HASH..HEAD --oneline

# 3. Plan state check
ls -la plan/
```

**THEN use AskUserQuestion tool to ask about any issues found:**

If modified/staged files exist OR new commits since backport review, use AskUserQuestion with questions like:

```
Question 1 (if modified files found):
  header: "Modified files"
  question: "Found N modified files: [list]. How should I handle them?"
  options:
    - label: "Continue work", description: "These are my in-progress changes, continue working on them"
    - label: "Discard changes", description: "Reset these files to HEAD"
    - label: "Review first", description: "Show me the diff before deciding"

Question 2 (if new commits since backport review):
  header: "Backport review"
  question: "N commits since last backport review. Update reviewed hash?"
  options:
    - label: "Yes, update", description: "All commits are typing/refactoring/docs, no bug fixes"
    - label: "Review commits", description: "Show me the commits to check for bug fixes"

Question 3 (if plan files exist):
  header: "Active plans"
  question: "Active plans found: [list with status]. Which plan are we working on?"
  options:
    - label: "[plan name]", description: "Continue work on this plan"
    - label: "None", description: "Not working on any plan today"
```

**Self-check after reading:**
- [ ] Can I state the emoji rule? (Start every line with emoji)
- [ ] Can I state the verification rule? (Paste command output before claiming)
- [ ] Can I state the git rule? (Fresh git status before operations)
- [ ] Did I RUN the backport check above? (Not just read about it)
- [ ] Did I RUN the plan state check above? (Not just read about it)
- [ ] Will I APPLY these to my next response? (Not just "know" them)

**THEN complete:** `.claude/PRE_FLIGHT_CHECKLIST.md` before starting work.

**🐛 BACKPORT CHECK:** After fixing ANY bug, check `.claude/BACKPORT.md` and add entry if the fix applies to stable branches (5.0). Ask user if unsure whether a fix needs backporting.

**⚠️ BEFORE CREATING ANY DOCUMENTATION:** Read `.claude/DOCUMENTATION_PLACEMENT_GUIDE.md` to know where to put it.

---

## 🚨 CRITICAL TESTING REQUIREMENT 🚨

**NEVER declare code "fixed"/"ready"/"working"/"complete" without running ALL tests:**

```bash
./qa/bin/test_everything  # ALL 6 test suites, exits on first failure
```

**DO NOT:**
- Skip tests
- Run partial tests and claim success
- Claim "fixed" without verification

**See:** `.claude/CI_TESTING.md` for complete checklist.

---

## Development Commands

### Setup

**First time setup:**
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

**Update dependencies:**
```bash
uv lock                          # Update lock file
./qa/bin/sync_requirements.sh    # Sync qa/requirements.txt
```

### Testing

```bash
# ALL tests (required before declaring success)
./qa/bin/test_everything

# Individual (for debugging only)
uv run ruff format src && uv run ruff check src
env exabgp_log_enable=false uv run pytest ./tests/unit/
./qa/bin/functional encoding  # ALL 72 tests
./qa/bin/functional decoding
./sbin/exabgp configuration validate -nrv ./etc/exabgp/conf-ipself6.conf

# Debug specific encoding test
./qa/bin/functional encoding --list  # List all tests
./qa/bin/functional encoding <letter>  # Run one test

# Inspect test configuration (view all test files)
env EDITOR=cat ./qa/bin/functional encoding --edit <letter>

# Debug in separate terminals
./qa/bin/functional encoding --server <letter>  # Terminal 1
./qa/bin/functional encoding --client <letter>  # Terminal 2

# Capture run logs for intermittent failures
./qa/bin/functional encoding <letter> --save /tmp/runs/
# Logs include: timing, message hashes, match/mismatch status
# Compare logs from multiple runs to diagnose intermittent issues

# Stress test - run N times and report statistics
./qa/bin/functional encoding <letter> --stress 10
# Shows pass/fail per run, timing stats (min/avg/max/stddev)

# Verbose mode - show full daemon/client output for each test
./qa/bin/functional encoding -v
# Shows ALL output (no truncation) on failure, useful for debugging
# Filters only keepalive timer spam, all other output preserved

# Quiet mode - minimal output, verbose only on failure
./qa/bin/functional encoding -q
# Single line on success: "passed N/N (100.0%)"
# Full verbose output on failure with debug hints
```

**See:**
- `.claude/FUNCTIONAL_TEST_DEBUGGING_GUIDE.md` for systematic debugging
- `.claude/FUNCTIONAL_TEST_EDIT.md` for inspecting test configurations

### Encode/Decode BGP Messages

```bash
# ENCODE: Convert route config to hex UPDATE message
./sbin/exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4"
./sbin/exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4 as-path [65000 65001]"
./sbin/exabgp encode -f "ipv6 unicast" "route 2001:db8::/32 next-hop 2001:db8::1"
./sbin/exabgp encode -n "route 10.0.0.0/24 next-hop 1.2.3.4"  # NLRI only

# DECODE: Parse hex message to JSON
./sbin/exabgp decode "<hex>"                    # Decode UPDATE
./sbin/exabgp decode -c <config> "<hex>"        # With config context
echo "<hex>" | ./sbin/exabgp decode             # From stdin
./sbin/exabgp encode "route ..." | ./sbin/exabgp decode  # Round-trip

# Use decode when server shows "unexpected message"
# IMPORTANT: Use -c with same config as test (from qa/encoding/<test>.ci)
```

### Linting

```bash
uv run ruff format src  # Single quotes, 120 char
uv run ruff check src   # Must pass
```

### Port Conflicts

```bash
killall -9 Python  # macOS uses capital P
```

---

## Git Workflow

**🚨 CRITICAL RULES 🚨**

**NEVER COMMIT without explicit user request:**
- User must say: "commit", "make a commit", "git commit"
- DO NOT commit after completing work
- WAIT for user review

**NEVER PUSH without explicit user request:**
- Each push requires explicit instruction for THAT work
- User must say: "push", "git push", "push now"

**When work complete:**
1. Stop, report what was done
2. WAIT for user instruction
3. Only commit if explicitly asked
4. Only push if explicitly asked

**Before ANY git operation:**
```bash
git status && git log --oneline -5
```

Verify no unexpected changes. If found: STOP and ask user.

**See:** `.claude/GIT_VERIFICATION_PROTOCOL.md` for complete requirements.

---

## Architecture Overview

**ExaBGP:** BGP protocol implementation + JSON API. Does NOT manipulate FIB.

**Core Components:**

1. **BGP Protocol** (`src/exabgp/bgp/`):
   - `fsm.py` - State machine (IDLE → ESTABLISHED)
   - `message/` - OPEN, UPDATE, NOTIFICATION, KEEPALIVE
   - `message/update/` - Attributes, NLRI, address families

2. **Reactor** (`src/exabgp/reactor/`):
   - Event-driven (custom, not asyncio)
   - `peer.py` - BGP peer handling
   - `api/` - External process communication

3. **Configuration** (`src/exabgp/configuration/`):
   - Flexible parser, templates, validation

4. **RIB** (`src/exabgp/rib/`):
   - Routing information base

**Supported Address Families:**
IPv4/IPv6, VPNv4/v6, EVPN, BGP-LS, FlowSpec, VPLS, MUP, SRv6

**Design Patterns:**
- Registry/Factory: `@Message.register`, `@NLRI.register`
- Template Method: `pack_nlri()`, `unpack_nlri()`
- State Machine: BGP FSM
- Observer: Reactor coordinates peers

**Data Flow:**
- Inbound: Network → Reactor → Message → NLRI/Attributes → API
- Outbound: Config → RIB → Update → Protocol → Network

---

## 📚 Essential Codebase References

**MUST READ when starting work on new features or major changes:**

1. **`.claude/exabgp/CODEBASE_ARCHITECTURE.md`** - Complete directory structure, module purposes, file locations
   - **Read when:** Need to find where specific functionality lives
   - **Contains:** Directory tree, file sizes, core vs peripheral modules

2. **`.claude/exabgp/DATA_FLOW_GUIDE.md`** - How data moves through the system
   - **Read when:** Adding features, debugging message flow
   - **Contains:** Inbound/outbound pipelines, parsing/serialization, RIB operations

3. **`.claude/exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md`** - How to extend ExaBGP
   - **Read when:** Adding NLRI types, attributes, capabilities, API commands
   - **Contains:** Step-by-step patterns, required file changes, common pitfalls

4. **`.claude/exabgp/BGP_CONCEPTS_TO_CODE_MAP.md`** - BGP RFC concepts to code locations
   - **Read when:** Implementing BGP features from RFCs
   - **Contains:** AFI/SAFI mappings, message types, attribute codes, capability codes

5. **`.claude/exabgp/CRITICAL_FILES_REFERENCE.md`** - Most frequently modified files
   - **Read when:** Need quick navigation to important files
   - **Contains:** Top 10 files, "change X update Y" table, stable interfaces

6. **`.claude/exabgp/CLI_COMMANDS.md`** - Complete CLI command reference
   - **Read when:** Working with CLI, adding commands, understanding syntax
   - **Contains:** All 43 commands, syntax, examples, neighbor selectors, display modes

7. **`.claude/exabgp/CLI_SHORTCUTS.md`** - CLI shortcut reference
   - **Read when:** Working with CLI, understanding shortcuts
   - **Contains:** Single/multi-letter shortcuts, context rules, expansion examples

8. **`.claude/exabgp/CLI_IMPLEMENTATION.md`** - CLI internal architecture
   - **Read when:** Modifying CLI code, adding completion features
   - **Contains:** 4 main classes, command flow, tab completion, threading model

9. **`.claude/exabgp/UNIX_SOCKET_API.md`** - Unix socket API protocol
   - **Read when:** Working with API, socket communication
   - **Contains:** Protocol spec, connection handshake, response parsing

10. **`.claude/exabgp/NEIGHBOR_SELECTOR_SYNTAX.md`** - Neighbor selector grammar
    - **Read when:** Working with neighbor-targeted commands
    - **Contains:** Selector syntax, matching algorithm, usage patterns

11. **`.claude/exabgp/ENVIRONMENT_VARIABLES.md`** - Environment variables reference
    - **Read when:** Working with configuration, environment variables, reactor/daemon/logging/API settings
    - **Contains:** All exabgp_* variables, tcp.attempts, bgp.*, daemon.*, log.*, api.*, reactor.*, cache.*, debugging options

**Quick reference:**
- Adding NLRI type → Read #3, then #1
- Understanding message flow → Read #2
- Finding where BGP concept lives → Read #4
- Starting new feature → Read #1, #3, #5
- Working with CLI → Read #6, #7, #8
- Adding CLI commands → Read #6, #8, #3
- Understanding API protocol → Read #9, #10
- Environment variables/configuration → Read #11

---

## AsyncIO Support

**Dual-mode:** Generator (default) vs Async (opt-in)

**Both are async I/O** - differ in syntax only:
- Generator: `yield` + `select.poll()`
- Async: `await` + asyncio

**Current:** Phase 2 (Production Validation)

**Enable async:**
```bash
exabgp_reactor_asyncio=true ./sbin/exabgp config.conf
```

**Test parity:** 100% (72/72 functional, 1376/1376 unit)

**See:** `.claude/asyncio-migration/` for details.

---

## Key Requirements

**Python 3.12+ ONLY:**
- Prefer `int | str` over `Union[int, str]`
- Prefer `str | None` over `Optional[str]`
- See `.claude/CODING_STANDARDS.md`

**BGP Method APIs (STABLE - DO NOT CHANGE):**
```python
def pack(self, negotiated: Negotiated) -> bytes: pass
```
Unused `negotiated` parameters are OK and EXPECTED.

**No asyncio introduction** - uses custom reactor
**No FIB manipulation** - BGP protocol only

**Environment Variables:**
- See `.claude/exabgp/ENVIRONMENT_VARIABLES.md` for all configuration options (tcp.*, bgp.*, daemon.*, log.*, api.*, reactor.*, etc.)

---

## Directory Structure

`.claude/` - Core protocols and codebase documentation:
- **Protocols:** 14 session files (ESSENTIAL_PROTOCOLS.md, SESSION_END_CHECKLIST.md, etc.)
- **Codebase reference:** exabgp/ - architecture, patterns, BGP mappings
- **Reference:** FUNCTIONAL_TEST_ARCHITECTURE.md, FILE_NAMING_CONVENTIONS.md
- **Documentation:** docs/ - projects, reference, plans, wip, archive

`plan/` - Implementation plans and active work:
- **Naming:** See plan/README.md for conventions
- **Template:** Includes Progress, Failures, Blockers, Resume Point sections

---

## Quick Checklist

Before declaring success:
- [ ] Read ESSENTIAL_PROTOCOLS.md
- [ ] `./qa/bin/test_everything` passes
- [ ] `git status` reviewed
- [ ] Plan files updated (if working on a plan)
- [ ] User approval for commit/push
- [ ] Python 3.12+ syntax
- [ ] No asyncio introduced

Before ending session:
- [ ] Run SESSION_END_CHECKLIST.md (mandatory)
- [ ] Update plan files with progress/failures/resume point

---

**Updated:** 2025-12-04
