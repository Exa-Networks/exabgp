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

## First Session? Start Here

**New to this repository?** Read these 4 protocols FIRST:

1. `VERIFICATION_PROTOCOL.md` - Never claim without proof
2. `COMMUNICATION_STYLE.md` - How to communicate
3. `TESTING_PROTOCOL.md` - When/how to test
4. `CODING_STANDARDS.md` - Python 3.10+, mypy rules

**Then read these before making changes:**

5. `GIT_VERIFICATION_PROTOCOL.md` - Git safety
6. `MANDATORY_REFACTORING_PROTOCOL.md` - Safe refactoring
7. `ERROR_RECOVERY_PROTOCOL.md` - Mistake recovery

**For codebase work, also read:**

- `exabgp/CODEBASE_ARCHITECTURE.md` - Where everything is
- `exabgp/DATA_FLOW_GUIDE.md` - How data flows

---

## Protocol Files by Category

### Core Work Protocols
- **VERIFICATION_PROTOCOL.md** - NEVER claim success without pasting proof
- **MANDATORY_REFACTORING_PROTOCOL.md** - One function at a time with verification
- **ERROR_RECOVERY_PROTOCOL.md** - NEVER rush after mistakes

### Communication Protocols
- **COMMUNICATION_STYLE.md** - Terse, direct communication
- **EMOJI_GUIDE.md** - Systematic emoji usage

### Quality & Standards
- **CODING_STANDARDS.md** - Python 3.10+, mypy, BGP APIs
- **TESTING_PROTOCOL.md** - Test requirements before claiming success

### Version Control
- **GIT_VERIFICATION_PROTOCOL.md** - Git safety rules
- **BACKPORT.md** - Bug fix tracking for backports

### Testing & Debugging
- **CI_TESTING.md** - Complete test suite commands
- **FUNCTIONAL_TEST_DEBUGGING_GUIDE.md** - Systematic debugging process
- **FUNCTIONAL_TEST_ARCHITECTURE.md** - How functional tests work
- **FUNCTIONAL_TEST_EDIT.md** - Inspecting test configurations

### Planning & Organization
- **PLANNING_GUIDE.md** - Project planning standards
- **DOCUMENTATION_PLACEMENT_GUIDE.md** - Where to put documentation
- **PRE_FLIGHT_CHECKLIST.md** - Session start checklist
- **FILE_NAMING_CONVENTIONS.md** - File naming rules

**Total: 18 protocol files (~37 KB)**

---

## Directory Structure

```
.claude/
├── # PROTOCOLS (how we work - READ EVERY SESSION)
├── VERIFICATION_PROTOCOL.md
├── COMMUNICATION_STYLE.md
├── GIT_VERIFICATION_PROTOCOL.md
├── MANDATORY_REFACTORING_PROTOCOL.md
├── ERROR_RECOVERY_PROTOCOL.md
├── CODING_STANDARDS.md
├── TESTING_PROTOCOL.md
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

## What Do You Want to Do?

**Task** | **Read These Docs**
---------|--------------------
Fix a bug | VERIFICATION_PROTOCOL.md, TESTING_PROTOCOL.md, MANDATORY_REFACTORING_PROTOCOL.md, FUNCTIONAL_TEST_DEBUGGING_GUIDE.md
Add a feature | exabgp/CODEBASE_ARCHITECTURE.md, exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md, exabgp/DATA_FLOW_GUIDE.md, TESTING_PROTOCOL.md
Understand codebase | exabgp/CODEBASE_ARCHITECTURE.md, exabgp/DATA_FLOW_GUIDE.md, exabgp/BGP_CONCEPTS_TO_CODE_MAP.md
Debug test failures | FUNCTIONAL_TEST_DEBUGGING_GUIDE.md, FUNCTIONAL_TEST_ARCHITECTURE.md, CI_TESTING.md
Work with CLI | exabgp/CLI_COMMANDS.md, exabgp/CLI_SHORTCUTS.md, exabgp/CLI_IMPLEMENTATION.md
Understand API | exabgp/UNIX_SOCKET_API.md, exabgp/NEIGHBOR_SELECTOR_SYNTAX.md
Refactor code | MANDATORY_REFACTORING_PROTOCOL.md, CODING_STANDARDS.md, TESTING_PROTOCOL.md
Review changes | VERIFICATION_PROTOCOL.md, GIT_VERIFICATION_PROTOCOL.md

---

## Quick Start

**At session start:**
1. Read ALL Core Protocols above (ALL mandatory, see top of file)
2. Check `git status`, `git diff`, `git diff --staged`
3. If files modified: ASK user before proceeding

**For any code changes:**
1. Make changes following CODING_STANDARDS.md
2. Follow MANDATORY_REFACTORING_PROTOCOL.md if refactoring
3. Run ALL tests per TESTING_PROTOCOL.md
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
**Last Updated:** 2025-11-30
