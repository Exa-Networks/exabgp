# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🚨 MANDATORY REFACTORING PROTOCOL 🚨

**For ANY refactoring work (renaming methods, restructuring code, etc.):**

**YOU MUST follow `.claude/MANDATORY_REFACTORING_PROTOCOL.md`**

This protocol is mandatory due to a critical failure where 95 files were refactored and committed with 72 test failures, requiring a full revert and loss of all work.

**The protocol requires:**
1. **Pre-work:** Write explicit numbered steps with verification for each
2. **Execution:** Prove each step passes tests before proceeding (paste exact output)
3. **Pre-commit:** Run full test suite and paste output showing 0 failures

**READ THE PROTOCOL BEFORE ANY REFACTORING WORK.**

## Development Commands

**Testing:**
- **Check file descriptor limit before running tests:** `ulimit -n` (should be ≥64000)
- **If needed, increase limit:** `ulimit -n 64000`
- `env exabgp_log_enable=false pytest --cov --cov-reset ./tests/*_test.py` - Unit tests with coverage
- `env exabgp_log_enable=false pytest ./tests/unit/` - Faster unit tests without coverage
- `./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf` - Configuration validation test
- `./qa/bin/functional encoding` - Run all functional encoding tests (integration tests)
  - **What it does:** Spawns 72 pairs of ExaBGP client/server instances to test real BGP message exchange
  - **Output format:** Visual progress bar showing test status with letter identifiers (0-9, A-Z, a-z, α-κ)
  - **Success criteria:** All 72 tests should pass (100%), typically completes in <60 seconds
  - **Timeout:** Each test has 20 second timeout; timeouts indicate message encoding/decoding failures
  - **Test results:**
    - ✓ (passed) - Test completed successfully
    - ✖ (failed) - Test failed with error
    - ⏱ (timed out) - Test exceeded 20 second timeout (usually encoding/decoding bug)
    - ○ (skipped) - Test was skipped
  - **Summary output:** Shows counts and IDs of passed/failed/timed out/skipped tests
  - **Pass percentage:** Total % of tests that passed (should be 100%)
- `./qa/bin/functional encoding --list` - List all 72 tests with their letter identifiers and descriptions
- `./qa/bin/functional encoding --short-list` - Compact list of test identifiers only
- `./qa/bin/functional encoding <letter>` - Run specific test (e.g., `A`, `B`, `0`, `α`)
  - Use this to debug individual test failures
  - Test runs both client and server components
- `./qa/bin/functional encoding --server <letter>` - Run only server component of specific test
- `./qa/bin/functional encoding --client <letter>` - Run only client component of specific test
- `./qa/bin/parsing` - Configuration file parsing tests
- `./qa/bin/functional decoding` - Message decoding tests
- `python3 setup.py sdist bdist_wheel` - Build distribution packages
- `./release binary <target>` - Create self-contained zipapp binary

**Linting:**
- Uses `ruff` for linting and formatting (configured in pyproject.toml)
- `ruff format` - Format code (single quotes, 120 char lines)

## Testing Requirements

⚠️ **CRITICAL: NEVER DECLARE CODE "FIXED" WITHOUT RUNNING ALL TESTS** ⚠️

**MANDATORY REQUIREMENTS - Before declaring code "fixed", "ready", "working", or "complete":**

You MUST run ALL of these tests and they MUST all pass:
1. ✅ `ruff format src && ruff check src` - MUST pass with no errors
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/` - ALL unit tests MUST pass
3. ✅ `./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf` - Configuration validation MUST pass
4. ✅ `./qa/bin/functional encoding` - **Run ALL 72 tests** (NOT individual tests unless debugging)

**IMPORTANT:** When running functional encoding tests:
- Default: `./qa/bin/functional encoding` runs ALL 72 tests - this is what you should use
- Only specify test IDs (e.g., `./qa/bin/functional encoding A B C`) when debugging specific failures
- NEVER run just 1-4 tests and claim success - you must verify all 72 tests pass

**DO NOT skip any tests. DO NOT claim success without verification.**

See `.claude/docs/CI_TESTING_GUIDE.md` for complete pre-merge checklist.

All CI tests must pass:
  - Linting (ruff format + ruff check)
  - Unit tests (Python 3.8-3.12)
  - Functional tests (parsing, encoding, decoding)
  - Legacy tests (Python 3.6)
- **File descriptor limit:** Automatically set to ≥40000 by functional tests
  - The `./qa/bin/functional` tool automatically checks and increases ulimit if needed
  - If tests fail with resource errors, manually run: `ulimit -n 64000`
- **Encoding tests:** `./qa/bin/functional encoding` runs all tests in parallel (this is fine)
  - Before running: `killall -9 python` to clear leftover test processes and avoid port conflicts
  - Should complete in <20 seconds; if longer, remaining tests have failed
  - Use `--list` or `--short-list` to see available tests
  - If one test fails, run it independently with `--server <letter>` and `--client <letter>`
- When tests fail, investigate and fix - don't just re-run

**Quick test commands:**
- Unit tests: `env exabgp_log_enable=false pytest --cov --cov-reset ./tests/*_test.py`
- Configuration validation: `./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf`
- Encoding tests: `./qa/bin/functional encoding`
- Linting: `ruff format src && ruff check src`

## Git Workflow

**🚨 CRITICAL GIT RULES - NEVER VIOLATE THESE 🚨**

**NEVER COMMIT WITHOUT EXPLICIT USER REQUEST:**
- DO NOT commit after completing work unless user explicitly says "commit"
- DO NOT commit automatically after edits
- WAIT for user to review changes first
- User must explicitly say: "commit", "make a commit", "git commit", etc.

**NEVER PUSH WITHOUT EXPLICIT USER REQUEST:**
- DO NOT push automatically after committing
- DO NOT push even if user said "commit and push" for a PREVIOUS task
- EACH push requires explicit instruction for THAT SPECIFIC WORK
- User must explicitly say: "push", "git push", "push now", etc.

**When work is complete:**
1. Stop and report what was done
2. WAIT for user instruction
3. Only commit if user explicitly asks
4. Only push if user explicitly asks for that specific commit

## Repository State Verification

**CRITICAL: Always verify repository state before git operations**

Before ANY git operations (commit, rebase, amend, reset, merge):
1. **ALWAYS run `git status`** - Check for staged/unstaged changes
2. **ALWAYS run `git log --oneline -5`** - Check recent commit history
3. **ALWAYS verify user hasn't made manual changes** since last interaction
4. **NEVER assume** the repository is in the state you last saw it
5. **If unexpected changes detected:** STOP and ask user before proceeding

This prevents overwriting user's manual work and ensures awareness of repository state.

## Architecture Overview

**ExaBGP is a BGP implementation that does NOT manipulate the FIB (Forwarding Information Base).** Instead, it focuses on BGP protocol implementation and external process communication via JSON API.

**Core Components:**

1. **BGP Protocol Stack** (`src/exabgp/bgp/`):
   - `fsm.py` - BGP finite state machine (IDLE → ACTIVE → CONNECT → OPENSENT → OPENCONFIRM → ESTABLISHED)
   - `message/` - BGP message types (OPEN, UPDATE, NOTIFICATION, KEEPALIVE)
   - `message/open/capability/` - BGP capabilities (ASN4, MP-BGP, graceful restart, AddPath)
   - `message/update/attribute/` - Path attributes (AS_PATH, communities, AIGP, BGP-LS, SR)
   - `message/update/nlri/` - Network Layer Reachability Info for various address families

2. **Reactor Pattern** (`src/exabgp/reactor/`):
   - Event-driven architecture (NOT asyncio-based, custom implementation)
   - `peer.py` - BGP peer state and protocol handling
   - `network/` - TCP connection management
   - `api/` - External process communication via JSON

3. **Configuration System** (`src/exabgp/configuration/`):
   - Flexible parser supporting templates and neighbor inheritance
   - Built-in validation
   - YANG model support (`conf/yang/`)

4. **RIB Management** (`src/exabgp/rib/`):
   - Maintains routing information base
   - Tracks route changes and updates

## Key NLRI Support

ExaBGP supports extensive BGP address families:
- IPv4/IPv6 Unicast and Multicast
- VPNv4/VPNv6 (MPLS L3VPN)
- EVPN (Ethernet VPN)
- BGP-LS (Link State)
- FlowSpec (Traffic filtering)
- VPLS (Virtual Private LAN Service)
- MUP (Mobile User Plane)
- SRv6 (Segment Routing over IPv6)

## Testing Strategy

**Functional Tests** (`qa/`):
- Encoding/decoding validation using `.ci`/`.msg` file pairs
- Tests BGP message construction and parsing
- Configuration file validation against examples in `etc/exabgp/`

**Unit Tests** (`tests/`):
- pytest-based with coverage reporting
- Component-specific tests (BGP-LS, flow, NLRI parsing)

## Class Hierarchy and Architecture

**Core Design Patterns:**

1. **Registry/Factory Pattern** - The most pervasive pattern enabling dynamic object creation:
   - Messages: `@Message.register` with TYPE field identification
   - NLRI: `@NLRI.register(AFI.ipv4, SAFI.unicast)` for address families
   - Attributes: `@Attribute.register` with unique ID system
   - Capabilities: `@Capability.register` for BGP capability negotiation

2. **Template Method Pattern** - Base classes define algorithmic structure:
   - `Message.message()` interface with specialized implementations
   - `NLRI.pack_nlri()`/`unpack_nlri()` for route encoding/decoding
   - `Attribute` processing with common flag handling

3. **State Machine Pattern** - `FSM` class implements BGP finite state machine:
   - States: `IDLE → ACTIVE → CONNECT → OPENSENT → OPENCONFIRM → ESTABLISHED`
   - Event-driven state transitions with API notifications

4. **Observer Pattern** - Reactor coordinates peer states and external processes
5. **Strategy Pattern** - Different processing based on capabilities, address families, error types

**Key Class Hierarchies:**

```
Message (base, inherits from Exception)
├── Open (session establishment)
├── Update (route announcements/withdrawals)
├── Notification/Notify (error handling)
├── KeepAlive (session maintenance)
└── Operational (ExaBGP extensions)

NLRI (base) ← Family ← AFI/SAFI handling
├── INET (IPv4/IPv6 unicast/multicast)
├── Flow (Flowspec traffic filtering)
├── EVPN (Ethernet VPN)
├── VPN/MVPN (L3VPN routes)
└── BGPLS (Link State information)

Attribute (base with LRU caching)
├── Well-known mandatory (Origin, ASPath, NextHop)
├── Optional transitive (Community, ExtendedCommunity)
└── Multiprotocol extensions (MPRNLRI, MPURNLRI)
```

**Data Flow Architecture:**
- **Inbound**: Network → Reactor → Protocol → Message → NLRI/Attributes → API Processes
- **Outbound**: Configuration → RIB → Update Generation → Protocol → Network

**Extensibility Points:**
- New NLRI types: Inherit from `NLRI` and register with AFI/SAFI
- New attributes: Inherit from `Attribute` with unique ID
- New capabilities: Register with capability code
- API extensions: External processes extend functionality

**Error Handling Strategy:**
- `Message` inherits from `Exception` for error propagation
- Treat-as-withdraw for invalid attributes
- Connection reset for protocol violations
- Graceful restart mechanisms

## Development Notes

- **Python 3.8.1+ required** - maintains compatibility with older Python versions
- **No async/await** - uses custom reactor pattern predating asyncio adoption
- **External Process Model** - communicates with external applications via JSON API
- **Stateful BGP** - maintains full BGP state machine and RIB (unlike some route servers)
- **Extensive RFC Support** - implements modern BGP extensions (ASN4, IPv6, MPLS, SRv6, etc.)
- **Registry-based Plugin Architecture** - Clean extensibility through decorator registration
- **Performance Optimized** - LRU caching, lazy loading, event-driven I/O

## Configuration Examples

Example configurations in `etc/exabgp/` demonstrate:
- API integration (`api-*.conf`)
- Protocol features (`conf-*.conf`) 
- Parsing validation (`parse-*.conf`)

The QA functional tests use these configurations to validate both parsing and BGP message generation.
