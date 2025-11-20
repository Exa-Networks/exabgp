# Testing Discipline

**MANDATORY - NEVER claim success without testing AND regression prevention.**

---

## Forbidden Phrases (without testing + regression tests)

❌ "The tests pass"
❌ "All tests pass"
❌ "The code is fixed"
❌ "The fix is complete"
❌ "Everything works"
❌ "Ready for merge"

✅ ONLY say after:
1. Running ALL required tests
2. Ensuring appropriate regression tests exist

---

## Required Test Sequence

After ANY code change:

```bash
# Single command - runs ALL tests, exits on first failure
./qa/bin/test_everything
```

**Individual test commands (for reference):**
```bash
# 1. Linting
ruff format src && ruff check src

# 2. Unit tests
env exabgp_log_enable=false pytest ./tests/unit/

# 3. Functional encoding tests (all 72 tests)
./qa/bin/functional encoding

# 4. Functional decoding tests
./qa/bin/functional decoding

# 5. Configuration validation
./sbin/exabgp validate -nrv ./etc/exabgp/conf-ipself6.conf
```

**ALL must pass before declaring success.**

---

## Regression Prevention

**MANDATORY - ALL code changes MUST include appropriate tests.**

### Bug Fixes
✅ Add test that would have caught the bug
✅ Verify test fails without fix, passes with fix
✅ Place in tests/unit/ or qa/bin/functional as appropriate

### New Features
✅ Add unit tests for new logic
✅ Add functional tests for protocol/API changes
✅ Test both success and failure cases

### Refactoring
✅ Verify existing tests cover refactored code
✅ Add missing tests before refactoring
✅ All tests must pass at every step (see MANDATORY_REFACTORING_PROTOCOL.md)

### Test Coverage Requirements

**Unit tests (tests/unit/):**
- Logic changes
- Helper functions
- Data structure manipulation
- Error handling

**Functional tests (qa/bin/functional):**
- BGP protocol changes
- Message encoding/decoding
- API command changes
- Configuration parsing

**Both when applicable.**

### Examples

❌ WRONG:
1. Fix encoding bug
2. Run tests - all pass
3. Declare "fixed"

✅ CORRECT:
1. Fix encoding bug
2. Add functional test that would have caught it (qa/encoding/<test>.ci/.msg)
3. Verify test fails without fix
4. Apply fix
5. Run ALL tests - all pass
6. Declare "fixed"

---

## Workflow

1. Write/update regression tests
2. Make code changes
3. Run ALL tests
4. Verify ALL pass
5. THEN tell user

❌ NEVER:
1. Make changes
2. Tell user it's fixed
3. Run tests
4. Discover failure

❌ NEVER:
1. Fix bug
2. Tests pass
3. Declare "complete"
4. No regression test added

---

## Quick Reference

**Before saying "fixed"/"ready"/"working"/"complete":**

- [ ] Regression tests added/updated ✅
- [ ] `./qa/bin/test_everything` passes all 6 test suites ✅

**No shortcuts. No exceptions. Every time.**

---

**Updated:** 2025-11-20
