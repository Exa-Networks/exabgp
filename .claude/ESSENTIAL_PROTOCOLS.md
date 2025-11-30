# Essential Protocols (READ EVERY SESSION)

**Purpose:** Core rules that apply to ALL interactions
**Size:** ~5 KB
**Read time:** <1 minute

**Token savings:** Reading this file vs. all protocols = **86% reduction** (5 KB vs 37 KB)

---

## 🚨 CRITICAL RULES 🚨

### 1. Verification Before Claiming

**Core principle:** Never claim success without proof

❌ **Forbidden without verification:**
- "Fixed" / "Complete" / "Working" / "All tests pass"
- ✅ checkmarks without command output
- Explanations instead of proof

✅ **Required:**
1. Run the actual command/test
2. Paste exact output
3. Let output prove success/failure

**Example:**
```bash
./qa/bin/test_everything
# [paste full output]
Exit code: 0
```

**See:** VERIFICATION_PROTOCOL.md for enforcement checklist

---

### 2. Communication Style

**Core principle:** Terse, direct, emoji-prefixed status lines

✅ **Do:**
- Start status lines with emoji (✅/❌/📁/🧪/🚀/📝)
- One-sentence responses for simple actions
- Direct statements, no hedging

❌ **Don't:**
- Politeness, reassurance, explanations
- "I'll help you..." / "Great news!" / "Unfortunately..."
- Multi-paragraph responses for simple tasks

**Examples:**
- ✅ "Tests pass (ruff + pytest: 1376)"
- ❌ "Great news! All tests passed successfully..."

**See:** COMMUNICATION_STYLE.md for full guidelines, EMOJI_GUIDE.md for emoji usage

---

### 3. Testing Requirement

**Core principle:** Never claim success without running ALL tests

❌ **Forbidden without testing:**
- "Done" / "Fixed" / "Ready" / "Complete"
- Any claim of working code

✅ **Required before claiming success:**
```bash
./qa/bin/test_everything  # ALL 6 test suites
```

**Regression tests mandatory:**
- Bug fix → Add test that would have caught bug
- New feature → Add unit + functional tests
- Refactoring → Verify tests cover code

**Test locations:**
- Unit tests: `tests/unit/`
- Functional tests: `qa/bin/functional encoding/decoding`

**See:** TESTING_PROTOCOL.md for enforcement checklist

---

### 4. Coding Standards

**Core principle:** Python 3.10+, strict mypy, stable BGP APIs

✅ **Required:**
- Python 3.10+ syntax: `int | str` NOT `Union[int, str]`
- NO code requiring mypy config changes
- BGP APIs: keep `negotiated` parameter (stable API, unused OK)
- Fix type errors at root cause, never `cast()` or `# type: ignore`

❌ **Prohibited:**
- `Union[int, str]` instead of `int | str`
- Adding mypy suppressions or relaxed settings
- Removing `negotiated` parameter from pack/unpack methods
- Introducing asyncio (custom reactor pattern used)

**Linting:**
```bash
ruff format src && ruff check src  # Must pass
```

**See:** CODING_STANDARDS.md for complete standards

---

## 🎯 Session Start Workflow

### 1. Read this file (you just did) ✅

### 2. Check git state

```bash
git status && git diff && git diff --staged
```

If ANY modified/staged files: ASK user how to handle before starting work.

### 3. Load contextual protocols based on task

**Use decision tree below to determine which additional protocols to read.**

| Activity | Load Protocol | Size |
|----------|---------------|------|
| Git operations (commit/push/branch) | GIT_VERIFICATION_PROTOCOL.md | 3.7 KB |
| Refactoring code | MANDATORY_REFACTORING_PROTOCOL.md | 3.2 KB |
| Test failures / debugging | FUNCTIONAL_TEST_DEBUGGING_GUIDE.md | 8.9 KB |
| Creating documentation | DOCUMENTATION_PLACEMENT_GUIDE.md | 12 KB |
| Error recovery / mistakes | ERROR_RECOVERY_PROTOCOL.md | 2.9 KB |
| Feature development | *(covered in this file - see below)* | - |

### 4. Use decision tree if uncertain

See README.md "What Do You Want to Do?" table

---

## Codebase Architecture Quick Reference

**For feature development, use this summary. Full details on-demand.**

**Directory structure:**
```
src/exabgp/
├── bgp/              # BGP protocol (messages, FSM, negotiation)
│   ├── message/      # OPEN, UPDATE, NOTIFICATION, KEEPALIVE
│   └── message/update/  # Attributes, NLRI, AFI/SAFI
├── reactor/          # Event loop (custom, NOT asyncio)
│   ├── peer.py       # BGP peer handling
│   └── api/          # External process communication
├── rib/              # Routing Information Base
├── configuration/    # Config parser, templates, validation
└── protocol/         # Protocol helpers

tests/unit/           # Unit tests (pytest)
qa/                   # Functional tests (encoding/decoding)
```

**Design patterns:**
- Registry/Factory: `@Message.register`, `@NLRI.register`
- Template Method: `pack_nlri()`, `unpack_nlri()`
- State Machine: BGP FSM

**Full details:** exabgp/CODEBASE_ARCHITECTURE.md, exabgp/DATA_FLOW_GUIDE.md

---

## Git Workflow Essentials

**NEVER commit/push without explicit user request.**

**User must say:** "commit" / "make a commit" / "push" / "git push"

**Before ANY git operation:**
```bash
git status && git log --oneline -5
```

**Workflow:**
1. Complete work
2. STOP and report what was done
3. WAIT for user instruction
4. Only commit/push if explicitly asked

**See:** GIT_VERIFICATION_PROTOCOL.md for complete workflow

---

## Reference Materials (NOT Auto-Loaded)

**Consult these when needed:**
- FUNCTIONAL_TEST_ARCHITECTURE.md - How tests work
- FUNCTIONAL_TEST_EDIT.md - Inspecting test configs
- FILE_NAMING_CONVENTIONS.md - Naming patterns
- CI_TESTING.md - Test commands reference
- PLANNING_GUIDE.md - Project planning standards
- BACKPORT.md - Bug fix tracking for backports
- PRE_FLIGHT_CHECKLIST.md - Session start checklist

**Complete protocol listing:** README.md

---

## Contextual Loading Triggers

**You should load additional protocols when:**

**Git work detected:**
- User mentions: "commit", "push", "branch", "merge"
- About to run git commands
- → Read GIT_VERIFICATION_PROTOCOL.md

**Refactoring detected:**
- User says: "refactor", "rename", "restructure"
- Multiple file edits planned
- → Read MANDATORY_REFACTORING_PROTOCOL.md

**Error/failure detected:**
- Test failure occurs
- User says: "wrong", "broken", "fix", "not working"
- → Read ERROR_RECOVERY_PROTOCOL.md

**Test debugging needed:**
- Functional test fails
- User asks about test failures
- → Read FUNCTIONAL_TEST_DEBUGGING_GUIDE.md

**Creating documentation:**
- Creating new .md file
- User asks "where should I document..."
- → Read DOCUMENTATION_PLACEMENT_GUIDE.md

---

## Quick Reference: Forbidden Phrases

**Without verification (command + output pasted):**
- ❌ "Fixed" / "Complete" / "Working" / "Ready"
- ❌ "All tests pass" / "Tests pass"
- ❌ ✅ checkmark without proof

**Without running ./qa/bin/test_everything:**
- ❌ "Done" / "Finished" / "Complete"
- ❌ Any claim code works

**Without explicit user request:**
- ❌ `git commit` / `git push`
- ❌ "I've committed..." / "I've pushed..."

**Auto-fix:** Stop. Run command. Paste output. Then claim.

---

## Emergency Protocol Selection

**Not sure which protocol to read?**

| Situation | Protocol |
|-----------|----------|
| About to commit | GIT_VERIFICATION_PROTOCOL.md |
| Renaming functions | MANDATORY_REFACTORING_PROTOCOL.md |
| Test failed | FUNCTIONAL_TEST_DEBUGGING_GUIDE.md |
| Made a mistake | ERROR_RECOVERY_PROTOCOL.md |
| Creating .md file | DOCUMENTATION_PLACEMENT_GUIDE.md |
| Everything else | *(covered in this file)* |

---

**Updated:** 2025-11-30
