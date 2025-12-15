# Buffer Protocol Audit and Documentation

**Status:** ✅ Complete
**Created:** 2025-12-11
**Updated:** 2025-12-15

## Goal

1. Update `.claude/` documentation so Claude doesn't accidentally undo Buffer optimizations
2. Audit and restore Buffer type hints where `bytes` should be `Buffer`

## Background

PEP 688 (Python 3.12+) provides `collections.abc.Buffer` for zero-copy buffer protocol operations. ExaBGP has partial adoption:

- **Current state:** 129 `data: bytes` vs 94 `data: Buffer` occurrences
- **Coverage:** ~42% of data parameters use Buffer (improved from ~33%)
- **Problem:** Claude tends to write `bytes` because it's more familiar, undoing optimizations

Documentation exists at `.claude/exabgp/PEP688_BUFFER_PROTOCOL.md` but is NOT referenced in:
- `ESSENTIAL_PROTOCOLS.md` (read every session)
- `CODING_STANDARDS.md` (read every session)
- `CLAUDE.md` (project instructions)

---

## Part 1: Documentation Updates

### Files to Modify

| File | Change |
|------|--------|
| `.claude/CODING_STANDARDS.md` | Add Buffer protocol section |
| `.claude/ESSENTIAL_PROTOCOLS.md` | Add Buffer reminder in Coding Standards section |
| `CLAUDE.md` | Add Buffer to Key Requirements section |

### Proposed Addition to CODING_STANDARDS.md

Add after "BGP Method APIs" section:

```markdown
---

## Buffer Protocol (PEP 688) - Zero-Copy Optimization

**Rule:** Use `Buffer` not `bytes` for `unpack` method parameters.

✅ **CORRECT:**
```python
from exabgp.util.types import Buffer

@classmethod
def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
    # data can be bytes, memoryview, or any buffer - zero-copy slicing
    view = memoryview(data)
    ...
```

❌ **AVOID:**
```python
@classmethod
def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Attribute:
    # Forces callers to convert memoryview to bytes - copies data
    ...
```

**Why Buffer matters:**
- `memoryview` slicing is zero-copy (no memory allocation)
- `bytes` slicing creates new objects (memory allocation + copy)
- Network code processes many buffers - overhead adds up
- `struct.unpack()` accepts Buffer directly

**When to use `bytes` vs `Buffer`:**
| Use `bytes` when | Use `Buffer` when |
|------------------|-------------------|
| Storing long-term (dict key, cache) | Parsing wire data |
| Need immutability guarantee | Passing to struct.unpack |
| External API requires bytes | Creating memoryview slices |
| Hashing required | Intermediate processing |

**Import:** `from exabgp.util.types import Buffer`

**See:** `.claude/exabgp/PEP688_BUFFER_PROTOCOL.md` for full details
```

### Proposed Addition to ESSENTIAL_PROTOCOLS.md

Add to "Coding Standards" section (after Python 3.12+ syntax bullet):

```markdown
- Buffer protocol: Use `Buffer` not `bytes` for unpack parameters (see CODING_STANDARDS.md)
```

### Proposed Addition to CLAUDE.md

Add to "Key Requirements" section:

```markdown
**Buffer Protocol (Zero-Copy):**
- Use `from exabgp.util.types import Buffer` for unpack method parameters
- NEVER change `data: Buffer` back to `data: bytes` - this undoes optimization
- See `.claude/exabgp/PEP688_BUFFER_PROTOCOL.md`
```

---

## Part 2: Audit Results

### Files Already Using Buffer (42 files, 50 occurrences) ✅

These are correct - DO NOT CHANGE:

```
src/exabgp/protocol/ip/__init__.py (3)
src/exabgp/protocol/family.py (2)
src/exabgp/bgp/message/open/asn.py (1)
src/exabgp/bgp/message/open/__init__.py (1)
src/exabgp/bgp/message/notification.py (1)
src/exabgp/bgp/message/unknown.py (1)
src/exabgp/bgp/message/scheduling.py (3)
src/exabgp/bgp/message/refresh.py (1)
src/exabgp/bgp/message/message.py (1)
src/exabgp/bgp/message/operational.py (1)
src/exabgp/bgp/message/update/eor.py (1)
src/exabgp/bgp/message/open/capability/capabilities.py (1)
src/exabgp/bgp/message/update/collection.py (1)
src/exabgp/bgp/message/keepalive.py (1)
src/exabgp/bgp/message/open/routerid.py (1)
src/exabgp/bgp/message/update/attribute/atomicaggregate.py (1)
src/exabgp/bgp/message/update/attribute/originatorid.py (1)
src/exabgp/bgp/message/update/attribute/attribute.py (1)
src/exabgp/bgp/message/update/attribute/mpurnlri.py (1)
src/exabgp/bgp/message/update/attribute/localpref.py (1)
src/exabgp/bgp/message/update/attribute/collection.py (1)
src/exabgp/bgp/message/update/attribute/nexthop.py (1)
src/exabgp/bgp/message/update/attribute/aspath.py (2)
src/exabgp/bgp/message/update/__init__.py (1)
src/exabgp/bgp/message/update/attribute/med.py (1)
src/exabgp/bgp/message/update/attribute/generic.py (1)
src/exabgp/bgp/message/update/attribute/aigp.py (1)
src/exabgp/bgp/message/update/attribute/aggregator.py (2)
src/exabgp/bgp/message/update/attribute/mprnlri.py (1)
src/exabgp/bgp/message/update/attribute/pmsi.py (1)
src/exabgp/bgp/message/update/attribute/clusterlist.py (1)
src/exabgp/bgp/message/update/attribute/origin.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/communities.py (2)
src/exabgp/bgp/message/update/nlri/cidr.py (1)
src/exabgp/bgp/message/update/nlri/evpn/nlri.py (1)
src/exabgp/bgp/message/update/nlri/qualifier/mac.py (1)
src/exabgp/bgp/message/update/nlri/qualifier/rd.py (1)
src/exabgp/bgp/message/update/nlri/qualifier/labels.py (1)
src/exabgp/bgp/message/update/nlri/qualifier/esi.py (1)
src/exabgp/bgp/message/update/attribute/community/large/communities.py (1)
src/exabgp/bgp/message/update/attribute/community/initial/communities.py (1)
src/exabgp/bgp/message/update/nlri/qualifier/etag.py (1)
```

### Files Needing Migration (90 files total, 77 remaining)

Script audit found 90 files needing migration (more than original 82 estimate).
Additional files include: `notification.py`, `logger/format.py`, `connection.py`, etc.

#### Priority 1: Core Capabilities (13 files) ✅ DONE

Migrated 2025-12-15:
```
src/exabgp/bgp/message/open/capability/capability.py (3)
src/exabgp/bgp/message/open/capability/mp.py (1)
src/exabgp/bgp/message/open/capability/addpath.py (1)
src/exabgp/bgp/message/open/capability/graceful.py (1)
src/exabgp/bgp/message/open/capability/asn4.py (1)
src/exabgp/bgp/message/open/capability/refresh.py (2)
src/exabgp/bgp/message/open/capability/extended.py (1)
src/exabgp/bgp/message/open/capability/nexthop.py (1)
src/exabgp/bgp/message/open/capability/hostname.py (1)
src/exabgp/bgp/message/open/capability/software.py (1)
src/exabgp/bgp/message/open/capability/ms.py (1)
src/exabgp/bgp/message/open/capability/operational.py (1)
src/exabgp/bgp/message/open/capability/unknown.py (3)
```

#### Priority 2: Communities (12 files)
Frequently parsed attributes:

```
src/exabgp/bgp/message/update/attribute/community/initial/community.py (1)
src/exabgp/bgp/message/update/attribute/community/large/community.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/community.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/rt.py (3)
src/exabgp/bgp/message/update/attribute/community/extended/origin.py (3)
src/exabgp/bgp/message/update/attribute/community/extended/bandwidth.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/traffic.py (9)
src/exabgp/bgp/message/update/attribute/community/extended/encapsulation.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/l2info.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/mac_mobility.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/mup.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/chso.py (1)
src/exabgp/bgp/message/update/attribute/community/extended/flowspec_scope.py (1)
```

#### Priority 3: BGP-LS (35 files)
Large subsystem, consistent pattern:

```
src/exabgp/bgp/message/update/nlri/bgpls/node.py (1)
src/exabgp/bgp/message/update/nlri/bgpls/link.py (1)
src/exabgp/bgp/message/update/nlri/bgpls/prefixv4.py (1)
src/exabgp/bgp/message/update/nlri/bgpls/prefixv6.py (1)
src/exabgp/bgp/message/update/nlri/bgpls/srv6sid.py (1)
src/exabgp/bgp/message/update/nlri/bgpls/tlvs/*.py (9 files)
src/exabgp/bgp/message/update/attribute/bgpls/linkstate.py (5)
src/exabgp/bgp/message/update/attribute/bgpls/node/*.py (6 files)
src/exabgp/bgp/message/update/attribute/bgpls/link/*.py (16 files)
src/exabgp/bgp/message/update/attribute/bgpls/prefix/*.py (7 files)
```

#### Priority 4: SR/SRv6 (9 files)

```
src/exabgp/bgp/message/update/attribute/sr/prefixsid.py (2)
src/exabgp/bgp/message/update/attribute/sr/labelindex.py (1)
src/exabgp/bgp/message/update/attribute/sr/srgb.py (1)
src/exabgp/bgp/message/update/attribute/sr/srv6/generic.py (2)
src/exabgp/bgp/message/update/attribute/sr/srv6/sidinformation.py (1)
src/exabgp/bgp/message/update/attribute/sr/srv6/sidstructure.py (1)
src/exabgp/bgp/message/update/attribute/sr/srv6/l3service.py (1)
src/exabgp/bgp/message/update/attribute/sr/srv6/l2service.py (1)
```

#### Priority 5: MVPN/Other (2 files)

```
src/exabgp/bgp/message/update/nlri/mvpn/nlri.py (1)
src/exabgp/protocol/iso/__init__.py (1)
```

---

## Implementation Plan

### Phase 1: Documentation (Non-breaking) ✅

- [x] Update `.claude/CODING_STANDARDS.md` with Buffer section
- [x] Update `.claude/ESSENTIAL_PROTOCOLS.md` with Buffer reminder
- [x] Update `CLAUDE.md` with Buffer requirement
- [x] Update date stamps on all modified files

### Phase 2: Migration Script ✅

Created `scripts/migrate_bytes_to_buffer.py`:
- Lists files needing migration (`--list`)
- Dry run mode (`--dry-run`)
- Migrate by priority group (`--priority 1-5`)
- Migrate all at once (`--all`)
- Automatically adds Buffer import if missing
- Replaces `data: bytes` with `data: Buffer` in signatures

### Phase 3: Priority 1 Migration (Capabilities) ✅

- [x] Migrate 13 capability files (18 replacements)
- [x] Run `./qa/bin/test_everything` - All 15 tests pass
- [ ] Commit (pending user request)

### Phase 4: Priority 2 Migration (Communities) ✅

- [x] Migrate 13 community files (30 replacements)
- [x] Run `./qa/bin/test_everything` - All tests pass

### Phase 5: Priority 3 Migration (BGP-LS) ✅

- [x] Migrate 22 BGP-LS files (29 replacements)
- [x] Run `./qa/bin/test_everything` - All tests pass

### Phase 6: Priority 4-5 + Remaining Migration ✅

- [x] Migrate 8 SR/SRv6 files (10 replacements)
- [x] Migrate 2 other files (2 replacements)
- [x] Migrate 32 additional files not in priority groups (40 replacements)
- [x] Fix import placement bug in logger/format.py
- [x] Run `./qa/bin/test_everything` - All 15 tests pass

### Phase 7: Constructor and Storage Migration ✅

- [x] Update migration script to handle `packed: bytes` and `_packed: bytes`
- [x] Migrate 68 additional files (121 replacements)
- [x] Run `./qa/bin/test_everything` - All 15 tests pass

### All Migrations Complete ✅

**Totals:**
- 117 files modified
- 250 type replacements:
  - `data: bytes` → `data: Buffer` (129)
  - `packed: bytes` → `packed: Buffer` (121)
- 0 files remaining needing migration

---

## Testing Strategy

Each phase:
1. Run migration script on file subset
2. `uv run ruff format src && uv run ruff check src`
3. `uv run mypy src/exabgp/` (type check)
4. `./qa/bin/test_everything` (full test suite)

No functional changes expected - only type hint updates.

---

## Success Criteria

- [x] All `.claude/` documentation updated with Buffer guidance
- [x] 0 occurrences of `def unpack.*data: bytes` (verified via migration script)
- [x] All tests pass (15/15)
- [ ] Claude stops accidentally reverting Buffer to bytes (ongoing)

---

## Notes

**Why `exabgp.util.types.Buffer`?**

The project defines its own `Buffer` type for compatibility:

```python
# src/exabgp/util/types.py
if TYPE_CHECKING:
    Buffer = bytes | memoryview  # For type checkers that don't support PEP 688
else:
    from collections.abc import Buffer  # Runtime: actual PEP 688 type
```

This allows:
- Type checkers to understand the type even without PEP 688 support
- Runtime code to use the actual `collections.abc.Buffer` ABC

---

**Dependencies:** None
**Blocked by:** None
**Blocks:** None (optimization only)
