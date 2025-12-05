# Plan: Refactor API with Parallel v4/v6 Dispatchers

## Status: IN PROGRESS

## Progress

### Completed
- [x] Create `dispatch/common.py` - Handler type, exceptions, COMMANDS list
- [x] Create `dispatch/v6.py` - dispatch_v6() implementation
- [x] Create `dispatch/v4.py` - dispatch_v4() implementation
- [x] Create `dispatch/__init__.py` - exports
- [x] Update `API` class in `__init__.py` - use new dispatchers, remove Command inheritance
- [x] Update `reactor.py` handlers - new signature (peers, command)
- [x] Update `announce.py` handlers - new signature (peers, command)

### Remaining
- [ ] Update `neighbor.py` handlers - new signature (peers, command)
- [ ] Update `peer.py` handlers - new signature (peers, command)
- [ ] Update `rib.py` handlers - new signature (peers, command)
- [ ] Update `watchdog.py` handlers - new signature (peers, command)
- [ ] Delete obsolete files: `transform.py`, `dispatch.py` (old), `command/command.py`
- [ ] Run `./qa/bin/test_everything` to verify

## Resume Point

Continue by updating the remaining handler files with new signature:
```python
def handler(self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool) -> bool:
```

Files to update:
1. `src/exabgp/reactor/api/command/neighbor.py` - Remove @Command.register, update signature
2. `src/exabgp/reactor/api/command/peer.py` - Remove @Command.register, update signature
3. `src/exabgp/reactor/api/command/rib.py` - Remove @Command.register, update signature, remove extract_neighbors calls
4. `src/exabgp/reactor/api/command/watchdog.py` - Remove @Command.register, update signature

Then delete:
- `src/exabgp/reactor/api/transform.py`
- `src/exabgp/reactor/api/dispatch.py` (old single file)
- `src/exabgp/reactor/api/command/command.py`

## Architecture Summary

### New Handler Signature
```python
Handler = Callable[['API', 'Reactor', str, list[str], str, bool], bool]
# (api, reactor, service, peers, command, use_json)
```

### New Flow
```
v4 command → dispatch_v4() → (handler, peers, command) → handler
v6 command → dispatch_v6() → (handler, peers, command) → handler
```

### Files Created
- `src/exabgp/reactor/api/dispatch/__init__.py`
- `src/exabgp/reactor/api/dispatch/common.py`
- `src/exabgp/reactor/api/dispatch/v4.py`
- `src/exabgp/reactor/api/dispatch/v6.py`

### Files Modified
- `src/exabgp/reactor/api/__init__.py` - API class, no longer inherits from Command
- `src/exabgp/reactor/api/command/reactor.py` - All handlers updated
- `src/exabgp/reactor/api/command/announce.py` - All handlers updated
