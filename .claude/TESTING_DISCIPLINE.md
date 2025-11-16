# Testing Discipline

**MANDATORY - NEVER claim success without testing.**

---

## Forbidden Phrases (without testing)

❌ "The tests pass"
❌ "All tests pass"
❌ "The code is fixed"
❌ "The fix is complete"
❌ "Everything works"
❌ "Ready for merge"

✅ ONLY say after running ALL required tests.

---

## Required Test Sequence

After ANY code change:

```bash
# 1. Linting
ruff format src && ruff check src

# 2. Unit tests
env exabgp_log_enable=false pytest ./tests/unit/

# 3. Functional tests (for affected functionality)
./qa/bin/functional encoding <test_id>
```

**ALL must pass before declaring success.**

---

## Workflow

1. Make code changes
2. Run ALL tests
3. Verify ALL pass
4. THEN tell user

❌ NEVER:
1. Make changes
2. Tell user it's fixed
3. Run tests
4. Discover failure

---

## Quick Reference

**Before saying "fixed"/"ready"/"working"/"complete":**

- [ ] `ruff format src && ruff check src` ✅
- [ ] `env exabgp_log_enable=false pytest ./tests/unit/` ✅
- [ ] `./qa/bin/functional encoding <test_id>` ✅

**No shortcuts. No exceptions. Every time.**

---

**Updated:** 2025-11-16
