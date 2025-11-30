# Claude AI Assistant Resources

Documentation and protocols for Claude Code interactions with ExaBGP.

---

## 🚨 START OF EVERY SESSION 🚨

**⚠️ CRITICAL: You have NO memory between sessions ⚠️**

### MANDATORY FIRST ACTION

**Read `ESSENTIAL_PROTOCOLS.md` (~5 KB)**

This single file contains core rules that apply to ALL interactions:
- Verification before claiming success
- Communication style (terse, emoji-prefixed)
- Testing requirements (./qa/bin/test_everything)
- Coding standards essentials (Python 3.10+, mypy)
- Session start workflow
- Contextual protocol loading guide

**Token savings:** 86% reduction vs. reading all protocols (5 KB vs 37 KB)

### Then Check Git State

```bash
git status && git diff && git diff --staged
```

If ANY files modified/staged: ASK user how to handle before starting work.

### Load Contextual Protocols Based on Task

**See decision tree below** to determine which additional protocols to read.

**Most tasks are covered by ESSENTIAL_PROTOCOLS.md alone.** Only load additional protocols when explicitly needed for specialized tasks (git, refactoring, test debugging, etc.).

---

## First Session? Start Here

**New to this repository?**

1. **Read `ESSENTIAL_PROTOCOLS.md`** - Contains all core rules (~5 KB)
2. **Check git state** - Run git status checks
3. **Use decision tree below** - Find docs for your specific task

**That's it!** The essential protocols file covers verification, communication, testing, and coding standards. Additional protocols are loaded contextually based on what you're doing.

---

## Protocol Files (Tiered System)

### Tier 1: Essential Core (Read Every Session)

- **ESSENTIAL_PROTOCOLS.md** - Core rules for ALL interactions (~5 KB)
  - Verification before claiming
  - Communication style
  - Testing requirements
  - Coding standards
  - Git workflow essentials
  - Contextual loading guide

**Read this ONE file at session start. Token savings: 86%**

### Tier 2: Contextual Protocols (Load When Relevant)

**Git & Version Control:**
- GIT_VERIFICATION_PROTOCOL.md - Complete git safety workflow
- BACKPORT.md - Bug fix tracking for backports

**Code Quality:**
- MANDATORY_REFACTORING_PROTOCOL.md - Safe refactoring (one function at a time)
- ERROR_RECOVERY_PROTOCOL.md - Mistake recovery workflow

**Testing & Debugging:**
- FUNCTIONAL_TEST_DEBUGGING_GUIDE.md - Debug test failures systematically

**Documentation:**
- DOCUMENTATION_PLACEMENT_GUIDE.md - Where to put docs

**Full Protocol Details:**
- VERIFICATION_PROTOCOL.md - Complete verification rules
- TESTING_PROTOCOL.md - Complete testing requirements
- CODING_STANDARDS.md - All coding standards
- COMMUNICATION_STYLE.md - Full communication guidelines

### Tier 3: Reference Materials (Consult When Needed)

- FUNCTIONAL_TEST_ARCHITECTURE.md - How tests work
- FUNCTIONAL_TEST_EDIT.md - Inspecting test configs
- FILE_NAMING_CONVENTIONS.md - Naming patterns
- CI_TESTING.md - Test commands reference
- PLANNING_GUIDE.md - Project planning standards
- EMOJI_GUIDE.md - Emoji reference
- PRE_FLIGHT_CHECKLIST.md - Session checklist

**Total: 1 essential + 10 contextual + 7 reference = 18 files**

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

**Task** | **Read These Docs** | **Protocols to Load**
---------|---------------------|----------------------
Fix a bug | exabgp/CODEBASE_ARCHITECTURE.md (summary in ESSENTIAL) | *(none - covered in ESSENTIAL)*
Add a feature | exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md, exabgp/DATA_FLOW_GUIDE.md | *(none - covered in ESSENTIAL)*
Commit changes | *(none)* | GIT_VERIFICATION_PROTOCOL.md
Refactor code | exabgp/CODEBASE_ARCHITECTURE.md | MANDATORY_REFACTORING_PROTOCOL.md
Debug test failures | FUNCTIONAL_TEST_DEBUGGING_GUIDE.md, CI_TESTING.md | FUNCTIONAL_TEST_DEBUGGING_GUIDE.md
Create documentation | DOCUMENTATION_PLACEMENT_GUIDE.md | DOCUMENTATION_PLACEMENT_GUIDE.md
Understand codebase | exabgp/CODEBASE_ARCHITECTURE.md, exabgp/DATA_FLOW_GUIDE.md | *(none)*
Work with CLI | exabgp/CLI_COMMANDS.md, exabgp/CLI_IMPLEMENTATION.md | *(none)*
Understand API | exabgp/UNIX_SOCKET_API.md, exabgp/NEIGHBOR_SELECTOR_SYNTAX.md | *(none)*
Recover from error | ERROR_RECOVERY_PROTOCOL.md | ERROR_RECOVERY_PROTOCOL.md

**Note:** ESSENTIAL_PROTOCOLS.md covers most tasks. Only load additional protocols for specialized workflows.

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
