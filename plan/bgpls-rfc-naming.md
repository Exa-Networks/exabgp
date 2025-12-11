# BGP-LS Class Naming Alignment with RFC/IANA

**Status:** 🔄 Active
**Created:** 2025-12-11

## Goal

Rename BGP-LS attribute classes to match IANA/RFC naming conventions.

## Reference

- IANA Registry: https://www.iana.org/assignments/bgp-ls-parameters
- RFC 7752: https://datatracker.ietf.org/doc/html/rfc7752
- RFC 9514: https://datatracker.ietf.org/doc/html/rfc9514

## Class Renames

| TLV | Old Name | New Name | Status |
|-----|----------|----------|--------|
| 1028/1029 | `LocalTeRid` | `LocalRouterId` | ✅ Done |
| 1030/1031 | `RemoteTeRid` | `RemoteRouterId` | ✅ Done |
| 1090 | `RsvpBw` | `MaxReservableBw` | ✅ Done |
| 1091 | `UnRsvpBw` | `UnreservedBw` | ✅ Done |
| 1099 | `SrAdjacency` | `AdjacencySid` | ✅ Done |
| 1100 | `SrAdjacencyLan` | `LanAdjacencySid` | ✅ Done |
| 1158 | `SrPrefix` | `PrefixSid` | ✅ Done |
| 1170 | `SrIgpPrefixAttr` | `PrefixAttributesFlags` | ✅ Done |
| 1171 | `SrSourceRouterID` | `SourceRouterId` | ✅ Done |

## Factory Method Renames

| Old Method | New Method |
|------------|------------|
| `make_localterid()` | `make_localrouterid()` |
| `make_remoteterid()` | `make_remoterouterid()` |
| `make_rsvpbw()` | `make_maxreservablebw()` |
| `make_unrsvpbw()` | `make_unreservedbw()` |
| `make_sradjacency()` | `make_adjacencysid()` |
| `make_sradjacencylan()` | `make_lanadjacencysid()` |

## JSON Key Changes

| Old Key | New Key |
|---------|---------|
| `local-te-router-ids` | `local-router-ids` |
| `remote-te-router-id` | `remote-router-id` |

## Files Modified

### Source Files (13)
- `src/exabgp/bgp/message/update/attribute/bgpls/__init__.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/link/__init__.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/node/__init__.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/prefix/__init__.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/node/lterid.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/link/rterid.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/link/rsvpbw.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/link/unrsvpbw.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/link/sradj.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/link/sradjlan.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/prefix/srprefix.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/prefix/srigpprefixattr.py`
- `src/exabgp/bgp/message/update/attribute/bgpls/prefix/srrid.py`

### Test Files (2)
- `tests/unit/test_bgpls.py`
- `tests/unit/test_bgpls_json_validation.py`

## Implementation Method

Used automated `sed` replacements:
```bash
# Example for one rename
find src tests -name "*.py" -exec sed -i '' \
  -e 's/LocalTeRid/LocalRouterId/g' \
  -e 's/local-te-router-ids/local-router-ids/g' \
  -e 's/make_localterid/make_localrouterid/g' \
  {} +
```

## Remaining Work

- [x] Update `__init__.py` documentation tables with new class names
- [x] Run full test suite (`./qa/bin/test_everything`)
- [ ] Rename source files to match class names
- [ ] Commit changes

## File Renames (Phase 2)

| Old File | New File | Class |
|----------|----------|-------|
| `node/lterid.py` | `node/localrouterid.py` | LocalRouterId |
| `link/rterid.py` | `link/remoterouterid.py` | RemoteRouterId |
| `link/rsvpbw.py` | `link/maxreservablebw.py` | MaxReservableBw |
| `link/unrsvpbw.py` | `link/unreservedbw.py` | UnreservedBw |
| `link/sradj.py` | `link/adjacencysid.py` | AdjacencySid |
| `link/sradjlan.py` | `link/lanadjacencysid.py` | LanAdjacencySid |
| `prefix/srprefix.py` | `prefix/prefixsid.py` | PrefixSid |
| `prefix/srigpprefixattr.py` | `prefix/prefixattributesflags.py` | PrefixAttributesFlags |
| `prefix/srrid.py` | `prefix/sourcerouterid.py` | SourceRouterId |

## Test Results

```
150 passed, 18 skipped in 0.46s
```

## Breaking Changes

This is a **breaking change** for any external code that:
1. Imports these classes directly by name
2. Uses the factory methods
3. Parses JSON output with the old keys (`local-te-router-ids`, `remote-te-router-id`)

No backward compatibility aliases are provided (intentional - to catch all usages).
