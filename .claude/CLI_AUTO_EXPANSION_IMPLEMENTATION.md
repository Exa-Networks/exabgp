# CLI Auto-Expansion Implementation

**Date:** 2025-11-20
**Status:** ✅ Complete

## Summary

Implemented auto-expansion of unambiguous partial tokens in CLI tab completion. When user types partial commands that have only one possible completion, the system automatically expands them inline.

## Implementation

### Core Changes

**File:** `src/exabgp/application/cli.py`

1. **Auto-expansion logic** (`_try_auto_expand_tokens`):
   - Iterates through all tokens in the line
   - For each token, checks if it has exactly one completion in its context
   - If yes, expands it; otherwise keeps original
   - Returns tuple of (expanded_tokens, expansions_made)

2. **Line replacement via ctypes**:
   - Added `_get_rl_replace_line()` - accesses readline's `rl_replace_line` via ctypes
   - Added `_get_rl_forced_update_display()` - forces display update after replacement
   - Works with both GNU readline (Linux) and libedit (macOS)

3. **Enhanced completion flow** (`complete` method):
   - On first TAB press (state==0), tries auto-expansion
   - If expansions made and rl_replace_line available:
     - Replaces entire line with expanded version
     - If current word also has single completion, includes it
     - Updates display immediately
   - Falls back to normal completion if can't modify line

**File:** `src/exabgp/reactor/api/command/registry.py`

- Added `OPTION_DESCRIPTIONS` dict for completion metadata
- Added `get_option_description()` method

### Testing

**New test file:** `tests/unit/test_cli_completion.py`

8 test cases covering:
- Auto-expansion of unambiguous tokens
- Preservation of ambiguous tokens
- No modification of complete tokens
- Context-aware completion
- Multiple token expansion
- Exact match handling

## Test Results

✅ **All tests passing:**
- Linting: ruff format + ruff check (clean)
- Unit tests: 1637/1637 passed (including 8 new CLI completion tests)
- Functional encoding tests: 72/72 passed (100%)

## Behavior

### Example: `s n<TAB>`

**Before:**
- `s` remains `s` (ambiguous: show/shutdown/silence-ack)
- `n` completes to `neighbor`
- Result: `s neighbor`

**After (with unambiguous context):**
- If only one command starting with `s` has subcommand `n`, expands both
- Otherwise: expands only unambiguous tokens
- Result: depends on command structure

### Example: `show n<TAB>`

**Before:** Shows completion options
**After:** Line becomes `show neighbor ` (with trailing space, ready for next arg)

## Python 3.8 Compatibility

✅ Uses `Tuple[List[str], bool]` (not `tuple[...]`)
✅ Uses `Union`, not `|` operator
✅ All type annotations compatible with Python 3.8.1+

## Known Limitations

1. **Requires rl_replace_line:** Auto-expansion only works if ctypes can load readline library
2. **Platform-specific paths:** Uses `/usr/lib/libedit.dylib` (macOS) or `libreadline.so` (Linux)
3. **Silent fallback:** If rl_replace_line unavailable, falls back to normal completion

## Additional Feature: JSON Pretty-Printing

**Also implemented:** Automatic pretty-printing of JSON responses

### Implementation

Modified `OutputFormatter.format_command_output()` to:
1. Detect JSON output (starts with `{` or `[`)
2. Parse with `json.loads()`
3. Pretty-print with `json.dumps(indent=2, ensure_ascii=False)`
4. Apply color highlighting if terminal supports it
5. Fall back gracefully for invalid JSON

### Behavior

**Before:**
```
{"name":"test","value":123,"nested":{"key":"value"}}
```

**After:**
```
{
  "name": "test",
  "value": 123,
  "nested": {
    "key": "value"
  }
}
```

### Features

- **2-space indentation** for readability
- **Unicode preservation** (`ensure_ascii=False`) for international text
- **Color highlighting** (cyan for JSON)
- **Graceful fallback** for invalid JSON (no crash)
- **Empty output handling** (returns empty string)

### Testing

7 new test cases in `TestOutputFormatter`:
- Pretty-print JSON objects
- Pretty-print JSON arrays
- Unicode character handling
- Invalid JSON passthrough
- Non-JSON text passthrough
- Empty output handling
- Indent level verification

## Files Modified

- `src/exabgp/application/cli.py` (+146 lines)
- `src/exabgp/reactor/api/command/registry.py` (+16 lines)

## Files Created

- `tests/unit/test_cli_completion.py` (181 lines, 15 tests)
- `.claude/CLI_AUTO_EXPANSION_IMPLEMENTATION.md` (this file)

## Integration

Works seamlessly with existing:
- CommandShortcuts (shortcut expansion happens first)
- Neighbor IP completion (with descriptions)
- Option descriptions (enhanced display)
- macOS libedit single-TAB display

## Future Improvements

1. Context-aware disambiguation (analyze full command to resolve ambiguity)
2. Fuzzy matching for partial tokens
3. User configuration for auto-expansion behavior
4. Fallback implementation without rl_replace_line (pure Python line editing)
