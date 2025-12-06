# Plan: Add NLRICollection and MPNLRICollection Wire Containers

## Goal

Add wire container classes for NLRI data following the established "packed-bytes-first" pattern:
- `NLRICollection`: Wire container for IPv4 announce/withdraw sections
- `MPNLRICollection`: Wire container for MP_REACH/MP_UNREACH attribute data

## Design Decisions

1. **Dual-mode support**: Both classes support wire-bytes input AND semantic NLRI list construction
2. **Factory methods**: Use existing `INET.from_cidr()` / `INET.make_route()` for explicit AFI/SAFI (no `__init__` changes)
3. **Update helpers**: Keep returning raw bytes only (`withdrawn_bytes`, `nlri_bytes`, etc.)
4. **MP pattern**: MPNLRICollection follows Update/UpdateCollection pattern (wire/semantic separation)

## Files to Create

### `src/exabgp/bgp/message/update/nlri/collection.py` (NEW)

```python
class NLRICollection:
    """Wire-format NLRI container for IPv4 announce/withdraw sections.

    Dual-mode:
    - Wire mode: __init__(packed, context, action) - stores bytes, lazy parsing
    - Semantic mode: make_collection(context, nlris) - stores NLRI list
    """
    _MODE_PACKED = 1
    _MODE_NLRIS = 2

    def __init__(self, packed: bytes, context: OpenContext, action: Action = Action.ANNOUNCE)

    @classmethod
    def make_collection(cls, context: OpenContext, nlris: list[NLRI], action: Action) -> NLRICollection

    @property
    def packed(self) -> bytes          # Raw NLRI bytes

    @property
    def nlris(self) -> list[NLRI]      # Lazy-parsed NLRI list

    def _parse_nlris(self) -> list[NLRI]  # Internal parsing


class MPNLRICollection:
    """Wire-format MP_REACH/MP_UNREACH NLRI container.

    Dual-mode:
    - Wire mode: __init__(packed, context, is_reach) - stores bytes, lazy parsing
    - Semantic mode: from_reach(mprnlri) / from_unreach(mpurnlri)
    """
    _MODE_PACKED = 1
    _MODE_SEMANTIC = 2

    def __init__(self, packed: bytes, context: OpenContext, is_reach: bool = True)

    @classmethod
    def from_reach(cls, mprnlri: MPRNLRI) -> MPNLRICollection

    @classmethod
    def from_unreach(cls, mpurnlri: MPURNLRI) -> MPNLRICollection

    @property
    def packed(self) -> bytes          # Raw MP attribute payload

    @property
    def nlris(self) -> list[NLRI]      # Lazy-parsed NLRI list

    @property
    def afi(self) -> AFI               # From MP attribute header

    @property
    def safi(self) -> SAFI             # From MP attribute header

    @property
    def nexthop(self) -> IP | None     # Only for MP_REACH
```

## Files to Modify

### `src/exabgp/bgp/message/update/nlri/__init__.py`

Add exports:
```python
from exabgp.bgp.message.update.nlri.collection import NLRICollection, MPNLRICollection
```

### `src/exabgp/bgp/message/update/__init__.py`

Add re-exports in `__all__`:
```python
from exabgp.bgp.message.update.nlri import NLRICollection, MPNLRICollection
```

## Files to Create (Tests)

### `tests/unit/bgp/message/update/nlri/test_collection.py` (NEW)

- `test_nlri_collection_from_bytes()` - Wire mode creation
- `test_nlri_collection_lazy_parsing()` - Parsing deferred until .nlris accessed
- `test_nlri_collection_make_collection()` - Semantic mode creation
- `test_nlri_collection_roundtrip()` - bytes -> parse -> pack -> bytes
- `test_mpnlri_collection_reach_from_bytes()` - MP_REACH wire mode
- `test_mpnlri_collection_unreach_from_bytes()` - MP_UNREACH wire mode
- `test_mpnlri_collection_from_semantic()` - from_reach/from_unreach factories
- `test_mpnlri_collection_afi_safi_extraction()` - AFI/SAFI from header

## Implementation Steps

1. Create `src/exabgp/bgp/message/update/nlri/collection.py` with NLRICollection
2. Add MPNLRICollection to same file
3. Update `nlri/__init__.py` exports
4. Update `update/__init__.py` exports
5. Create unit tests
6. Run `./qa/bin/test_everything`

## Key Dependencies

- `OpenContext` from `src/exabgp/bgp/message/open/capability/negotiated.py` - parsing context
- `NLRI.unpack_nlri()` from `src/exabgp/bgp/message/update/nlri/nlri.py` - NLRI factory
- `MPRNLRI` / `MPURNLRI` from `src/exabgp/bgp/message/update/attribute/` - MP parsing

## Notes

- No changes to NLRI base class `__init__` signature
- No changes to Update class (keeps returning raw bytes)
- MPRNLRI/MPURNLRI remain as-is (MPNLRICollection delegates to them for parsing)

## Progress

- [x] Step 1: Create NLRICollection class
- [x] Step 2: Create MPNLRICollection class
- [x] Step 3: Update nlri/__init__.py exports
- [x] Step 4: Update update/__init__.py exports
- [x] Step 5: Create unit tests (19 tests in tests/unit/test_collection.py)
- [x] Step 6: Run full test suite (11/11 passed)

## Implementation Summary (2025-12-06)

### Files Created
- `src/exabgp/bgp/message/update/nlri/collection.py` - NLRICollection and MPNLRICollection classes
- `tests/unit/test_collection.py` - 19 unit tests

### Files Modified
- `src/exabgp/bgp/message/update/nlri/__init__.py` - Added exports
- `src/exabgp/bgp/message/update/__init__.py` - Added re-exports

### Key Implementation Details
- Both classes follow packed-bytes-first pattern with dual-mode support
- NLRICollection: wire mode via `__init__(packed, context, action)`, semantic mode via `make_collection()`
- MPNLRICollection: wire mode via `__init__(packed, context, is_reach)`, semantic mode via `from_reach()`/`from_unreach()`
- Lazy parsing: NLRIs are only parsed when `.nlris` property is accessed
- Roundtrip tested: wire -> parse -> pack -> wire produces identical bytes
