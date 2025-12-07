# Plan: Convert NLRI Classes to Packed-Bytes-First Pattern

**Status:** 🔄 Ready to start
**Priority:** 🟡 Medium
**Command:** `/convert-nlri <nlri-name>`
**Reference:** `.claude/exabgp/PACKED_BYTES_FIRST_PATTERN.md`
**Prerequisite:** `plan/nlri-immutability-refactoring.md` (Phase 5 complete for VPLS)

---

## Overview

Convert all NLRI classes to the packed-bytes-first pattern to:
- Reduce memory allocation (store wire bytes directly)
- Enable lazy unpacking (parse fields only when accessed)
- Support zero-copy routing (return stored bytes without re-packing)

## Key Principles

1. **`_packed` is ALWAYS required** - no `None`, no conditionals in properties
2. **Two entry points only:**
   - `unpack_nlri()` - from existing wire Buffer (don't modify, just store)
   - `make_xxx()` - build new packed bytes from components
3. **`@property` for all fields** - simple return, no conditionals
4. **No `make_empty()`** - breaks immutability

## Prerequisite: NLRI Immutability Refactoring

**See:** `plan/nlri-immutability-refactoring.md`

Configuration parser refactoring status:
- Phase 1: ✅ COMPLETE - Add factory methods to NLRI classes
- Phase 2: ✅ COMPLETE - RouteBuilderValidator deferred construction
- Phase 3: ✅ COMPLETE - Static route deferred construction
- Phase 4: ✅ COMPLETE - TypeSelectorValidator deferred construction
- Phase 5: ✅ COMPLETE for VPLS - Remove mutation support

**VPLS is fully immutable and can be used as reference implementation.**

---

## Conversion Status

### Core NLRI Classes

| Class | File | Has Tests | Converted | Notes |
|-------|------|-----------|-----------|-------|
| VPLS | `nlri/vpls.py` | ✅ | ✅ | Reference implementation |
| RTC | `nlri/rtc.py` | ✅ | ❌ | Partial - rt needs negotiated |
| Flow | `nlri/flow.py` | ❌ | ❌ | Builder pattern - not applicable |
| INET | `nlri/inet.py` | ❌ | ❌ | Base for Label/IPVPN |
| Label | `nlri/label.py` | ❌ | ❌ | Extends INET |
| IPVPN | `nlri/ipvpn.py` | ❌ | ❌ | Extends Label |

### EVPN Classes

| Class | File | Has Tests | Converted | Notes |
|-------|------|-----------|-----------|-------|
| EVPN (base) | `evpn/nlri.py` | ❌ | ❌ | Base class |
| GenericEVPN | `evpn/nlri.py` | ❌ | ❌ | Fallback handler |
| MAC | `evpn/mac.py` | ❌ | ❌ | Type 2 |
| EthernetAD | `evpn/ethernetad.py` | ❌ | ❌ | Type 1 |
| Multicast | `evpn/multicast.py` | ❌ | ❌ | Type 3 |
| EthernetSegment | `evpn/segment.py` | ❌ | ❌ | Type 4 |
| Prefix | `evpn/prefix.py` | ❌ | ❌ | Type 5 |

### MVPN Classes

| Class | File | Has Tests | Converted | Notes |
|-------|------|-----------|-----------|-------|
| MVPN (base) | `mvpn/nlri.py` | ❌ | ❌ | Base class |
| GenericMVPN | `mvpn/nlri.py` | ❌ | ❌ | Fallback handler |
| SourceAD | `mvpn/sourcead.py` | ❌ | ❌ | Type 1 |
| SharedJoin | `mvpn/sharedjoin.py` | ❌ | ❌ | Type 6 |
| SourceJoin | `mvpn/sourcejoin.py` | ❌ | ❌ | Type 7 |

### MUP Classes

| Class | File | Has Tests | Converted | Notes |
|-------|------|-----------|-----------|-------|
| MUP (base) | `mup/nlri.py` | ❌ | ❌ | Base class |
| GenericMUP | `mup/nlri.py` | ❌ | ❌ | Fallback handler |
| InterworkSegmentDiscoveryRoute | `mup/isd.py` | ❌ | ❌ | ISD |
| DirectSegmentDiscoveryRoute | `mup/dsd.py` | ❌ | ❌ | DSD |
| Type1SessionTransformedRoute | `mup/t1st.py` | ❌ | ❌ | T1ST |
| Type2SessionTransformedRoute | `mup/t2st.py` | ❌ | ❌ | T2ST |

### BGP-LS Classes

| Class | File | Has Tests | Converted | Notes |
|-------|------|-----------|-----------|-------|
| BGPLS (base) | `bgpls/nlri.py` | ❌ | ❌ | Base class |
| GenericBGPLS | `bgpls/nlri.py` | ❌ | ❌ | Fallback handler |
| NODE | `bgpls/node.py` | ❌ | ❌ | Node descriptor |
| LINK | `bgpls/link.py` | ❌ | ❌ | Link descriptor |
| PREFIXv4 | `bgpls/prefixv4.py` | ❌ | ❌ | IPv4 prefix |
| PREFIXv6 | `bgpls/prefixv6.py` | ❌ | ❌ | IPv6 prefix |
| SRv6SID | `bgpls/srv6sid.py` | ❌ | ❌ | SRv6 SID |

---

## Conversion Order (Recommended)

1. **Simple fixed-length first:**
   - RTC (already partial)
   - MVPN types (fixed format)
   - MUP types

2. **EVPN types:**
   - Variable length but well-defined structure

3. **BGP-LS types:**
   - Complex TLV structure

4. **Skip or document as not applicable:**
   - Flow (builder pattern with rules)
   - INET/Label/IPVPN (inheritance hierarchy - needs careful analysis)

---

## How to Convert

Use the slash command:
```
/convert-nlri <nlri-name>
```

Examples:
- `/convert-nlri rtc`
- `/convert-nlri evpn/mac`
- `/convert-nlri mvpn/sourcead`
- `/convert-nlri mup/isd`

The command will:
1. Read and analyze the NLRI structure
2. Check for / create unit tests
3. Convert to packed-bytes-first pattern
4. Run tests to verify

---

## Progress Log

### 2025-12-07
- Created conversion plan
- Created `/convert-nlri` slash command
- VPLS already converted (reference implementation)

### 2025-12-07 - Phase 5 Verified
- Verified Phase 4 of prerequisite plan (TypeSelectorValidator)
- Completed Phase 5: VPLS immutability
  - Updated announce/path.py, label.py, vpn.py to use Settings mode
  - Removed deprecated make_empty() and assign() from VPLS
  - Removed builder mode slots and simplified properties
  - All 11 tests pass
- VPLS is now fully immutable and ready as reference implementation

---

**Updated:** 2025-12-07
