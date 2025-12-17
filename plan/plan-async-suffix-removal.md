# Plan: Remove `_async` Suffix from API Methods

**Status:** 📋 Planning
**Created:** 2025-12-17
**Last Updated:** 2025-12-17

## Goal

Remove all `_async` suffixes from function names in the reactor API. Async functions should just be named normally (e.g., `answer_done` not `answer_done_async`).

## Current State

In `src/exabgp/reactor/api/processes.py`:
- `_answer` (private sync) and `_answer_async` (private async)
- `answer_done` (sync) and `answer_done_async` (async)
- `answer_error` (sync) and `answer_error_async` (async)

Missing method that's being called:
- `answer_async` in route.py - called 6 times but doesn't exist

## Proposed Changes

### Phase 1: Add Missing `answer` Method
- Add `answer(self, service: str, data: Any)` method to Processes
- Should handle JSON serialization of arbitrary data
- This fixes the mypy `attr-defined` errors in route.py

### Phase 2: Merge Async Methods
- Make `answer_done` async (merge `answer_done_async` into it)
- Make `answer_error` async (merge `answer_error_async` into it)
- Make `_answer` async (merge `_answer_async` into it)
- Remove the `_async` suffixed versions

### Phase 3: Update All Callers
Files to update:
- `src/exabgp/reactor/api/command/announce.py` (~70 calls)
- `src/exabgp/reactor/api/command/route.py` (~15 calls)
- `src/exabgp/reactor/api/command/group.py` (~10 calls)
- `src/exabgp/reactor/api/command/peer.py` (~10 calls)
- `src/exabgp/reactor/api/command/rib.py` (~15 calls)
- `src/exabgp/reactor/api/command/reactor.py` (~25 calls)
- `src/exabgp/reactor/api/command/neighbor.py` (~15 calls)
- `src/exabgp/reactor/api/command/watchdog.py` (~2 calls)
- `src/exabgp/reactor/api/__init__.py` (~5 calls)

Changes needed:
- `answer_done_async` -> `answer_done` (already correct name, just remove `_async`)
- `answer_error_async` -> `answer_error` (already correct name, just remove `_async`)
- `answer_async` -> `answer` (new method)
- Sync callers need to be converted to async patterns

### Phase 4: Handle Sync Callers
Some code calls sync versions without `await`. Options:
1. Convert those code paths to async
2. Keep sync wrappers that block on async

## Files Affected

- `src/exabgp/reactor/api/processes.py` - Main changes
- `src/exabgp/reactor/api/command/*.py` - Update all callers
- `src/exabgp/reactor/api/__init__.py` - Update callers

## Testing

- Run `./qa/bin/test_everything` after changes
- Verify functional encoding/decoding tests pass
- Test API commands manually if needed

## Notes

- This is a breaking change for any external code using these methods
- The sync versions are used in non-async contexts - need careful handling
