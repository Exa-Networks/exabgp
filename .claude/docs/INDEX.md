# Complete Documentation Index

**Total files:** 100 markdown files

---

## By Category

### Protocols (`.claude/` root - 18 files)

**Core Work Protocols:**
- `VERIFICATION_PROTOCOL.md` - Never claim success without pasting proof
- `MANDATORY_REFACTORING_PROTOCOL.md` - One function at a time with verification
- `ERROR_RECOVERY_PROTOCOL.md` - Slow down after mistakes
- `GIT_VERIFICATION_PROTOCOL.md` - Git safety rules
- `TESTING_PROTOCOL.md` - Test requirements before claiming success

**Communication & Standards:**
- `COMMUNICATION_STYLE.md` - Terse, direct communication style
- `EMOJI_GUIDE.md` - Systematic emoji usage
- `CODING_STANDARDS.md` - Python 3.10+, mypy, BGP APIs

**Testing & Debugging:**
- `CI_TESTING.md` - Complete test suite commands
- `FUNCTIONAL_TEST_DEBUGGING_GUIDE.md` - Systematic debugging process
- `FUNCTIONAL_TEST_ARCHITECTURE.md` - How functional tests work
- `FUNCTIONAL_TEST_EDIT.md` - Inspecting test configurations

**Planning & Organization:**
- `PLANNING_GUIDE.md` - Project planning standards
- `DOCUMENTATION_PLACEMENT_GUIDE.md` - Where to put documentation
- `PRE_FLIGHT_CHECKLIST.md` - Session start checklist
- `FILE_NAMING_CONVENTIONS.md` - File naming rules
- `BACKPORT.md` - Bug fix backport tracking
- `README.md` - Main protocols overview

### Codebase Reference (`.claude/exabgp/` - 11 files)

**Architecture & Patterns:**
- `CODEBASE_ARCHITECTURE.md` - Complete directory structure, module purposes
- `DATA_FLOW_GUIDE.md` - How data moves through the system
- `REGISTRY_AND_EXTENSION_PATTERNS.md` - How to extend ExaBGP
- `BGP_CONCEPTS_TO_CODE_MAP.md` - BGP RFC concepts → code locations
- `CRITICAL_FILES_REFERENCE.md` - Most frequently modified files

**API & Command Reference:**
- `CLI_COMMANDS.md` - Complete CLI command reference (43 commands)
- `CLI_SHORTCUTS.md` - CLI shortcut reference
- `CLI_IMPLEMENTATION.md` - CLI internal architecture
- `UNIX_SOCKET_API.md` - Unix socket API protocol
- `NEIGHBOR_SELECTOR_SYNTAX.md` - Neighbor selector grammar
- `ENVIRONMENT_VARIABLES.md` - Environment variables reference

### Active Work (`plan/` - project root)

**Note:** Active project plans are now in `plan/` directory at project root.

**Main TODO:** `plan/todo.md` - Central tracking for all quality improvements
- Type Safety (89 mypy errors - 92% reduction from baseline)
- Packed-bytes-first refactoring
- Test coverage (59.71%)
- Security, architecture, code quality

**Project-specific plans:**
- `plan/packed-attribute.md` - Packed-bytes-first refactoring waves
- `plan/coverage.md` - Test coverage audit
- `plan/type-annotations/` - Type annotation detailed plans
- `plan/xxx-cleanup/` - XXX comment cleanup (Phases 4-5 pending)

### Completed Projects (`.claude/docs/projects/` - 50+ files)

**asyncio-migration/** - ✅ COMPLETE (26 files)
- `README.md` - Migration overview
- `PHASE2_PRODUCTION_VALIDATION.md` - Current phase
- `investigation-sessions.md` - Links to debugging sessions
- `async-architecture.md` - How async mode works
- `GENERATOR_VS_ASYNC_EQUIVALENCE.md` - Technical equivalence
- `INDEX.md` - Complete project index
- `archive/` - 6 historical documents
- `phases/` - 4 phase-specific documents
- `sessions/` - 5 session summaries
- `technical/` - 7 technical deep-dives
- `overview/` - 2 completion documents

**cli-dual-transport/** - ✅ COMPLETE
- Project documentation (location verified but not enumerated)

**type-annotations/** - 🔄 MOVED TO plan/
- Active tracking now in `plan/todo.md`
- Detailed plans in `plan/type-annotations/`

### Archive (`.claude/docs/archive/` - 25+ files)

**asyncio-investigation-2025-11/** - ✅ COMPLETE (9 files)
- `README.md` - Investigation overview
- `2025-11-18/` - 7 investigation session files
- `SESSION_2025-11-19_LOOP_ORDER_FIX.md`
- `SESSION_2025-11-19_DOCUMENTATION_UPDATE.md`

**testing-improvements/** - ✅ SUPERSEDED (6 files)
- `README.md` - Archive overview with "See instead" pointers
- `analysis.md`, `improvement-plan.md`, `progress.md`, `roadmap.md`, `ci-testing-guide.md`

**cli-enhancement/** - ✅ COMPLETE
- `README.md` - Archive overview with "See instead" pointers

**api-peer-mgmt/** - ✅ SUPERSEDED
- `README.md` - Early experiments overview

**dual-transport/** - ✅ COMPLETE
- `README.md` - Early dual transport work

---

## Quick Navigation

### I want to...

**Fix a bug:**
1. `VERIFICATION_PROTOCOL.md`
2. `TESTING_PROTOCOL.md`
3. `MANDATORY_REFACTORING_PROTOCOL.md`
4. `FUNCTIONAL_TEST_DEBUGGING_GUIDE.md`

**Add a feature:**
1. `exabgp/CODEBASE_ARCHITECTURE.md`
2. `exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md`
3. `exabgp/DATA_FLOW_GUIDE.md`
4. `TESTING_PROTOCOL.md`

**Understand the codebase:**
1. `exabgp/CODEBASE_ARCHITECTURE.md`
2. `exabgp/DATA_FLOW_GUIDE.md`
3. `exabgp/BGP_CONCEPTS_TO_CODE_MAP.md`

**Work with CLI:**
1. `exabgp/CLI_COMMANDS.md`
2. `exabgp/CLI_SHORTCUTS.md`
3. `exabgp/CLI_IMPLEMENTATION.md`

**Debug test failures:**
1. `FUNCTIONAL_TEST_DEBUGGING_GUIDE.md`
2. `FUNCTIONAL_TEST_ARCHITECTURE.md`
3. `CI_TESTING.md`

---

## File Count by Category

| Category | Count | Status |
|----------|-------|--------|
| Protocols (root) | 18 | ✅ Active |
| Codebase reference (exabgp/) | 11 | ✅ Active |
| Active plans (plan/) | 15+ | 🔄 Active |
| Completed projects | 50+ | ✅ Complete |
| Archive | 25+ | 📦 Historical |
| **Total** | **100+** | - |

---

**Updated:** 2025-12-04
