# Plan: MUP JSON Name Format - API Version-dependent Naming

**Status:** 📋 Planning
**Created:** 2025-12-10
**Updated:** 2025-12-10

## Goal

Change MUP route type names in JSON output to use different formats based on **API version**:
- **API v4 (legacy)**: Keep CamelCase names (backward compatibility)
- **API v6 (current)**: Use kebab-case RFC-aligned names

## Backward Compatibility Requirement

**CRITICAL: Do NOT break existing API v4 consumers.**

The current JSON output uses CamelCase names like `Type2SessionTransformedRoute`. Existing users parsing API v4 JSON depend on these names. Changing them would break their code.

For API v6 (current default), we can introduce the cleaner RFC-aligned kebab-case format.

## Existing Infrastructure

The JSON encoder already has full backward compatibility support:
- `JSON.use_v4_json` flag (set True for API v4 via `V4JSON` wrapper)
- `_nlri_to_json()` method in `json.py` checks this flag:
  - If `use_v4_json=True`: calls `nlri.v4_json()`
  - If `use_v4_json=False`: calls `nlri.json()`
- Base `NLRI.v4_json()` defaults to calling `json()` - subclasses override for differences

**This pattern is already used by FlowSpec** (`src/exabgp/bgp/message/update/nlri/flow.py:1016`)

## RFC Reference

**Source:** [draft-mpmz-bess-mup-safi-03](https://datatracker.ietf.org/doc/html/draft-mpmz-bess-mup-safi-03)

RFC uses space-separated names with abbreviations:
- "Interwork Segment Discovery route"
- "Direct Segment Discovery route"
- "Type 1 Session Transformed (ST) route"
- "Type 2 Session Transformed (ST) route"

## Current State

MUP route types in `src/exabgp/bgp/message/update/nlri/mup/`:

| Class | NAME (CamelCase) | RFC Name | Proposed IPv6 Name (kebab-case) |
|-------|------------------|----------|--------------------------------|
| InterworkSegmentDiscoveryRoute | `InterworkSegmentDiscoveryRoute` | Interwork Segment Discovery route | `interwork-segment-discovery-route` |
| DirectSegmentDiscoveryRoute | `DirectSegmentDiscoveryRoute` | Direct Segment Discovery route | `direct-segment-discovery-route` |
| Type1SessionTransformedRoute | `Type1SessionTransformedRoute` | Type 1 Session Transformed (ST) route | `type-1-st-route` |
| Type2SessionTransformedRoute | `Type2SessionTransformedRoute` | Type 2 Session Transformed (ST) route | `type-2-st-route` |

**Note:** For Type 1/2 ST routes, using `type-1-st-route` (with RFC abbreviation "ST") rather than `type-1-session-transformed-route` for brevity.

## Implementation Plan

### Step 1: Add RFC-aligned Names to MUP Classes

Add `NAME_V6` ClassVar to each MUP subclass (for documentation/clarity):

**isd.py:**
```python
NAME: ClassVar[str] = 'InterworkSegmentDiscoveryRoute'  # API v4
NAME_V6: ClassVar[str] = 'interwork-segment-discovery-route'  # API v6
```

**dsd.py:**
```python
NAME: ClassVar[str] = 'DirectSegmentDiscoveryRoute'  # API v4
NAME_V6: ClassVar[str] = 'direct-segment-discovery-route'  # API v6
```

**t1st.py:**
```python
NAME: ClassVar[str] = 'Type1SessionTransformedRoute'  # API v4
NAME_V6: ClassVar[str] = 'type-1-st-route'  # API v6 (RFC abbreviation "ST")
```

**t2st.py:**
```python
NAME: ClassVar[str] = 'Type2SessionTransformedRoute'  # API v4
NAME_V6: ClassVar[str] = 'type-2-st-route'  # API v6 (RFC abbreviation "ST")
```

### Step 2: Update `json()` to Use RFC-aligned Names

Change each MUP subclass's `json()` to use `NAME_V6`:

```python
def json(self, compact: bool | None = None) -> str:
    content = '"name": "{}", '.format(self.NAME_V6)  # API v6 format
    # ... rest of json generation ...
```

### Step 3: Add `v4_json()` for Backward Compatibility

Add `v4_json()` to each MUP subclass (copy of original `json()` with `NAME`):

```python
def v4_json(self, compact: bool = False) -> str:
    """API v4 backward compatible JSON with CamelCase names."""
    content = '"name": "{}", '.format(self.NAME)  # API v4 format
    # ... rest of json generation (same as json()) ...
```

**Alternative:** If json() bodies are identical except for name, use helper:

```python
def _json_content(self, name: str) -> str:
    content = f'"name": "{name}", '
    content += f'"arch": {self.ARCHTYPE}, '
    # ... rest ...
    return content

def json(self, compact: bool | None = None) -> str:
    return '{{ {} }}'.format(self._json_content(self.NAME_V6))

def v4_json(self, compact: bool = False) -> str:
    return '{{ {} }}'.format(self._json_content(self.NAME))
```

### Step 4: Update test_api_encode Decoder

Update `qa/bin/test_api_encode` `format_mup_announce()` to handle both name formats:

```python
# Map both CamelCase and kebab-case names to MUP type keywords
NAME_TO_TYPE = {
    # CamelCase (API v4 backward compat)
    "InterworkSegmentDiscoveryRoute": "mup-isd",
    "DirectSegmentDiscoveryRoute": "mup-dsd",
    "Type1SessionTransformedRoute": "mup-t1st",
    "Type2SessionTransformedRoute": "mup-t2st",
    # kebab-case (API v6 RFC-aligned)
    "interwork-segment-discovery-route": "mup-isd",
    "direct-segment-discovery-route": "mup-dsd",
    "type-1-st-route": "mup-t1st",
    "type-2-st-route": "mup-t2st",
}
```

### Step 5: Add Unit Tests

Add tests to verify:
1. `json()` returns RFC-aligned kebab-case names (API v6)
2. `v4_json()` returns CamelCase names (API v4)

### Step 6: Update CI Test Expected JSON

Update `qa/encoding/conf-srv6-mup.ci` JSON lines for MUP routes:
- Tests decode with default settings, which calls `json()` (API v6 format)
- Change expected `"name"` values to kebab-case

---

## Files to Modify

| File | Change |
|------|--------|
| `src/exabgp/bgp/message/update/nlri/mup/isd.py` | Add `NAME_V6`, update `json()`, add `v4_json()` |
| `src/exabgp/bgp/message/update/nlri/mup/dsd.py` | Add `NAME_V6`, update `json()`, add `v4_json()` |
| `src/exabgp/bgp/message/update/nlri/mup/t1st.py` | Add `NAME_V6`, update `json()`, add `v4_json()` |
| `src/exabgp/bgp/message/update/nlri/mup/t2st.py` | Add `NAME_V6`, update `json()`, add `v4_json()` |
| `qa/bin/test_api_encode` | Handle both name formats in decoder |
| `qa/encoding/conf-srv6-mup.ci` | Update JSON expected output for API v6 names |

---

## Testing

```bash
# Run full test suite
./qa/bin/test_everything

# Verify MUP round-trip still works
./qa/bin/test_api_encode --self-check -v qa/encoding/conf-srv6-mup.ci

# Test decode output format (default is API v6)
./sbin/exabgp decode "<mup_hex>"  # Should show kebab-case (API v6 default)

# Test API v4 output (via functional tests or manual testing)
env exabgp_api_version=4 ./sbin/exabgp ...  # Should show CamelCase
```

---

## Risks

1. **Context variable scope**: Must ensure context is properly set/reset
2. **Test CI file updates**: MUP test JSON expectations need updating
3. **Decoder compatibility**: `test_api_encode` must handle both formats

---

## Progress

- [ ] Add `NAME_V6` to `isd.py`, update `json()`, add `v4_json()`
- [ ] Add `NAME_V6` to `dsd.py`, update `json()`, add `v4_json()`
- [ ] Add `NAME_V6` to `t1st.py`, update `json()`, add `v4_json()`
- [ ] Add `NAME_V6` to `t2st.py`, update `json()`, add `v4_json()`
- [ ] Update `test_api_encode` decoder for both name formats
- [ ] Update CI test JSON expectations for API v6 names
- [ ] Run `./qa/bin/test_everything`
- [ ] Verify `json()` returns RFC-aligned names (API v6)
- [ ] Verify `v4_json()` returns CamelCase names (API v4)

---

## Documentation Note

**BACKWARD COMPATIBILITY POLICY:**

When modifying JSON output format for any NLRI type:
1. **API v4**: ALWAYS maintain existing format for backward compatibility
2. **API v6**: May introduce cleaner RFC-aligned formats
3. **Document both formats** in API documentation
4. **Update decoders** to accept both formats

This policy applies to MUP and should be considered for future NLRI types.
