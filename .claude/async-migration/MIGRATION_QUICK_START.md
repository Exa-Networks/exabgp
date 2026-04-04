# Async Migration - Quick Start Guide

This guide helps you start the migration immediately with clear next steps.

---

## TL;DR - What To Do Now

1. **Read:** `ASYNC_MIGRATION_PLAN.md` (full plan)
2. **Start with:** PR #1 - Async Infrastructure
3. **Test stability:** Run all tests before any changes
4. **Work incrementally:** One PR at a time, never skip infrastructure

---

## Pre-Migration Checklist

Before starting PR #1, complete these tasks:

```bash
# 1. Ensure you're on the right branch
git status
# Should show: claude/convert-generators-to-async-011CUwFUB42rVxbv6Uf6XFQw

# 2. Run full test suite and record baseline
PYTHONPATH=src python -m pytest tests/ -v --cov=src/exabgp > baseline_tests.log 2>&1

# 3. Record current performance (if tools available)
# Run any performance tests you have

# 4. Document current behavior
./qa/bin/functional encoding --list > baseline_functional.log 2>&1

# 5. Create PR branch for infrastructure
git checkout -b async-pr-01-infrastructure
```

---

## Your First PR: Infrastructure (#1)

### What You'll Do
Modify `src/exabgp/reactor/asynchronous.py` to support both generators AND coroutines.

### Step-by-Step

#### 1. Read the current file
```bash
cat src/exabgp/reactor/asynchronous.py
```

#### 2. Add imports at the top
```python
import asyncio
import inspect
```

#### 3. Add helper method to ASYNC class
```python
def _is_coroutine(self, callback):
    """Check if callback is a coroutine or generator"""
    return inspect.iscoroutine(callback) or inspect.iscoroutinefunction(callback)
```

#### 4. Modify the `run()` method
```python
async def run(self):
    """Execute scheduled callbacks (both generators and coroutines)"""
    if not self._async:
        return False

    length = range(self.LIMIT)
    uid, callback = self._async.popleft()

    for _ in length:
        try:
            # Support both old (generator) and new (coroutine) style
            if inspect.isgenerator(callback):
                # Old style: resume generator
                next(callback)
            elif inspect.iscoroutine(callback):
                # New style: await coroutine
                await callback
            else:
                # If it's a coroutine function, call it first
                if inspect.iscoroutinefunction(callback):
                    await callback()
                else:
                    next(callback)
        except StopIteration:
            # Generator completed, get next one
            if not self._async:
                return False
            uid, callback = self._async.popleft()
        except Exception as exc:
            log.error('async | %s | problem with callback' % uid, 'reactor')
            if not self._async:
                return False
            uid, callback = self._async.popleft()

    self._async.appendleft((uid, callback))
    return True
```

#### 5. Update schedule method (add type hints for clarity - optional)
```python
def schedule(self, uid, command, callback):
    """
    Schedule a callback (generator or coroutine) for execution

    Args:
        uid: Unique identifier
        command: Command string
        callback: Generator or coroutine to execute
    """
    log.debug('async | %s | %s' % (uid, command), 'reactor')
    self._async.append((uid, callback))
```

#### 6. Test your changes
```bash
# Run tests to ensure backward compatibility
PYTHONPATH=src python -m pytest tests/ -v

# Compare with baseline
# All tests should still pass!
```

#### 7. Create test for new functionality
Create `tests/unit/test_async_infrastructure.py`:

```python
import asyncio
import pytest
from exabgp.reactor.asynchronous import ASYNC


def test_async_supports_generators():
    """Test that ASYNC still works with generators"""
    async_handler = ASYNC()
    results = []

    def gen_callback():
        results.append(1)
        yield
        results.append(2)
        yield

    async_handler.schedule('test', 'test-gen', gen_callback())

    # Run event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_handler.run())

    assert 1 in results


@pytest.mark.asyncio
async def test_async_supports_coroutines():
    """Test that ASYNC works with new coroutines"""
    async_handler = ASYNC()
    results = []

    async def coro_callback():
        results.append(1)
        await asyncio.sleep(0)
        results.append(2)

    async_handler.schedule('test', 'test-coro', coro_callback())
    await async_handler.run()

    assert 1 in results
    assert 2 in results


@pytest.mark.asyncio
async def test_async_mixed_workload():
    """Test that ASYNC handles both generators and coroutines"""
    async_handler = ASYNC()
    results = []

    def gen_callback():
        results.append('gen')
        yield

    async def coro_callback():
        results.append('coro')
        await asyncio.sleep(0)

    async_handler.schedule('test1', 'test-gen', gen_callback())
    async_handler.schedule('test2', 'test-coro', coro_callback())

    await async_handler.run()

    assert 'gen' in results
    assert 'coro' in results
```

#### 8. Commit your changes
```bash
git add src/exabgp/reactor/asynchronous.py
git add tests/unit/test_async_infrastructure.py
git commit -m "[async-migration] PR #1: Add async/await infrastructure to ASYNC class

- Modified ASYNC.run() to support both generators and coroutines
- Added inspect module for type checking
- Maintains backward compatibility with existing generator code
- Added unit tests for new functionality

Testing: All existing tests pass, new tests verify coroutine support
Risk: Medium (core infrastructure change with backward compatibility)
Generators converted: 0 (infrastructure only)"
```

#### 9. Push and create PR
```bash
# Push to remote
git push -u origin async-pr-01-infrastructure

# Create PR (if gh CLI available, otherwise create manually)
gh pr create \
  --title "PR #1: Add async/await infrastructure to ASYNC class" \
  --body "See ASYNC_MIGRATION_PLAN.md for details. This is PR #1 of 28 in the generator migration." \
  --base claude/convert-generators-to-async-011CUwFUB42rVxbv6Uf6XFQw
```

---

## What Comes Next?

After PR #1 is merged:

### PR #2: Update Main Event Loop
- File: `src/exabgp/reactor/loop.py`
- Convert main `run()` to async def
- Update all calls to `self.asynchronous.run()` to use await

### PR #3: Add Async Testing Utilities
- Create test helpers for async code
- Add fixtures for async testing

Then you can move to the **Critical Path** (PRs 4-8).

---

## Common Issues & Solutions

### Issue: `RuntimeError: This event loop is already running`
**Solution:** Use `asyncio.create_task()` or ensure you're not nesting event loops

### Issue: Tests hang with async code
**Solution:** Add timeout decorators:
```python
@pytest.mark.timeout(5)
async def test_something():
    ...
```

### Issue: Generator and coroutine mixing fails
**Solution:** Check the ASYNC.run() method handles both types correctly with inspect module

---

## Testing Checklist for Each PR

Before considering a PR complete:

- [ ] All unit tests pass: `PYTHONPATH=src python -m pytest tests/unit/ -v`
- [ ] All fuzz tests pass: `PYTHONPATH=src python -m pytest tests/fuzz/ -v`
- [ ] Coverage hasn't decreased: `PYTHONPATH=src python -m pytest tests/ --cov=src/exabgp`
- [ ] No performance regression (if measurable)
- [ ] Code reviewed (if team available)
- [ ] Documentation updated (if public API changed)
- [ ] Commit message follows format
- [ ] Can rollback cleanly if needed

---

## Progress Tracking

After each PR, update `MIGRATION_PROGRESS.md`:

```markdown
## Progress Update: [Date]

### Completed PRs
- [x] PR #1: Async Infrastructure (merged [date])

### In Progress
- [ ] PR #2: Event Loop (in review)

### Stats
- Generators converted: 0/150 (0%)
- Tests passing: 100%
- PRs merged: 1/28 (4%)

### Next Session
Start PR #2 after #1 merges
```

---

## Need Help?

1. **Refer to the plan:** `ASYNC_MIGRATION_PLAN.md`
2. **Check patterns:** Appendix B has common conversion patterns
3. **Review dependencies:** Appendix shows which PRs depend on others
4. **Session handoff:** Use Appendix D template if pausing work

---

## Quick Reference: File Priority

**MUST CONVERT (Do these first):**
1. ✅ `reactor/asynchronous.py` - Infrastructure (PR #1)
2. ⏳ `reactor/loop.py` - Event loop (PR #2)
3. ⏳ `reactor/api/command/announce.py` - 30 generators (PRs #4-6)
4. ⏳ `reactor/protocol.py` - 14 generators (PR #7)
5. ⏳ `reactor/peer.py` - 9 generators (PR #8)

**DO NOT MODIFY (Keep stable for testing):**
- ❌ `tests/unit/test_connection_advanced.py`
- ❌ `tests/fuzz/test_connection_reader.py`
- ❌ `tests/unit/test_route_refresh.py`

---

## Success Criteria for PR #1

- [x] ASYNC class supports generators (backward compatible)
- [x] ASYNC class supports coroutines (new feature)
- [x] All existing tests pass
- [x] New tests verify coroutine support
- [x] No performance regression
- [x] Documentation updated (docstrings)

Once all checked, PR #1 is ready for review/merge!

---

**Ready to start? Begin with the Pre-Migration Checklist above!**
