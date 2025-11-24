# Claude AI Assistant Resources

Documentation and protocols for Claude Code interactions with ExaBGP.

---

## 🚨 START OF EVERY SESSION - READ ALL PROTOCOLS 🚨

**⚠️ CRITICAL: You have NO memory between sessions ⚠️**

**MANDATORY FIRST ACTION: Read ALL Core Protocols listed below using the Read tool.**

**DO NOT:**
- Skip any protocols ("I'll read them later")
- Assume you remember them from previous sessions
- Start work before reading ALL protocols
- Claim you "understand the requirements" without reading

**DO:**
- Use the Read tool to read EVERY protocol file below
- Read them EVERY session (no exceptions)
- Read them BEFORE doing any other work
- Read them in parallel for efficiency

**Then check git state:**
```bash
git status
git diff
git diff --staged
```

If ANY files modified/staged: ASK user how to handle before starting work.

---

## Core Protocols (ALL MANDATORY - READ EVERY SESSION)

| File | Purpose | Size |
|------|---------|------|
| **VERIFICATION_DISCIPLINE.md** | NEVER claim success without pasting proof | 1.7 KB |
| **MANDATORY_REFACTORING_PROTOCOL.md** | Step-by-step verification for ALL refactoring | 3.2 KB |
| **ERROR_RECOVERY_PROTOCOL.md** | NEVER rush after mistakes - slow down and follow protocols | 2.9 KB |
| **GIT_VERIFICATION_PROTOCOL.md** | NEVER make git claims without fresh verification | 3.1 KB |
| **CODING_STANDARDS.md** | Python 3.8+ compatibility, type annotations, BGP APIs | 3.9 KB |
| **TESTING_DISCIPLINE.md** | NEVER claim success without testing ALL | 2.1 KB |
| **COMMUNICATION_STYLE.md** | Terse, direct communication. Use agents. | 3.9 KB |
| **EMOJI_GUIDE.md** | Systematic emoji usage for clarity | 1.8 KB |
| **PLANNING_GUIDE.md** | Standards for project planning docs | 1.6 KB |
| **CI_TESTING.md** | Complete testing requirements and commands | 1.1 KB |
| **FUNCTIONAL_TEST_DEBUGGING_GUIDE.md** | Systematic process for debugging encoding test failures | 4.2 KB |
| **PRE_FLIGHT_CHECKLIST.md** | Session start checklist | 0.9 KB |
| **DOCUMENTATION_PLACEMENT_GUIDE.md** | Where to put docs (CRITICAL for creating docs) | 7.3 KB |

**Total core protocols: ~37 KB**

---

## Directory Structure

```
.claude/
├── # PROTOCOLS (how we work - READ EVERY SESSION)
├── VERIFICATION_DISCIPLINE.md
├── COMMUNICATION_STYLE.md
├── GIT_VERIFICATION_PROTOCOL.md
├── MANDATORY_REFACTORING_PROTOCOL.md
├── ERROR_RECOVERY_PROTOCOL.md
├── CODING_STANDARDS.md
├── TESTING_DISCIPLINE.md
├── PLANNING_GUIDE.md
├── CI_TESTING.md
├── FUNCTIONAL_TEST_DEBUGGING_GUIDE.md
├── PRE_FLIGHT_CHECKLIST.md
├── EMOJI_GUIDE.md
├── DOCUMENTATION_PLACEMENT_GUIDE.md    # ⚠️ READ BEFORE CREATING ANY DOC
│
├── # CODEBASE REFERENCE (how to use/modify codebase)
├── exabgp/
│   ├── CODEBASE_ARCHITECTURE.md        # Where everything is
│   ├── DATA_FLOW_GUIDE.md              # How data flows
│   ├── REGISTRY_AND_EXTENSION_PATTERNS.md  # How to extend
│   ├── BGP_CONCEPTS_TO_CODE_MAP.md     # BGP concepts → code
│   └── CRITICAL_FILES_REFERENCE.md     # Most important files
│
├── # DOCUMENTATION (all project docs)
├── docs/
│   ├── README.md
│   ├── projects/               # Completed work
│   │   ├── asyncio-migration/
│   │   ├── type-annotations/
│   │   ├── pack-method-standardization/
│   │   └── ...
│   ├── wip/                    # Active work in progress
│   │   └── type-annotations/
│   ├── reference/              # API reference
│   │   └── NEIGHBOR_SELECTOR_SYNTAX.md
│   ├── plans/                  # Future plans
│   └── archive/                # Superseded experiments
│
├── # REFERENCE DOCS
├── FUNCTIONAL_TEST_ARCHITECTURE.md
├── FILE_NAMING_CONVENTIONS.md
│
└── # SPECIAL
    ├── README.md                        # This file
    └── settings.local.json
```

**⚠️ BEFORE CREATING ANY DOC:** Read `DOCUMENTATION_PLACEMENT_GUIDE.md`

---

## Active Work (`docs/wip/`)

Active development projects. Completed work moves to `docs/projects/`.

### CLI Interactive Enhancement (2025-11-20)
**Status:** ✅ Complete with comprehensive testing
**Progress:** Implementation + 189 new tests, all passing

**Files:**
- CLI_WORK_SUMMARY.md - Quick overview (READ THIS FIRST)
- CLI_INTERACTIVE_ENHANCEMENT_STATUS.md - Complete implementation guide
- CLI_TESTING_GUIDE.md - Test cases and debugging
- CLI_TESTING_COMPLETE.md - Test coverage report

**Code changes:**
- `src/exabgp/reactor/api/command/registry.py` - NEW: Command introspection
- `src/exabgp/application/shortcuts.py` - NEW: Shared shortcut expansion
- `sbin/exabgp-doc-generator` - NEW: Wiki documentation generator
- `src/exabgp/application/cli.py` - MODIFIED: Uses shared shortcuts
- `src/exabgp/application/cli_interactive.py` - MODIFIED: Enhanced completion

**Test files:**
- `tests/unit/test_shortcuts.py` - 71 tests for shortcut expansion
- `tests/unit/test_command_registry.py` - 59 tests for registry introspection
- `tests/unit/test_completer.py` - 59 tests for completion logic

**Features:**
- Dynamic command discovery (no hardcoded lists)
- Neighbor IP completion (queries running ExaBGP)
- AFI/SAFI completion for eor/route-refresh
- Route keyword completion (next-hop, community, etc.)
- Neighbor filter completion (local-ip, local-as, etc.)
- Refactored shortcuts (eliminated 120 lines duplication)

**Testing:** ✅ 1613/1613 tests pass (1424 existing + 189 new)

### Type Annotations (`docs/wip/type-annotations/`)
**Status:** Phase 3 - MyPy error reduction
**Progress:** 605 errors (47% ↓ from 1,149 baseline)

**Files:**
- README.md - Project overview
- MYPY_STATUS.md - Current error analysis
- PROGRESS.md - Phase tracking
- See full structure in `docs/wip/type-annotations/`

**Historical docs:** `docs/projects/type-annotations/` (early planning)

---

## Completed Projects (`docs/projects/`)

**All completed work is in:** `.claude/docs/projects/`

Major completed projects:
- AsyncIO Migration (100% test parity)
- Pack Method Standardization
- RFC Alignment
- Testing Improvements
- CLI Interactive Enhancement

**See:** `.claude/docs/projects/README.md` for full project list

---

## File Size Policy

**Active files MUST stay under:**
- Core protocols: < 5 KB
- Reference docs: < 8 KB
- Status/progress: < 5 KB
- READMEs: < 3 KB

**If exceeding: compress or archive**

---

## Quick Start

**At session start:**
1. Read ALL Core Protocols above (ALL mandatory, see top of file)
2. Check `git status`, `git diff`, `git diff --staged`
3. If files modified: ASK user before proceeding

**For any code changes:**
1. Make changes following CODING_STANDARDS.md
2. Follow MANDATORY_REFACTORING_PROTOCOL.md if refactoring
3. Run ALL tests per TESTING_DISCIPLINE.md
4. Only THEN claim success

**Remember:**
- COMMUNICATION_STYLE.md + EMOJI_GUIDE.md apply to EVERY response
- GIT_VERIFICATION_PROTOCOL.md applies to EVERY git operation
- ERROR_RECOVERY_PROTOCOL.md applies when mistakes happen

---

## Testing Quick Reference

```bash
# Before claiming "fixed"/"ready"/"complete":
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
./qa/bin/functional encoding <test_id>
```

**All must pass. No exceptions.**

---

## Recent Changes (2025-11-20)

✅ **CLI Interactive Enhancement** - Intelligent auto-completion for ExaBGP CLI
✅ Created `CommandRegistry` for dynamic command discovery
✅ Refactored shortcut expansion (eliminated 120 lines duplication)
✅ Added neighbor IP, AFI/SAFI, route keyword completion
✅ Created wiki documentation generator (`sbin/exabgp-doc-generator`)
✅ All tests pass (1424/1424 unit tests)

**Previous (2025-11-17):**
✅ Reorganized documentation structure
✅ Created `wip/` for active work (clear separation from protocols)
✅ Moved all completed projects to `docs/projects/`
✅ Added Git Verification Protocol

**Previous (2025-11-16):**
✅ Compressed core protocols (59 KB → 14 KB, 77% ↓)
✅ Updated baselines (605 MyPy, 1376 tests)

---

**Current Status:** ✅ CLI enhancement ready for testing with running ExaBGP
**Last Updated:** 2025-11-20
