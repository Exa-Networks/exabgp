# Essential Protocols (READ EVERY SESSION)

**Purpose:** Core rules that apply to ALL interactions
**Size:** ~5 KB
**Read time:** <1 minute

**Token savings:** Reading this file vs. all protocols = **86% reduction** (5 KB vs 37 KB)

---

## 🚨 CRITICAL RULES 🚨

### 0. Work Preservation (NEVER LOSE CODE) 🚨🚨🚨

**Core principle:** NEVER discard uncommitted work. ALWAYS ask first.

## ❌ FORBIDDEN without saving diff first AND asking user:

1. **These commands require SAVE + ASK workflow:**
   - `git checkout -- <file>`
   - `git checkout HEAD -- <file>`
   - `git reset --hard`
   - `git stash drop`

2. **NEVER decide on your own to revert/discard work**
   - Even if tests fail
   - Even if you think the approach is wrong
   - Even if you want to try a different approach

## ✅ MANDATORY WORKFLOW when you want to revert/change approach:

**STEP 1: ALWAYS save first**
```bash
git diff > .claude/backups/work-$(date +%Y%m%d-%H%M%S).patch
```

**STEP 2: ALWAYS ask the user**
Use AskUserQuestion tool:
- "Tests are failing. Should I: (a) keep debugging, (b) save and try different approach, (c) revert to last working state?"
- WAIT for user response before ANY destructive action

**STEP 3: Only proceed after explicit user approval**

## When tests fail on experimental code:

1. **DO NOT REVERT** - the work has value even if broken
2. Save to backup: `git diff > .claude/backups/failing-code.patch`
3. ASK user what to do next
4. Options to present:
   - Continue debugging
   - Commit as WIP: "WIP: experimental (tests failing)"
   - Try different approach (after saving)

**Backup location:** `.claude/backups/` - ALWAYS use this folder

**Recovery:** If work was lost, check:
- `.claude/backups/` - saved patches
- `git stash list` - stashed changes
- `git reflog` - recent commits

**See:** ERROR_RECOVERY_PROTOCOL.md for recovery procedures

---

### 0.5. Plan Maintenance (Keep Notes Updated)

**Core principle:** Always maintain notes as you work. NEVER delete from plan files.

**Plan file location:** `plan/` - Implementation plans and active work (project root)

✅ **Required during complex work:**
1. If a plan file exists (e.g., `plan/*.md`), update it as you discover:
   - Edge cases found during implementation
   - Design decisions made
   - Issues encountered and their resolutions
   - Status of each task (✅/🔄/❌)

2. Before ending a session or when making significant progress:
   - Update the plan with current state
   - Note any failing tests and their causes
   - Document what was learned

3. When tests fail:
   - Add the failure details to the plan BEFORE attempting fixes
   - Document the root cause once identified
   - This creates a record even if the session is interrupted

## ❌ NEVER delete content from plan files

- Only APPEND new information
- Mark outdated sections with ~~strikethrough~~ or "SUPERSEDED BY: ..."
- Keep history of failed approaches - they have value
- If an approach didn't work, document WHY before trying another

**Benefit:** If a session is lost, the plan file contains the full context needed to resume.

---

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

### 3. Test-Driven Development (TDD) 🚨

**Core principle:** Write tests BEFORE code. Tests define expected behavior.

## TDD Workflow (MANDATORY)

**STEP 1: Write tests FIRST**
```bash
# Create/update unit tests for new interface
# Tests MUST fail initially - this proves they test something
uv run pytest tests/unit/path/to/test.py -v  # Should FAIL
```

**STEP 2: Implement code to make tests pass**

**STEP 3: Verify ALL tests pass**
```bash
./qa/bin/test_everything  # ALL 6 test suites
```

**IF TESTS FAIL:**
1. **STOP** - Do NOT immediately try to fix
2. **Update plan file FIRST** (if one exists for this work):
   - Add entry to "## Recent Failures" section
   - Include: test name, error message, suspected cause
3. **THEN** proceed to fix
4. **After fixing**, update plan with resolution

**Template for failure entry:**
```markdown
### [Date] Test Failure: test_name

**Error:** [paste error message]
**Suspected cause:** [your analysis]
**Status:** 🔄 Investigating | ✅ Fixed | ❌ Blocked

**Resolution:** [what fixed it, or why blocked]
```

## Test Requirements by Change Type

| Change Type | Required Tests |
|-------------|----------------|
| Bug fix | Test that reproduces the bug (fails before fix) |
| New feature | Unit tests + functional tests if applicable |
| Refactoring | Verify existing tests cover the code |
| New `__init__` signature | Unit test: construct, verify properties |
| New factory method | Unit test: factory creates valid instance |
| Validation logic | Unit test: invalid input raises exception |

❌ **Forbidden:**
- Writing code before tests
- Claiming "Done" / "Fixed" / "Complete" without test verification
- Skipping the "tests fail first" step

✅ **Required before claiming success:**
```bash
./qa/bin/test_everything  # ALL 6 test suites
```

**Test locations:**
- Unit tests: `tests/unit/`
- Functional tests: `qa/bin/functional encoding/decoding`

**See:** TESTING_PROTOCOL.md for enforcement checklist

---

### 4. Coding Standards

**Core principle:** Python 3.12+, strict mypy, stable BGP APIs

✅ **Required:**
- Python 3.12+ syntax: `int | str` NOT `Union[int, str]`
- NO code requiring mypy config changes
- BGP APIs: keep `negotiated` parameter (stable API, unused OK)
- Fix type errors at root cause, avoid `# type: ignore`
- `cast()` is acceptable ONLY when preceded by runtime type check (isinstance/hasattr)
  - Example: `if isinstance(x, bool): return cast(T, x)` ✅
  - Example: `return cast(int, value)` without check ❌
  - Prefer assertions/raises over fallback cast: `raise TypeError(...)` not `return cast(T, value)`

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

### 3. Check plan state

```bash
ls -la plan/
```

- List all active plan files
- For each, check status emoji in header (🔄 Active, 📋 Planning, ✅ Completed, ⏸️ On Hold)
- Report to user: "Active plans: [list with status]"
- Ask: "Which plan (if any) are we working on today?"

**If working on a plan:** Keep it updated throughout the session (see Plan Update Triggers below).

### 4. Load contextual protocols based on task

**Use decision tree below to determine which additional protocols to read.**

| Activity | Load Protocol | Size |
|----------|---------------|------|
| Git operations (commit/push/branch) | GIT_VERIFICATION_PROTOCOL.md | 3.7 KB |
| Refactoring code | MANDATORY_REFACTORING_PROTOCOL.md | 3.2 KB |
| Test failures / debugging | FUNCTIONAL_TEST_DEBUGGING_GUIDE.md | 8.9 KB |
| Creating documentation | DOCUMENTATION_PLACEMENT_GUIDE.md | 12 KB |
| Error recovery / mistakes | ERROR_RECOVERY_PROTOCOL.md | 2.9 KB |
| Feature development | *(covered in this file - see below)* | - |

### 5. Use decision tree if uncertain

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

## Plan Update Triggers

**When to update plan files (if working on a plan):**

### Mandatory Triggers (MUST update)
- ❌ **Test failure** → Document in "Recent Failures" BEFORE fixing
- 🚫 **Blocker discovered** → Add to "Blockers" section
- 💡 **Design decision made** → Add to "Decisions" or relevant section
- ✅ **Task completed** → Mark ✅ in progress table
- 🛑 **Session ending** → Full plan review (see SESSION_END_CHECKLIST.md)

### What Counts as "Significant Progress"
Any of these means update the plan:
- Completed a task (even partial)
- Changed approach/strategy
- Discovered something unexpected
- Hit a blocker
- Made a decision that affects scope

### Enforcement
Before ending ANY session where you worked on a plan:
- [ ] Plan file has "Last Updated" timestamp current
- [ ] All failures documented
- [ ] All blockers documented
- [ ] "Resume Point" section updated

**See:** SESSION_END_CHECKLIST.md for complete checklist

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
- SESSION_END_CHECKLIST.md - Session end checklist (mandatory)

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

**Without writing tests FIRST (TDD):**
- ❌ Implementing code before tests exist
- ❌ Skipping the "verify tests fail" step
- ❌ "I'll add tests later"

**Without explicit user request:**
- ❌ `git commit` / `git push`
- ❌ "I've committed..." / "I've pushed..."

**Auto-fix:** Stop. Write tests. Verify they fail. Implement. Verify they pass. Then claim.

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

**Updated:** 2025-12-04
