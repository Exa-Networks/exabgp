# Optional Trailing Semicolons

**Status:** 📋 Planning
**Created:** 2025-12-15
**Updated:** 2025-12-15

## Goal

Make trailing semicolons at end of configuration lines optional while keeping them required as separators between multiple commands on the same line. Full backward compatibility with existing configuration files.

## Current Behavior

### Tokenizer (`format.py`)
- Semicolons are in `eol = [';', '{', '}']` (line 71)
- When `;` encountered outside quotes, tokens are yielded and reset (lines 96-107)
- **Problem**: Lines 141-145 raise `ValueError` if leftover `word` or `parsed` at end of line

```python
# Current (lines 141-145)
if word:
    raise ValueError(f'invalid syntax line {nb_lines}: "{word}"')

if parsed:
    raise ValueError(f'invalid syntax line {nb_lines}: "{parsed}"')
```

### Parser (`parser.py`)
- `__call__` sets `self.end = self.line[-1]` (line 217)
- Last token is always the delimiter (`;`, `{`, `}`)

### Dispatch (`configuration.py`)
- Lines 724-744 check `parser.end`:
  - `';'` → Execute command
  - `'{'` → Enter block
  - `'}'` → Exit block
  - `not parser.end` → End of file
  - Otherwise → Error

### Example: Current vs Desired

**Current (required semicolons):**
```
neighbor 127.0.0.1 {
    router-id 10.0.0.2;
    local-as 65533;
    peer-as 65533;
}
```

**Desired (optional trailing semicolons):**
```
neighbor 127.0.0.1 {
    router-id 10.0.0.2
    local-as 65533
    peer-as 65533
}
```

**Multiple commands on one line (semicolon still required as separator):**
```
# These are equivalent:
router-id 10.0.0.2 ; local-as 65533
router-id 10.0.0.2 ; local-as 65533 ;   # trailing semicolon optional
```

## Design

### Approach: Newline as Implicit Semicolon

When a line ends without an explicit delimiter (`{`, `}`, or `;`), the tokenizer automatically appends `;` to the token list. This normalizes the input so downstream code (parser, dispatch) requires no changes.

### Key Insight

The tokenizer processes line-by-line. At end of each line:
- If there's a `parsed` list with content and no delimiter, currently an error is raised
- Instead, append `;` and yield - the line becomes a complete statement
- Parser and dispatch already handle `;` correctly
- No new marker types, no downstream changes needed

### Why This Works

Lines ending with `{` start a block - don't add `;`
Lines ending with `}` close a block - don't add `;`
Lines ending with `;` already have terminator - don't add `;`
Lines ending with content (no delimiter) - add implicit `;`

## Implementation Plan

### Single Change: Tokenizer Modification (`format.py`)

**File:** `src/exabgp/configuration/core/format.py`

**Changes (lines 141-145):**

```python
# Before:
if word:
    raise ValueError(f'invalid syntax line {nb_lines}: "{word}"')

if parsed:
    raise ValueError(f'invalid syntax line {nb_lines}: "{parsed}"')

# After:
if word:
    parsed.append((nb_lines, nb_chars - len(word), word))
    word = ''

if parsed:
    # Implicit semicolon: line ends without { } or ;
    # Add semicolon to make it a complete statement
    parsed.append((nb_lines, nb_chars, ';'))
    yield parsed
    parsed = []
```

### No Other Changes Required

- **Dispatch** (`configuration.py`): Already handles `;` correctly
- **Parser** (`parser.py`): Already handles `;` correctly
- **API** (`configuration.py`): Already adds `;` if missing (line 615)

## Files to Modify

| File | Lines | Change |
|------|-------|--------|
| `src/exabgp/configuration/core/format.py` | 141-145 | Add implicit `;` for lines without delimiter, yield instead of raise |

## Test Cases

### Unit Tests (new file: `tests/unit/configuration/test_optional_semicolon.py`)

1. **Single command without semicolon**
   - Input: `router-id 10.0.0.2`
   - Expected: Parses successfully

2. **Single command with semicolon (backward compat)**
   - Input: `router-id 10.0.0.2;`
   - Expected: Parses successfully

3. **Multiple commands on one line with separator**
   - Input: `router-id 10.0.0.2 ; local-as 65533`
   - Expected: Both commands parse successfully

4. **Multiple commands with trailing semicolon**
   - Input: `router-id 10.0.0.2 ; local-as 65533 ;`
   - Expected: Both commands parse successfully

5. **Block without trailing semicolon**
   - Input: `neighbor 127.0.0.1 { local-as 65533 }`
   - Expected: Parses successfully

6. **Nested blocks without semicolons**
   - Input: `neighbor 127.0.0.1 { static { route 10.0.0.0/24 { next-hop 1.2.3.4 } } }`
   - Expected: Parses successfully

7. **Mixed semicolons (some present, some absent)**
   - Input: Multi-line config with inconsistent semicolons
   - Expected: All lines parse successfully

### Functional Tests

- All 72 existing encoding tests must pass
- All existing configuration files in `etc/exabgp/` must parse
- Create new test configuration without trailing semicolons

## Edge Cases

1. **Empty lines** - `parsed` is empty → `if parsed:` is False → nothing yielded ✓
2. **Comment-only lines** (`# comment`) - `#` triggers `break`, `parsed` empty → nothing yielded ✓
3. **Content + comment** (`router-id 10.0.0.2 # comment`) - `parsed` has tokens → add `;` and yield ✓
4. **Line continuation with `\`** - Already handled in `set_file()` (parser.py lines 179-188)
5. **Quoted strings with semicolons** - Already handled (lines 97-99 check `quoted`)
6. **Block openers `{`** - Triggers yield with `{` as last token → no implicit `;` added ✓
7. **Block closers `}`** - Triggers yield with `}` as last token → no implicit `;` added ✓

### Comment Handling Detail

The tokenizer's comment handling (lines 86-94):
```python
if char in comment:
    if quoted:
        word += char
    else:
        if word:
            parsed.append(...)  # Note: existing bug appends '#' not word
            word = ''
        break  # Exit char loop, go to end-of-line handling
```

When `#` is encountered outside quotes:
- Any pending `word` is (should be) added to `parsed`
- Loop `break`s, falling through to lines 141-145
- If `parsed` is empty (comment-only line) → nothing yielded
- If `parsed` has content → implicit `;` added and yielded

## Backward Compatibility

- Existing configs with semicolons continue to work (explicit `;` still accepted)
- Configs without trailing semicolons now work (implicit `;` injected by tokenizer)
- API commands unchanged (auto-add `;` behavior in `partial()` preserved)
- No configuration file migration required

## Risks

1. **Ambiguous multi-line statements**: A command split across lines without continuation character could be misinterpreted. Mitigated by: line continuation with `\` is already supported and explicit.

2. **Error message clarity**: Need clear error messages when syntax is wrong. The tokenizer should still detect truly malformed input (e.g., unclosed quotes).

3. **Minimal risk**: Since we inject `;` at the tokenizer level, all downstream code sees valid `;`-terminated statements - no special handling needed.

## Progress

- [ ] Modify tokenizer (`format.py` lines 141-145)
- [ ] Unit tests for optional semicolons
- [ ] Verify all existing tests pass (`./qa/bin/test_everything`)
- [ ] Test with all `etc/exabgp/*.conf` files
- [ ] Create example config without semicolons

## Resume Point

Not started.

---

**Updated:** 2025-12-15
