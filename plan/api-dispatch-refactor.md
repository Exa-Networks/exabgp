# Plan: Refactor API with Tree-Based Dictionary Dispatch

## Status: IN PROGRESS - Phase 1-4 Complete

## Goal

Refactor the API dispatch system to use tree-based dictionary routing with proper Tokeniser usage:
1. v6 dispatcher uses tree-based dict structure with Tokeniser ✅
2. v4 dispatcher translates commands to v6 format and delegates to v6 (pending)
3. All handlers receive clean v6 format commands (pending)

## Progress

### Phase 1: Update Tokeniser ✅
- Added `consumed` counter to track token consumption
- Added `_get()` and `_peek()` helper methods
- Commit: 98878dee

### Phase 2: Add Tree Dispatch Infrastructure ✅
- Added to `dispatch/common.py`:
  - `DispatchTree`, `DispatchNode` type aliases
  - `SELECTOR_KEY` constant
  - `tokenise_command()`, `remaining_string()` functions
  - `dispatch()` tree walker function
  - `extract_selector()` using peek/consume pattern
- Commit: 98878dee

### Phase 3: Refactor v6 Dispatcher ✅
- Replaced 352-line if/elif chain with tree-based dictionary
- Tree structure clearly shows command hierarchy
- `dispatch_v6()` now uses tree dispatch
- Commit: 98878dee

### Phase 4: Add v6_announce/v6_withdraw Dispatchers ✅
- Added dispatcher functions that route to specific handlers
- Currently prepends "announce"/"withdraw" prefix for backward compatibility
- Commit: 98878dee

### Phase 5: Update API Class (pending)
- Minor changes to use new dispatch return type

### Phase 6: Update api_* Methods for Clean Format (pending)
- Update `api_route()`, `api_flow()`, etc. to accept clean format
- Remove action prefix requirement from handlers
- Remove prefix prepending in v6_announce/v6_withdraw

### Phase 7: Refactor v4 to Translate and Delegate (pending)
- Replace v4 dispatch logic with translation to v6 format
- Delegate to v6 dispatcher

## Architecture

### Tree Structure (v6.py)
```python
tree = {
    '#': comment_handler,
    'daemon': {
        'shutdown': shutdown_handler,
        'reload': reload_handler,
        ...
    },
    'peer': {
        'list': list_neighbor,
        'show': show_neighbor,
        SELECTOR_KEY: {  # *, IP, or [bracket] selector
            'announce': v6_announce,
            'withdraw': v6_withdraw,
            'show': show_neighbor,
            'teardown': teardown,
        },
    },
    ...
}
```

### Dispatch Flow
```
Command: "peer * announce route 10.0.0.0/24 next-hop 1.2.3.4"
    ↓
dispatch_v6() creates Tokeniser, replenishes with tokens
    ↓
dispatch() walks tree:
  - consumes 'peer'
  - sees '*' is selector start (SELECTOR_KEY)
  - extract_selector() consumes '*', returns all peers
  - consumes 'announce'
  - returns (v6_announce, peers)
    ↓
remaining_string() = "route 10.0.0.0/24 next-hop 1.2.3.4"
    ↓
v6_announce() prepends "announce", calls announce_route()
```

### Files Modified
- `src/exabgp/configuration/core/parser.py` - Tokeniser.consumed counter
- `src/exabgp/reactor/api/dispatch/common.py` - Tree dispatch infrastructure
- `src/exabgp/reactor/api/dispatch/v6.py` - Tree-based dispatch
- `src/exabgp/reactor/api/dispatch/__init__.py` - New exports
- `src/exabgp/reactor/api/command/announce.py` - v6_announce/v6_withdraw

### Documentation Added
- `.claude/exabgp/TOKENISER_USAGE.md` - Tokeniser usage patterns
