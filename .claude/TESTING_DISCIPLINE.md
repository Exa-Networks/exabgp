# Testing Discipline

NEVER claim success without testing AND regression tests.

---

## 🚨 BLOCKING RULE: No Tests = Not Done 🚨

**MANDATORY:** Every code change MUST include corresponding tests.

❌ Cannot say "done"/"fixed"/"complete" without listing test files added/updated
✅ Must explicitly name: `tests/unit/test_X.py` or `qa/encoding/X.ci` etc.

---

## Forbidden Phrases (Without Testing + Regression Tests)

❌ "The tests pass" ❌ "All tests pass"
❌ "The code is fixed" ❌ "The fix is complete"
❌ "Everything works" ❌ "Ready for merge"

✅ ONLY say after:
1. Running ALL tests
2. Ensuring regression tests exist

---

## Required Test Sequence

After ANY code change:

```bash
./qa/bin/test_everything  # ALL tests, exits on first failure
```

---

## Regression Prevention (MANDATORY)

ALL code changes MUST include tests.

**Bug fixes:**
✅ Add test that would have caught bug
✅ Verify test fails without fix, passes with fix

**New features:**
✅ Add unit tests for logic
✅ Add functional tests for protocol/API changes
✅ Test success + failure cases

**Refactoring:**
✅ Verify existing tests cover code
✅ Add missing tests before refactoring
✅ All tests pass at every step

**Test location:**
- Unit tests → `tests/unit/`
- Functional tests → `qa/bin/functional`

---

## Workflow

1. Write/update regression tests
2. Make code changes
3. Run ALL tests
4. Verify ALL pass
5. THEN tell user

❌ NEVER:
1. Make changes → tell user "fixed" → run tests → discover failure
2. Fix bug → tests pass → declare "complete" → no regression test added

---

## Quick Reference

Before saying "fixed"/"ready"/"working"/"complete":

- [ ] Regression tests added/updated
- [ ] `./qa/bin/test_everything` passes all 6 suites

**No shortcuts. No exceptions. Every time.**

---

## ENFORCEMENT

Before saying "fixed"/"ready"/"complete":
```bash
./qa/bin/test_everything
```
- [ ] Command run: `<paste command>`
- [ ] Output: `<paste showing all 6 suites passed>`
- [ ] Exit code: 0
- [ ] Tests added/updated: `<list specific test files>`
  - If bug fix: test that reproduces the bug
  - If new feature: unit tests + functional tests if protocol/API
  - If refactoring: verified existing tests cover changes OR added missing tests

**If ANY unchecked: NOT DONE. STOP.**

---

## VIOLATION DETECTION

**If I say these without enforcement checklist above, I'm violating:**
- "The tests pass"
- "All tests pass"
- "Fixed"
- "Complete"
- "Ready"
- "Working"

**Auto-fix:** Stop. Run `./qa/bin/test_everything`. Paste output. Then claim success.

**If I claim completion without listing test files, I'm violating.**

Auto-fix: STOP. Ask yourself "What test file did I add/update?" If none: NOT DONE.
