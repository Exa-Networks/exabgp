# MANDATORY REFACTORING PROTOCOL

**STATUS: MANDATORY - MUST BE FOLLOWED FOR ALL REFACTORING WORK**

This protocol exists because of a critical failure on 2025-11-16 where 95 files were refactored and committed with 72 test failures. The commit had to be reverted, losing all work.

## Why This Protocol Exists

**The Failure Pattern:**
1. Started refactoring work across many files
2. Tested "some things" and saw them pass
3. Assumed everything was working
4. Committed without running full test suite
5. Discovered 72 tests were actually failing
6. Had to revert, losing all work

**Root Cause:** No forcing function to prove each step before proceeding.

**Solution:** Mandatory step-by-step verification with visible proof at each stage.

---

## PROTOCOL PHASE 0: PLANNING (MANDATORY)

**Before touching ANY code, you MUST:**

### 1. Write Explicit Numbered Steps

NOT acceptable: "Rename pack() methods across the codebase"

REQUIRED:
```
Step 1: Rename ESI.pack() to pack_esi() in qualifier/esi.py
  Verification: pytest tests/unit/test_evpn.py -q

Step 2: Rename MAC.pack() to pack_mac() in qualifier/mac.py
  Verification: pytest tests/unit/test_evpn.py -q

Step 3: Rename Labels.pack() to pack_labels() in qualifier/labels.py
  Verification: pytest tests/unit/test_label.py -q

... [continue for ALL steps]

Step N: Run full test suite
  Verification: pytest ./tests/unit/ -q (MUST show 0 failures)
```

### 2. How to Write the Step-by-Step Plan

**Each step MUST include:**

#### Step Number and Description
```
Step N: [Action] [What] in [Where]
```

**Requirements:**
- **Action:** Specific verb (Rename, Update, Fix, Add, Remove)
- **What:** Exact thing being changed (method name, class, variable)
- **Where:** Exact file path or location

**Good examples:**
- ✅ `Step 1: Rename Origin.pack() to pack_attribute() in src/exabgp/bgp/message/update/attribute/origin.py`
- ✅ `Step 2: Update call sites from .pack() to .pack_attribute() in src/exabgp/bgp/message/update/attribute/attributes.py`
- ✅ `Step 3: Fix test file to use pack_attribute() in tests/unit/test_path_attributes.py`

**Bad examples:**
- ❌ `Step 1: Rename methods` (too vague)
- ❌ `Step 2: Update files` (what files? what update?)
- ❌ `Step 3: Fix tests` (which tests? how?)

#### Verification Command
```
Verification: [exact command to run]
```

**Requirements:**
- Must be an exact command that can be copy-pasted
- Must test the specific changes in this step
- Must be narrow enough to catch errors in this step only

**Good examples:**
- ✅ `Verification: env exabgp_log_enable=false pytest tests/unit/test_path_attributes.py -k origin -q`
- ✅ `Verification: env exabgp_log_enable=false pytest tests/unit/test_evpn.py -q`
- ✅ `Verification: ruff check src/exabgp/bgp/message/update/attribute/origin.py`

**Bad examples:**
- ❌ `Verification: Run tests` (what tests?)
- ❌ `Verification: Check it works` (how?)
- ❌ `Verification: pytest` (too broad, doesn't isolate this step)

#### Expected Output
```
Expected: [what success looks like]
```

**Requirements:**
- State what the output should show
- Include pass count if known
- State "0 failures" explicitly

**Good examples:**
- ✅ `Expected: 15 passed, 0 failed`
- ✅ `Expected: All checks passed!`
- ✅ `Expected: No output (ruff finds no issues)`

#### Scope Definition

For each step, explicitly state:
- **Files changed:** List exact file paths
- **Changes made:** Brief description of what's being modified
- **Why isolated:** Why this step is separate from others

**Example:**
```
Step 3: Rename Labels.pack() to pack_labels() in qualifier/labels.py
  Files: src/exabgp/bgp/message/update/nlri/qualifier/labels.py
  Changes: Method definition and all internal calls
  Isolation: Labels is used by label NLRI, separate from EVPN
  Verification: pytest tests/unit/test_label.py -q
  Expected: 35 passed, 0 failed
```

### 3. Plan Structure Template

**Your complete plan document MUST follow this structure:**

```markdown
# REFACTORING PLAN: [Brief Title]

## Overview
[1-2 sentence description of what's being refactored and why]

## Scope
- Total files affected: [number]
- Total steps: [number]
- Estimated test groups: [number]

## Pre-requisites
- [ ] All tests currently passing (verified)
- [ ] Git working directory clean (verified)
- [ ] File descriptor limit ≥64000 (verified)

## Steps

### Step 1: [Description]
**Files:** [exact paths]
**Changes:** [specific changes]
**Verification:** `[exact command]`
**Expected:** [expected output]

### Step 2: [Description]
**Files:** [exact paths]
**Changes:** [specific changes]
**Verification:** `[exact command]`
**Expected:** [expected output]

[... continue for ALL steps ...]

### Step N: Full Test Suite Verification
**Command:** `env exabgp_log_enable=false pytest ./tests/unit/ -q`
**Expected:** `1376 passed` with 0 failures
**Required:** Must paste complete output

### Step N+1: Linting Verification
**Command:** `ruff format src && ruff check src`
**Expected:** `All checks passed!`
**Required:** Must paste output

### Step N+2: Functional Tests (if applicable)
**Command:** `./qa/bin/functional encoding`
**Expected:** 120/120 passed
**Required:** Must paste summary

## Success Criteria
- [ ] All unit tests pass (1376/1376)
- [ ] All functional tests pass
- [ ] Linting passes
- [ ] No behavioral changes
- [ ] All verification outputs pasted in execution

## Risks
[List potential issues and how they'll be caught]

## Rollback Plan
[How to undo if something goes wrong]
```

### 4. Plan Quality Checklist

Before presenting your plan, verify:

- [ ] **Every step has a number** (Step 1, Step 2, ...)
- [ ] **Every step has exact file paths** (no "various files")
- [ ] **Every step has a verification command** (exact, runnable)
- [ ] **Every step has expected output** (specific, measurable)
- [ ] **Steps are ordered logically** (dependencies clear)
- [ ] **Steps are appropriately sized** (not too big, not too small)
- [ ] **Final steps include full test suite** (pytest + ruff + functional)
- [ ] **No vague language** ("various", "some", "multiple" are red flags)
- [ ] **No assumptions** (prove, don't assume)

### 5. Common Planning Mistakes to Avoid

❌ **Too broad:**
```
Step 1: Update all pack() methods
  Verification: pytest
```
Why bad: No isolation, can't tell what broke

✅ **Correct:**
```
Step 1: Rename Origin.pack() to pack_attribute() in origin.py
  Verification: pytest tests/unit/test_path_attributes.py -k origin -q
  Expected: 9 passed, 0 failed
```

❌ **Missing verification:**
```
Step 1: Rename ESI.pack() to pack_esi()
```
Why bad: No way to prove it worked

✅ **Correct:**
```
Step 1: Rename ESI.pack() to pack_esi() in qualifier/esi.py
  Verification: pytest tests/unit/test_evpn.py -q
  Expected: 45 passed, 0 failed
```

❌ **Vague scope:**
```
Step 1: Fix various test files
```
Why bad: Which files? What fixes?

✅ **Correct:**
```
Step 1: Update ESI test calls from pack() to pack_esi() in test_evpn.py
  Files: tests/unit/test_evpn.py (lines 156, 203, 287)
  Verification: pytest tests/unit/test_evpn.py -q
  Expected: 45 passed, 0 failed
```

### 6. Get User Approval

Present the complete plan with all steps and verifications.

**DO NOT proceed without user approval.**

**Say explicitly:**
```
I have created a step-by-step plan with [N] steps.
Each step has:
- Exact file changes
- Verification command
- Expected output

Please review and approve before I begin execution.
```

---

## PROTOCOL PHASE 1-N: EXECUTION (MANDATORY)

**For EACH step, you MUST follow this exact sequence:**

### Step Execution Template

```
=== STARTING STEP N ===
Description: [exact description of what will be changed]

[Make the changes for this step ONLY]

=== VERIFICATION FOR STEP N ===
Running: [exact command]

[Run the command]

OUTPUT:
[PASTE EXACT OUTPUT HERE - DO NOT SUMMARIZE]

Result: [PASS/FAIL]

=== STEP N VERIFIED ===
```

### Mandatory Requirements

1. **ANNOUNCE before starting:** "Starting Step N: [description]"

2. **DO ONLY THAT STEP:** Do not make changes for step N+1

3. **RUN VERIFICATION:** Execute the verification command for this step

4. **PASTE EXACT OUTPUT:** Do not summarize, do not paraphrase
   - Copy the ENTIRE output
   - Include pass/fail counts
   - Include any error messages

5. **DECLARE COMPLETION:** "Step N verified: [result]"

6. **STOP:** Do not proceed to step N+1 until proof is shown

### What You Cannot Do

❌ Skip verification for a step
❌ Batch multiple steps without verifying each
❌ Summarize test output instead of pasting it
❌ Claim success without showing proof
❌ Proceed to next step with failures

### What You Must Do

✅ Announce each step explicitly
✅ Complete only that one step
✅ Run the verification test
✅ Paste complete output
✅ Show the user the proof
✅ Wait for confirmation before proceeding (if in doubt)

---

## PROTOCOL PHASE FINAL: PRE-COMMIT VERIFICATION (MANDATORY)

**Before ANY git commit, you MUST:**

### 1. Run Complete Unit Test Suite

```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**PASTE THE EXACT OUTPUT**

Must show:
- Total number of tests passed
- **ZERO failures**
- **ZERO errors**

Example of acceptable output:
```
........................................................................ [ 94%]
........                                                                 [100%]
1376 passed in 3.96s
```

### 2. Run Linting

```bash
ruff format src && ruff check src
```

**PASTE THE EXACT OUTPUT**

Must show:
```
N files left unchanged
All checks passed!
```

### 3. Run Functional Tests (if applicable)

```bash
./qa/bin/functional encoding
```

**PASTE THE SUMMARY**

Must show all tests passed.

### 4. Only Then Proceed to Commit

If ANY of the above show failures:
- **DO NOT COMMIT**
- **DO NOT claim the work is complete**
- **DO NOT say "tests pass"**
- Fix the failures
- Re-run ALL verifications
- Paste the new outputs

---

## PROTOCOL: COMMIT CHECKLIST

**Before running git commit:**

- [ ] All unit tests pass (1376/1376) - proof pasted above
- [ ] Linting passes - proof pasted above
- [ ] Functional tests pass - proof pasted above
- [ ] Ran `git status` and reviewed changes
- [ ] Ran `git diff --stat` to see scope
- [ ] Prepared commit message
- [ ] User has reviewed (if applicable)

**Only when ALL boxes checked: run git commit**

---

## ENFORCEMENT

**This is not optional guidance. This is MANDATORY.**

If you violate this protocol:
- Work may need to be reverted
- Time is wasted
- Trust is broken

**The forcing function:**
You cannot proceed to the next step without pasting proof the current step passed.

**Why this works:**
- Forces transparency - can't hide failures
- Forces verification - must actually run tests
- Forces discipline - can't skip ahead
- Forces honesty - can't claim success without evidence

---

## EXAMPLE: Correct Protocol Execution

```
User: "Rename all pack() methods to pack_attribute()"

Claude: Let me create an explicit plan first.

=== PLAN ===
Step 1: Rename Origin.pack() to pack_attribute() in origin.py
  Verification: pytest tests/unit/test_path_attributes.py -k origin -q

Step 2: Rename NextHop.pack() to pack_attribute() in nexthop.py
  Verification: pytest tests/unit/test_path_attributes.py -k nexthop -q

Step 3: Rename ASPath.pack() to pack_attribute() in aspath.py
  Verification: pytest tests/unit/test_aspath.py -q

Step 4: [... all other steps ...]

Step N: Full test suite verification
  Verification: pytest ./tests/unit/ -q

Do you approve this plan?

[User approves]

=== STARTING STEP 1 ===
Renaming Origin.pack() to pack_attribute() in origin.py

[Makes changes]

=== VERIFICATION FOR STEP 1 ===
Running: pytest tests/unit/test_path_attributes.py -k origin -q

OUTPUT:
.........                                                         [100%]
9 passed in 0.23s

Result: PASS ✓

=== STEP 1 VERIFIED ===

[Continues for all steps...]

=== FINAL VERIFICATION ===
Running: env exabgp_log_enable=false pytest ./tests/unit/ -q

OUTPUT:
........................................................................ [ 94%]
........                                                                 [100%]
1376 passed in 3.96s

Result: ALL TESTS PASS ✓

=== READY TO COMMIT ===
All verifications complete. Proceeding with commit.
```

---

## ONE FUNCTION AT A TIME - THE GOLDEN RULE

### Why One Function at a Time?

**MANDATORY RULE: Refactor ONE function at a time, never batch multiple functions together.**

#### The Problem with Batching

When you batch multiple function renames/refactors together:
- ❌ **Cannot identify** which specific change caused test failures
- ❌ **Cannot revert** just the problematic change
- ❌ **Cannot debug** efficiently (too many variables changed)
- ❌ **Cannot build confidence** incrementally
- ❌ **Wastes time** when entire batch fails and must be redone
- ❌ **Loses progress** when you have to throw away working changes with broken ones

#### The Benefits of One-at-a-Time

When you refactor one function at a time:
- ✅ **Immediate feedback** - Know instantly if THIS change works
- ✅ **Easy debugging** - Only one thing changed, so you know where to look
- ✅ **Surgical rollback** - Revert just the broken change, keep the rest
- ✅ **Progressive confidence** - Each success builds on the last
- ✅ **Saveable progress** - User can save after each successful step
- ✅ **Clear history** - Git history shows exactly what changed when
- ✅ **Testable isolation** - Each change is independently verified
- ✅ **Always working** - Codebase remains in passing state at every commit

### How to Apply One-at-a-Time to Your Steps

When creating your step-by-step plan:

**Each step should refactor ONE function only:**
- ✅ CORRECT: "Step 1: Rename ESI.pack() to ESI.pack_esi()"
- ❌ WRONG: "Step 1: Rename all qualifier pack() methods"

**Even if functions are in the same file:**
- ✅ CORRECT: "Step 1: Rename Origin.pack(), Step 2: Rename NextHop.pack()"
- ❌ WRONG: "Step 1: Rename Origin.pack() and NextHop.pack()"

**Even if functions are conceptually related:**
- ✅ CORRECT: Six separate steps for six qualifiers
- ❌ WRONG: One step for all qualifiers together

### Common Scenarios

#### Multiple Functions in Same File
**Question:** File has 3 functions that all need renaming. Can I do them together?
**Answer:** NO. Do them one at a time in separate steps.

#### Related Functions Across Files
**Question:** ESI, Labels, EthernetTag are all "qualifiers". Can I rename them together?
**Answer:** NO. Each is a separate function with separate call sites and separate failure modes.

#### Base Class and Subclasses
**Question:** I have a base class and 10 subclasses. Must I do all 11 separately?
**Answer:** YES. Base class first (or last), then each subclass one at a time.

#### "But It's Just a Simple Rename"
**Question:** This is just renaming `pack()` to `pack_esi()`. It's mechanical. Can't I batch 5 of these?
**Answer:** NO.

**Reality:** "Simple" renames can fail for:
- Missed call sites in unusual places
- Inheritance/override issues
- Mock objects in tests
- Dynamic getattr() calls
- String-based dispatch
- Cached references
- Partial function application

You don't know which rename will hit these until you test it. One-at-a-time ensures you find out immediately.

### ALL TESTS MUST ALWAYS PASS

**MANDATORY RULE: Every refactoring step MUST leave the codebase in a passing state.**

- **NEVER commit code with failing tests**
- **NEVER proceed to the next function if current tests are failing**
- **100% test pass rate is MANDATORY at every single step**
- **EVERY commit represents working, passing code**

**If tests fail:**
1. **STOP** - Do not continue to other functions
2. **ANALYZE** - Understand why THIS function change failed
3. **FIX** - Correct the issue
4. **RETEST** - Run full test suite again
5. **ONLY PROCEED** when all tests pass

**There is NO acceptable state where tests are failing.** The codebase must ALWAYS be in a working, passing state after every single refactoring step.

### Step Size Guidelines

**Good step examples:**
- ✅ `Step 1: Rename Origin.pack() to pack_attribute() in origin.py`
- ✅ `Step 2: Update Origin cache calls to use pack_attribute() in origin.py`
- ✅ `Step 3: Rename NextHop.pack() to pack_attribute() in nexthop.py`

**Bad step examples:**
- ❌ `Step 1: Rename all attribute pack() methods` (too broad)
- ❌ `Step 1: Update origin.py` (too vague)
- ❌ `Step 1: Rename Origin.pack() and NextHop.pack()` (multiple functions)

### Exceptions (There Are None)

**Q:** Are there cases where batching is OK?
**A:** NO.

**Q:** What if they're really really related?
**A:** Still no. One at a time.

**Q:** What if I'm 100% sure it'll work?
**A:** You're not. One at a time.

**Q:** What if the user asks me to batch them?
**A:** Explain why one-at-a-time is better. Get buy-in. Proceed one-at-a-time.

---

## GIT COMMIT STRATEGY

### Commit Message Format

For function renames:
```
Refactor: Rename <Class>.<old_method>() to <Class>.<new_method>()
```

For function signature changes:
```
Refactor: Change <Class>.<method>() signature to accept <new_param>
```

**Always:**
- Use "Refactor:" prefix
- Name the specific function(s)
- Be clear about what changed
- Each commit = one function change

### When to Commit

**Commit ONLY when:**
- ✅ Function renamed
- ✅ All call sites updated
- ✅ All tests updated
- ✅ ALL tests pass
- ✅ Linting passes
- ✅ User approval obtained (if applicable)

**NEVER commit when:**
- ❌ Tests are failing
- ❌ Only partially complete
- ❌ "Will fix in next commit"
- ❌ Multiple functions changed together

### Example: Correct Git History

```
Commit 1: "Refactor: Rename ESI.pack() to ESI.pack_esi()"
- esi.py: pack() → pack_esi()
- 6 call sites updated
- Tests: 1376 passed ✓

Commit 2: "Refactor: Rename Labels.pack() to Labels.pack_labels()"
- labels.py: pack() → pack_labels()
- 10 call sites updated
- Tests: 1376 passed ✓

Commit 3: "Refactor: Rename EthernetTag.pack() to EthernetTag.pack_etag()"
- etag.py: pack() → pack_etag()
- 5 call sites updated
- Tests: 1376 passed ✓
```

**Every commit is a working, tested, verified state.**

---

## METRICS OF SUCCESS

Good refactoring sessions have:
- ✅ High number of small commits (one per function)
- ✅ **100% test pass rate at EVERY SINGLE STEP**
- ✅ **EVERY commit represents working, passing code**
- ✅ Clear git history showing progression
- ✅ No reverts needed (because each step was verified)
- ✅ User confidence in every change

Bad refactoring sessions have:
- ❌ Few large commits (many functions batched)
- ❌ Test failures discovered late
- ❌ **ANY commit with failing tests**
- ❌ **ANY step left in broken state**
- ❌ Unclear which change caused failure
- ❌ Multiple reverts and retries
- ❌ Lost work and wasted time

---

## REMEMBER

**The protocol only works if you actually follow it.**

**The Core Principles:**
1. **ONE FUNCTION AT A TIME** - Never batch, never skip
2. **ALL TESTS MUST ALWAYS PASS** - No exceptions, no "will fix later"
3. **PASTE PROOF AT EVERY STEP** - Show exact test output
4. **COMMIT ONLY WHEN PASSING** - Every commit is a working state

**The Discipline:**
- No shortcuts
- No assumptions
- No "it should work"
- Proof required at every step
- One function, fully tested, before moving to next
- User trust depends on this

**When in doubt: STOP and verify.**

**Refactoring is not about speed. It's about correctness, confidence, and maintainability. One function at a time ensures all three.**
