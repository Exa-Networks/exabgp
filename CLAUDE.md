# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working with this repository.

---

## 🚨 SESSION START PROTOCOL - READ FIRST 🚨

**CRITICAL: These are ACTIVE RULES, not reference docs. You MUST apply them to EVERY response.**

**Read these files as RULES you will FOLLOW, not just information to absorb:**

1. `.claude/VERIFICATION_DISCIPLINE.md` - Verify before claiming (read FIRST)
   - **Rule:** Never claim success without pasting command output
   - **Apply:** Before ANY claim, run command, paste output

2. `.claude/COMMUNICATION_STYLE.md` - Terse, direct communication
   - **Rule:** No politeness, no hedging, no verbosity
   - **Apply:** Every response - check word count, cut explanations

3. `.claude/EMOJI_GUIDE.md` - Emoji usage
   - **Rule:** Start EVERY line with emoji (✅/❌/📁/🧪/etc)
   - **Apply:** Before sending response, verify every status line starts with emoji

4. `.claude/GIT_VERIFICATION_PROTOCOL.md` - Git state verification
   - **Rule:** Never git operation without fresh `git status` pasted
   - **Apply:** Before ANY git command, run and paste verification

5. `.claude/MANDATORY_REFACTORING_PROTOCOL.md` - Refactoring verification
   - **Rule:** One function at a time, paste proof at every step
   - **Apply:** When refactoring, stop after each function, paste test output

6. `.claude/ERROR_RECOVERY_PROTOCOL.md` - Slow down after mistakes
   - **Rule:** After mistake, SLOW DOWN, re-read protocol
   - **Apply:** When corrected, stop, identify violated protocol, re-read

7. `.claude/CODING_STANDARDS.md` - Python 3.10+, BGP APIs
   - **Rule:** Union[int, str] NOT int | str, negotiated param required
   - **Apply:** Before writing code, check syntax compatibility

8. `.claude/TESTING_DISCIPLINE.md` - Never claim success without testing
   - **Rule:** ./qa/bin/test_everything before "fixed"/"ready"/"complete"
   - **Apply:** Before claiming done, run all tests, paste output

9. `.claude/PLANNING_GUIDE.md` - Project planning
10. `.claude/CI_TESTING.md` - Testing requirements
11. `.claude/FUNCTIONAL_TEST_DEBUGGING_GUIDE.md` - Debug test failures

**HOW TO READ: For each protocol, extract the SPECIFIC RULE you will apply to your NEXT response.**

**IMMEDIATELY AFTER reading protocols, EXECUTE these commands (not later - NOW):**

```bash
# 1. Git state check
git status && git diff && git diff --staged

# 2. Backport review - MANDATORY AT SESSION START
LAST_HASH=$(grep "Last reviewed commit" .claude/BACKPORT.md | awk '{print $NF}')
echo "=== Commits since last backport review ($LAST_HASH) ==="
git log $LAST_HASH..HEAD --oneline
```

**STOP and report:**
- If modified/staged files: ASK user how to handle
- If new commits since backport review: Report them, note if any are bug fixes

**Self-check after reading:**
- [ ] Can I state the emoji rule? (Start every line with emoji)
- [ ] Can I state the verification rule? (Paste command output before claiming)
- [ ] Can I state the git rule? (Fresh git status before operations)
- [ ] Did I RUN the backport check above? (Not just read about it)
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

### Testing

```bash
# ALL tests (required before declaring success)
./qa/bin/test_everything

# Individual (for debugging only)
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
./qa/bin/functional encoding  # ALL 72 tests
./qa/bin/functional decoding
./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf

# Debug specific encoding test
./qa/bin/functional encoding --list  # List all tests
./qa/bin/functional encoding <letter>  # Run one test

# Inspect test configuration (view all test files)
env EDITOR=cat ./qa/bin/functional encoding --edit <letter>

# Debug in separate terminals
./qa/bin/functional encoding --server <letter>  # Terminal 1
./qa/bin/functional encoding --client <letter>  # Terminal 2
```

**See:**
- `.claude/FUNCTIONAL_TEST_DEBUGGING_GUIDE.md` for systematic debugging
- `.claude/FUNCTIONAL_TEST_EDIT.md` for inspecting test configurations

### Decode BGP Messages

```bash
./sbin/exabgp decode -c <config> "<hex>"
# Use when server shows "unexpected message"
# IMPORTANT: Use -c with same config as test (from qa/encoding/<test>.ci)
```

### Linting

```bash
ruff format src  # Single quotes, 120 char
ruff check src   # Must pass
```

### Port Conflicts

```bash
killall -9 python  # Clear leftover test processes
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

**Python 3.10+ ONLY:**
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
- **Protocols:** 13 session-start files (VERIFICATION_DISCIPLINE.md, etc.)
- **Codebase reference:** exabgp/ - architecture, patterns, BGP mappings
- **Reference:** FUNCTIONAL_TEST_ARCHITECTURE.md, FILE_NAMING_CONVENTIONS.md
- **Documentation:** docs/ - projects, reference, plans, wip, archive

---

## Quick Checklist

Before declaring success:
- [ ] Read all 11 protocol files
- [ ] `./qa/bin/test_everything` passes
- [ ] `git status` reviewed
- [ ] User approval for commit/push
- [ ] Python 3.10+ syntax
- [ ] No asyncio introduced

---

**Updated:** 2025-11-26
