# MANDATORY REFACTORING PROTOCOL

**Exists due to:** 2025-11-16 failure - 95 files refactored, 72 test failures, full revert, all work lost.

**Root cause:** No verification between steps. Assumed tests passed without running them.

---

## PHASE 0: PLANNING

### Write Numbered Steps

Each step MUST have:
```
Step N: [Action] [What] in [Where]
  Files: [exact paths]
  Verification: [exact command]
  Expected: [expected output - "0 failures"]
```

❌ Vague: "Rename methods" "Update files"
✅ Specific: "Rename ESI.pack() to pack_esi() in nlri/qualifier/esi.py"

### Plan Requirements

- [ ] Every step numbered
- [ ] Every step has exact file paths
- [ ] Every step has verification command
- [ ] Every step has expected output
- [ ] Steps ordered logically
- [ ] Final step: full test suite
- [ ] No vague language ("various", "some", "multiple")

### Get User Approval

Present complete plan. **DO NOT proceed without approval.**

---

## PHASE 1-N: EXECUTION

### For Each Step

```
=== STEP N ===
[Make changes for THIS step only]

Verification: [run command]
OUTPUT:
[PASTE EXACT OUTPUT - DO NOT SUMMARIZE]

Result: PASS ✓
=== STEP N COMPLETE ===
```

### Rules

✅ Announce step before starting
✅ Complete ONLY that step
✅ Run verification
✅ **PASTE EXACT OUTPUT** (no summary)
✅ Declare completion
✅ Stop if ANY failures

❌ Skip verification
❌ Batch multiple steps
❌ Summarize output
❌ Proceed with failures

---

## PHASE FINAL: PRE-COMMIT

**Before ANY git commit:**

### 1. Run Complete Test Suite
```bash
./qa/bin/test_everything
```
**PASTE OUTPUT - Must show all 6 test suites passed**

This runs:
- Ruff format
- Ruff check
- Unit tests (1376 tests)
- Functional encoding tests (72 tests)
- Functional decoding tests
- Configuration validation

### 2. Checklist

- [ ] `./qa/bin/test_everything` passed (proof pasted)
- [ ] `git status` reviewed
- [ ] User approval obtained

**If ANY box unchecked: DO NOT COMMIT**

---

## ONE FUNCTION AT A TIME

**MANDATORY: Refactor ONE function per step, never batch.**

**Why:**
- ✅ Immediate feedback if THIS change works
- ✅ Easy debugging - only one thing changed
- ✅ Surgical rollback - revert just the broken change
- ✅ Always working - codebase passes tests at every step

**Examples:**
- ✅ "Step 1: ESI.pack() → pack_esi()" "Step 2: Labels.pack() → pack_labels()"
- ❌ "Step 1: Rename all qualifier pack() methods"

**No exceptions.** Even if functions are in same file, related, or "simple".

### All Tests Must Always Pass

**100% pass rate MANDATORY at every step.**

If tests fail:
1. STOP - no other functions
2. ANALYZE - why THIS change failed
3. FIX - correct the issue
4. RETEST - full suite again
5. ONLY PROCEED when all tests pass

**No acceptable state with failing tests.**

---

## GIT STRATEGY

### Commit Messages
```
Refactor: Rename <Class>.<old>() to <Class>.<new>()
```

### When to Commit
✅ Function renamed, all call sites updated, ALL tests pass, linting passes
❌ Tests failing, partial work, "will fix next"

### One Function = One Commit
Every commit represents working, tested, verified code.

---

## ENFORCEMENT

**This protocol is MANDATORY.**

Violating it:
- Wastes time (reverts)
- Loses work
- Breaks trust

**The forcing function:** Cannot proceed without pasting proof current step passed.

---

## REMEMBER

1. **ONE FUNCTION AT A TIME**
2. **ALL TESTS MUST ALWAYS PASS**
3. **PASTE PROOF AT EVERY STEP**
4. **COMMIT ONLY WHEN PASSING**

**When in doubt: STOP and verify.**
