# MANDATORY REFACTORING PROTOCOL

**Exists due to:** 95 files refactored, 72 test failures, full revert. No verification between steps.

---

## PHASE 0: PLANNING

Write numbered steps. Each MUST have:
```
Step N: [Action] [What] in [Where]
  Files: [exact paths]
  Verification: [exact command]
  Expected: "0 failures"
```

❌ Vague: "Rename methods"
✅ Specific: "Rename ESI.pack() to pack_esi() in nlri/qualifier/esi.py"

**Plan Requirements:**
- [ ] Every step numbered
- [ ] Exact file paths
- [ ] Verification command
- [ ] Expected output
- [ ] Final step: full test suite
- [ ] No vague language

**Get user approval. DO NOT proceed without approval.**

---

## PHASE 1-N: EXECUTION

```
=== STEP N ===
[Make changes]
Verification: [run command]
OUTPUT:
[PASTE EXACT OUTPUT - NO SUMMARY]
Result: PASS ✓
=== STEP N COMPLETE ===
```

**Rules:**
✅ Announce step
✅ Complete ONLY that step
✅ Run verification
✅ PASTE EXACT OUTPUT
✅ Stop if failures

❌ Skip verification
❌ Batch steps
❌ Summarize output
❌ Proceed with failures

---

## PHASE FINAL: PRE-COMMIT

**Before ANY commit:**

```bash
./qa/bin/test_everything
```
**PASTE OUTPUT - all 6 suites passed**

**Checklist:**
- [ ] `./qa/bin/test_everything` passed (proof pasted)
- [ ] `git status` reviewed
- [ ] User approval

**If ANY unchecked: DO NOT COMMIT**

---

## ONE FUNCTION AT A TIME

**MANDATORY: ONE function per step. No batching.**

**Why:**
- Immediate feedback
- Easy debugging
- Surgical rollback
- Always working

✅ "Step 1: ESI.pack() → pack_esi()" "Step 2: Labels.pack() → pack_labels()"
❌ "Step 1: Rename all qualifier pack() methods"

**No exceptions.**

### All Tests Always Pass

**100% pass rate at every step.**

If tests fail:
1. STOP
2. ANALYZE why THIS change failed
3. FIX it
4. RETEST full suite
5. PROCEED only when all pass

---

## GIT STRATEGY

**Commit messages:**
```
Refactor: Rename <Class>.<old>() to <Class>.<new>()
```

**When to commit:**
✅ Function renamed + all call sites + ALL tests pass + linting passes
❌ Tests failing, partial work, "will fix next"

**One function = one commit.**

---

## ENFORCEMENT

Cannot proceed without pasting proof current step passed.

---

## REMEMBER

1. ONE FUNCTION AT A TIME
2. ALL TESTS MUST ALWAYS PASS
3. PASTE PROOF AT EVERY STEP
4. COMMIT ONLY WHEN PASSING

**When in doubt: STOP and verify.**

---

## ENFORCEMENT

For EACH step before proceeding to next:
```
=== STEP N ===
Verification: <command>
OUTPUT:
<FULL OUTPUT PASTED - NO SUMMARY>
Exit code: 0
Result: PASS ✓
```
- [ ] Output pasted (not summarized)
- [ ] Exit code 0
- [ ] ALL tests passed (not "most tests")

**If ANY unchecked: STOP. Fix current step.**

Before ANY commit:
- [ ] `./qa/bin/test_everything` run
- [ ] Output pasted showing all 6 suites passed
- [ ] User approval obtained

**If ANY unchecked: DO NOT COMMIT.**

---

## VIOLATION DETECTION

**If I do these, I'm violating:**
- Batch multiple steps together
- Summarize test output instead of pasting
- Proceed with ANY test failures
- Skip verification command
- Commit without full test suite passing

**Auto-fix:** Stop. Run verification. Paste output. Wait for pass before next step.

---

## See Also

- TESTING_PROTOCOL.md - Test requirements at each step
- VERIFICATION_PROTOCOL.md - Verification before proceeding
- GIT_VERIFICATION_PROTOCOL.md - Git workflow during refactoring

---

**Updated:** 2025-11-30
