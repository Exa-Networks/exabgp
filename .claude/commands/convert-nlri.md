# Convert NLRI to Packed-Bytes-First Pattern

You are converting an NLRI class to the packed-bytes-first pattern. This pattern stores wire bytes directly and unpacks fields lazily on property access.

## Key Principles

1. **`_packed` is ALWAYS required** - no `None`, no conditionals in properties
2. **Two entry points only:**
   - `unpack_nlri()` - from existing wire Buffer (don't modify, just store)
   - `make_xxx()` - build NEW packed bytes from components, pass to `__init__`
3. **`@property` for all fields** - simple return, no conditionals
4. **No `make_empty()`** - breaks immutability

## Arguments

The user will provide the NLRI file path or name, e.g.:
- `/convert-nlri vpls` - convert VPLS NLRI
- `/convert-nlri evpn/mac` - convert EVPN MAC NLRI
- `/convert-nlri mup/isd` - convert MUP ISD NLRI

## Required Reading

Before starting, read these files:
1. `.claude/exabgp/PACKED_BYTES_FIRST_PATTERN.md` - The pattern documentation
2. `src/exabgp/bgp/message/update/nlri/vpls.py` - Reference (note: still has transitional builder mode)

## Workflow

Execute these steps in order:

### Step 1: Locate and Analyze the NLRI

1. Find the NLRI file based on user input
2. Read the entire file
3. Identify:
   - Wire format structure (what fields, what sizes, is there a length prefix?)
   - Current `__init__` signature
   - Current `pack_nlri` / `_pack_nlri_simple` implementation
   - Current `unpack_nlri` implementation
   - Any existing factory methods

4. Document the wire format:
   ```
   Wire format (N bytes total):
   [field1(X)] [field2(Y)] [field3(Z)] ...
    0:X         X:X+Y       ...
   ```

### Step 2: Check for Unit Tests

1. Search for existing tests:
   ```bash
   ls tests/unit/test_*.py | xargs grep -l "ClassName"
   ```

2. If tests exist, read them to understand coverage

3. If NO tests exist or coverage is insufficient, CREATE tests FIRST:
   - Test file: `tests/unit/test_{nlri_name}.py`
   - Required tests:
     - `test_create_basic` - Create with typical values
     - `test_pack_unpack_roundtrip` - Pack then unpack preserves data
     - `test_pack_format` - Verify wire format structure
     - `test_unpack_known_data` - Unpack known wire bytes
     - `test_json` - JSON output format
     - `test_str` - String representation
     - `test_feedback_*` - Validation feedback tests (if applicable)

4. Run the new tests to ensure they pass with current implementation:
   ```bash
   env exabgp_log_enable=false uv run pytest tests/unit/test_{nlri_name}.py -v
   ```

### Step 3: Convert to Packed-Bytes-First

Make these changes to the NLRI class:

#### 3.1 Update Class Docstring
```python
"""NLRI using packed-bytes-first pattern.

Stores wire bytes directly, unpacks fields on @property access.
"""
```

#### 3.2 Add Constants
```python
# Wire format length (including length prefix if present)
PACKED_LENGTH = N  # Document byte breakdown
```

#### 3.3 Update `__init__`
```python
def __init__(self, packed: bytes) -> None:
    """Create from packed wire-format bytes.

    Args:
        packed: N bytes wire format (ALWAYS required)

    Note: action defaults to UNSET, set after creation (announce/withdraw).
    """
    NLRI.__init__(self, AFI.xxx, SAFI.yyy)
    self.nexthop = IP.NoNextHop

    self._packed: bytes = packed  # ALWAYS required, never None
```

**No builder mode storage needed** - `_packed` is always present.
**Do NOT set `self.action`** - it defaults to `Action.UNSET` from base class, set after creation.

#### 3.4 Add Factory Method
```python
@classmethod
def make_xxx(cls, field1, field2, ...) -> 'ClassName':
    """Factory method to create from components.

    Used by configuration parsing - packs fields immediately.
    Note: action defaults to UNSET - caller must set after creation.
    """
    packed = (
        pack('!H', length)  # Include length prefix!
        + field1.pack()
        + pack('!H', field2)
        # ...
    )
    return cls(packed)
```

**No `make_empty()` needed** - configuration uses `make_xxx()` with all fields.
**Do NOT accept action parameter** - caller sets `nlri.action = action` after creation.

#### 3.5 Convert Fields to @property Methods (CRITICAL)

**You MUST create `@property` methods for EVERY field that was previously a direct attribute.**

This is the core of the pattern - fields are no longer stored as regular instance attributes. Instead, they are computed on-demand from `_packed` via properties.

For EACH semantic field:
```python
@property
def fieldN(self) -> Type:
    """Description - unpacked from wire bytes on access."""
    return Type(self._packed[START:END])  # ACCOUNT FOR LENGTH PREFIX OFFSET

@property
def fieldM(self) -> int:
    """Description - unpacked from wire bytes on access."""
    return unpack('!H', self._packed[START:END])[0]
```

**No setters needed** - NLRI is immutable after creation.

**Checklist for each field:**
- [ ] Remove direct assignment in `__init__` (e.g., `self.rd = ...`)
- [ ] Remove any `_field` storage variables
- [ ] Create `@property` getter that unpacks from `_packed`
- [ ] No conditional checks needed - `_packed` is always present

#### 3.6 Update `_pack_nlri_simple`
```python
def _pack_nlri_simple(self) -> Buffer:
    """Pack NLRI - returns stored wire bytes directly (zero-copy)."""
    return self._packed
```

**No conditional logic** - just return `_packed`.

#### 3.7 Update `unpack_nlri`
**CRITICAL: Include length prefix in packed bytes!**
```python
@classmethod
def unpack_nlri(cls, afi, safi, data, action, addpath, negotiated):
    # Read length prefix
    (length,) = unpack('!H', bytes(data[0:2]))
    total_length = 2 + length

    # CRITICAL: Start from byte 0, not byte 2!
    packed = bytes(data[0:total_length])  # Includes length prefix
    nlri = cls(packed)
    nlri.action = action

    return nlri, data[total_length:]
```

#### 3.8 Update Copy Methods (if present)
```python
def __copy__(self) -> 'ClassName':
    new = self.__class__.__new__(self.__class__)
    self._copy_nlri_slots(new)
    new._packed = self._packed  # bytes are immutable, safe to share
    return new
```

#### 3.9 Update Configuration Parser
Find the parser file (usually in `src/exabgp/configuration/`) and update:
- Replace direct constructor calls with `make_xxx()` factory method
- Pass all field values to the factory method
- No field assignment after creation (NLRI is immutable)

### Step 4: Update Tests for New Pattern

Add/update tests to cover:
- `test_unpack_fields` - Create from wire bytes, verify fields unpack correctly via @property
- `test_factory_method` - Create via factory method, verify pack returns correct bytes
- `test_zero_copy_pack` - Verify pack returns exact same bytes as input
- `test_immutable` - Verify NLRI has no setters (fields are read-only)

### Step 5: Run All Tests

```bash
# Run specific unit tests first
env exabgp_log_enable=false uv run pytest tests/unit/test_{nlri_name}.py -v

# If passing, run full test suite
./qa/bin/test_everything
```

### Step 6: Report Results

Report to user:
1. Wire format documented (with byte offsets)
2. Tests added/updated (list them)
3. Code changes made (summary)
4. Test results (all passing?)

## Critical Rules

1. **`_packed` is ALWAYS required** - No `None`, no builder mode, no conditionals in properties
2. **ALWAYS include length prefix in `_packed`** - Store `data[0:total]` not `data[2:total]`
3. **Property offsets must account for length prefix** - If length prefix is 2 bytes, field1 starts at byte 2, not byte 0
4. **Properties are simple returns** - Just `return Type(self._packed[START:END])`, no `if` checks
5. **Run tests after EVERY change** - Don't batch changes without verification
6. **Create tests BEFORE converting** - Ensures you don't break existing functionality

## Example Conversion

See `src/exabgp/bgp/message/update/nlri/vpls.py` for a complete reference implementation.

Wire format:
```
[length(2)] [RD(8)] [endpoint(2)] [offset(2)] [size(2)] [base(3)]
 0:2         2:10    10:12         12:14       14:16     16:19
```

Properties access bytes at offsets accounting for 2-byte length prefix.
