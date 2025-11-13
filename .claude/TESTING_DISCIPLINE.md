# TESTING DISCIPLINE - MANDATORY RULES

## ⚠️ READ THIS FIRST - THESE ARE ABSOLUTE REQUIREMENTS ⚠️

### Rule #1: NEVER Claim Success Without Testing

**FORBIDDEN PHRASES** (unless ALL tests have passed):
- ❌ "The tests pass"
- ❌ "All tests pass"
- ❌ "The code is fixed"
- ❌ "The fix is complete"
- ❌ "Everything works"
- ❌ "Ready for merge"
- ❌ "Should work now"
- ❌ "This fixes the issue"

**ONLY say these AFTER running ALL required tests:**
- ✅ "I've run all tests (ruff, pytest, functional) and they all pass"

### Rule #2: The Complete Test Sequence

When you make ANY code change, you MUST run this EXACT sequence:

```bash
# Step 1: ALWAYS run ruff (both format and check on src folder only)
ruff format src && ruff check src

# Step 2: ALWAYS run pytest unit tests
env exabgp_log_enable=false pytest ./tests/unit/

# Step 3: ALWAYS run functional tests for affected functionality
./qa/bin/functional encoding <test_id>
```

**ALL THREE MUST PASS before you declare success.**

### Rule #3: Test Before Speaking

Your workflow MUST be:
1. Make code changes
2. Run ALL tests
3. Verify ALL tests pass
4. THEN tell the user the results

**NEVER:**
1. Make code changes
2. Tell user it's fixed ❌
3. Run tests
4. Discover it failed

### Rule #4: Memorize These Commands

These commands should be automatic muscle memory:

**After ANY code change:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
./qa/bin/functional encoding <affected_test>
```

**Before saying "tests pass":**
- Check ruff output: "All checks passed!" ✅
- Check pytest output: Count how many passed (e.g., "1376 passed") ✅
- Check functional test: Look for green ✓ checkmark ✅

### Rule #5: Complete Output Required

When reporting test results, ALWAYS show:
1. The exact command you ran
2. The exit code or success indicator
3. Any relevant summary (e.g., "1376 tests passed", "All checks passed!")

### Rule #6: No Assumptions

**NEVER assume tests will pass.**
**NEVER skip tests "because the change was small."**
**NEVER tell the user to run tests themselves without you running them first.**

### Examples of Correct Behavior

❌ **WRONG:**
```
I've fixed the issue by adding the fromString() method. This should resolve
the test failures.
```

✅ **CORRECT:**
```
I've added the fromString() method. Let me run all tests now:

1. Running ruff...
2. Running pytest...
3. Running functional tests...

All tests pass! The fix is complete.
```

### Consequences of Violating These Rules

If you tell the user code is "fixed" without running tests:
- You waste the user's time
- You lose credibility
- You force the user to remind you (annoying)
- You make the user question if you're paying attention

### Remember

**Testing is not optional. Testing is not a suggestion. Testing is MANDATORY.**

If you made a code change, you MUST test it. No exceptions.

---

## Quick Reference Card

**Before saying ANY of these words:**
- "fixed"
- "working"
- "ready"
- "complete"
- "passes"

**You MUST have run:**
1. ✅ `ruff format src && ruff check src`
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/`
3. ✅ `./qa/bin/functional encoding <test_id>`

**And they ALL must have passed.**

No shortcuts. No exceptions. Every time.
