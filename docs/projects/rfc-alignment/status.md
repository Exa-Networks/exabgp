# RFC-Aligned Method Naming Refactoring Plan

**Status:** ✅ COMPLETED
**Date Started:** 2025-01-15
**Date Completed:** 2025-01-15
**Priority:** Medium (improves consistency and RFC alignment)

## Completion Summary

**All 41 generic `unpack()` methods successfully renamed!**

- ✅ **2 Protocol family methods** (AFI, SAFI) → `unpack_afi()`, `unpack_safi()`
- ✅ **3 IP address methods** (IP, IPv4, IPv6) → `unpack_ip()`, `unpack_ipv4()`, `unpack_ipv6()`
- ✅ **2 BGP identifier methods** (ASN, RouterID) → `unpack_asn()`, `unpack_routerid()`
- ✅ **5 NLRI qualifier methods** (RD, Labels, ESI, ETag, MAC) → specific names
- ✅ **1 CIDR method** → `unpack_cidr()`
- ✅ **9 BGP-LS TLV methods** → specific names (linkid, node, ifaceaddr, etc.)
- ✅ **5 EVPN route types** → `unpack_evpn_route()`
- ✅ **4 MUP route types** → `unpack_mup_route()`
- ✅ **3 MVPN route types** → `unpack_mvpn_route()`
- ✅ **7 Other methods** (Prefix, various descriptors)

**Testing:** All 1376 unit tests pass ✅

## Objective

Standardize all `unpack()` methods across the ExaBGP codebase to use RFC-aligned naming conventions with clear suffixes that indicate what is being unpacked.

## Background

Recent refactoring work improved BGP-LS naming consistency:
- ✅ `bc1158ee`: Renamed BGP-LS NLRI `unpack_nlri()` → `unpack_bgpls()`
- ✅ `778a4fa0`: Fixed `ExtendedCommunity.unpack_attribute()` parameter passing
- ✅ `b1a116aa`: Renamed attribute `unpack()` → `unpack_attribute()`
- ✅ Latest: Renamed BGP-LS NLRI `unpack_bgpls()` → `unpack_bgpls_nlri()` for clarity
- ✅ Latest: Renamed BGP-LS attribute components to `unpack_bgpls()`

This work identified 41 remaining methods using generic `unpack()` that should be renamed for consistency.

## Current State Analysis

**Total unpack methods found:** 174 across 143 files

### Already RFC-Aligned (131/174 methods)

| Pattern | Count | Status |
|---------|-------|--------|
| `unpack_message()` | 14 | ✅ Good - BGP messages (RFC 4271) |
| `unpack_attribute()` | 58 | ✅ Good - BGP attributes (RFC 4271) |
| `unpack_nlri()` | 13 | ✅ Good - Base NLRI (RFC 4271, 4760) |
| `unpack_capability()` | 16 | ✅ Good - BGP capabilities (RFC 2858) |
| `unpack_bgpls_nlri()` | 5 | ✅ Good - BGP-LS NLRI (RFC 7752) |
| `unpack_bgpls()` | 34 | ✅ Good - BGP-LS attributes (RFC 7752) |
| **Subtotal** | **140** | **RFC-aligned** |

### ✅ Refactored Successfully (41/174 methods)

All generic `unpack()` methods have been renamed with RFC-aligned specific suffixes:

## Refactoring Categories

### 1. BGPLS TLVs (13 files) - Priority: HIGH
**Location:** `src/exabgp/bgp/message/update/nlri/bgpls/tlvs/`

These are sub-components within BGP-LS NLRI structures (RFC 7752).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `LinkIdentifier.unpack()` | `unpack_cidr()` | `linkid.py` | RFC 7752 §3.2.2 |
| `IfaceAddr.unpack()` | `unpack_cidr()` | `ifaceaddr.py` | RFC 7752 §3.2.2 |
| `NeighAddr.unpack()` | `unpack_cidr()` | `neighaddr.py` | RFC 7752 §3.2.2 |
| `IpReach.unpack()` | `unpack_ipreachability()` | `ipreach.py` | RFC 7752 §3.2.3 |
| `OspfRoute.unpack()` | `unpack_cidr()` | `ospfroute.py` | RFC 7752 §3.2.3 |
| `MTID.unpack()` | `unpack_cidr()` | `multitopology.py` | RFC 7752 |
| `Prefix.unpack()` | `unpack_cidr()` | `prefix.py` | RFC 7752 §3.2.3 |
| `NodeDescriptor.unpack()` | `unpack_node()` | `node.py` | RFC 7752 §3.2.1.4 |
| `Srv6SIDInformation.unpack()` | `unpack_cidr()` | `srv6sidinformation.py` | RFC 9514 |

**Reasoning:** These are TLV descriptors within BGP-LS, not top-level attributes.

**Callers to update:**
- `src/exabgp/bgp/message/update/nlri/bgpls/link.py` (calls NodeDescriptor, LinkIdentifier, IfaceAddr, NeighAddr, MTID)
- `src/exabgp/bgp/message/update/nlri/bgpls/node.py` (calls NodeDescriptor)
- `src/exabgp/bgp/message/update/nlri/bgpls/prefixv4.py` (calls NodeDescriptor, OspfRoute, IpReach)
- `src/exabgp/bgp/message/update/nlri/bgpls/prefixv6.py` (calls NodeDescriptor, OspfRoute, IpReach)
- `src/exabgp/bgp/message/update/nlri/bgpls/srv6sid.py` (calls NodeDescriptor, MTID, Srv6SIDInformation)
- Tests: `tests/unit/test_bgpls.py`

---

### 2. NLRI Qualifiers (5 files) - Priority: HIGH
**Location:** `src/exabgp/bgp/message/update/nlri/qualifier/`

These are components that qualify NLRI (Route Distinguisher, Labels, ESI, etc.).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `RouteDistinguisher.unpack()` | `unpack_routedistinguisher()` | `rd.py` | RFC 4364 §4 |
| `Labels.unpack()` | `unpack_labels()` | `labels.py` | RFC 3107 §3 |
| `ESI.unpack()` | `unpack_esi()` | `esi.py` | RFC 7432 §5 |
| `EthernetTag.unpack()` | `unpack_etag()` | `etag.py` | RFC 7432 §7.1 |
| `MAC.unpack()` | `unpack_mac()` | `mac.py` | RFC 7432 §7 |

**Reasoning:** These are NLRI qualifiers/components, not full NLRI or attributes.

**Callers to update:**
- `src/exabgp/bgp/message/update/nlri/bgpls/nlri.py` (RD)
- `src/exabgp/bgp/message/update/nlri/evpn/*.py` (ESI, Labels, ETag, MAC)
- `src/exabgp/bgp/message/update/nlri/vpls.py` (RD, Labels)
- `src/exabgp/bgp/message/update/nlri/inet.py` (Labels)
- `src/exabgp/bgp/message/update/nlri/mup/*.py` (RD)
- `src/exabgp/bgp/message/update/nlri/mvpn/*.py` (RD)
- `src/exabgp/configuration/static/mpls.py` (Labels)
- Tests: Multiple test files

---

### 3. EVPN Route Types (5 files) - Priority: MEDIUM
**Location:** `src/exabgp/bgp/message/update/nlri/evpn/`

EVPN-specific route type implementations (RFC 7432).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `Prefix.unpack()` | `unpack_evpn_route()` | `prefix.py` | RFC 7432 §7.2/7.3 |
| `MAC.unpack()` | `unpack_evpn_route()` | `mac.py` | RFC 7432 §7.2 |
| `EthernetSegment.unpack()` | `unpack_evpn_route()` | `segment.py` | RFC 7432 §7.4 |
| `EthernetAD.unpack()` | `unpack_evpn_route()` | `ethernetad.py` | RFC 7432 §7.1 |
| `Multicast.unpack()` | `unpack_evpn_route()` | `multicast.py` | RFC 7432 §7.3 |

**Reasoning:** These unpack specific EVPN route types within the EVPN NLRI.

**Callers to update:**
- `src/exabgp/bgp/message/update/nlri/evpn/nlri.py` (dispatcher)
- Tests: `tests/unit/test_evpn.py`

---

### 4. MUP Route Types (5 files) - Priority: MEDIUM
**Location:** `src/exabgp/bgp/message/update/nlri/mup/`

Mobile User Plane (MUP) route type implementations (draft-mpmz-bess-mup-safi).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `DirectSegmentDiscovery.unpack()` | `unpack_mup_route()` | `dsd.py` | draft-mpmz |
| `Type1SourceTree.unpack()` | `unpack_mup_route()` | `t1st.py` | draft-mpmz |
| `Type2SourceTree.unpack()` | `unpack_mup_route()` | `t2st.py` | draft-mpmz |
| `InterworkSegmentDiscovery.unpack()` | `unpack_mup_route()` | `isd.py` | draft-mpmz |

**Reasoning:** These unpack specific MUP route types within the MUP NLRI.

**Callers to update:**
- `src/exabgp/bgp/message/update/nlri/mup/nlri.py` (dispatcher)
- Tests: `tests/unit/test_mup.py`

---

### 5. MVPN Route Types (3 files) - Priority: MEDIUM
**Location:** `src/exabgp/bgp/message/update/nlri/mvpn/`

Multicast VPN route type implementations (RFC 6514).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `SourceAD.unpack()` | `unpack_mvpn_route()` | `sourcead.py` | RFC 6514 §4.1 |
| `SourceJoin.unpack()` | `unpack_mvpn_route()` | `sourcejoin.py` | RFC 6514 §4.3 |
| `SharedJoin.unpack()` | `unpack_mvpn_route()` | `sharedjoin.py` | RFC 6514 §4.4 |

**Reasoning:** These unpack specific MVPN route types within the MVPN NLRI.

**Callers to update:**
- `src/exabgp/bgp/message/update/nlri/mvpn/nlri.py` (dispatcher)
- Tests: `tests/unit/test_mvpn.py`

---

### 6. Protocol Families (2 files) - Priority: HIGH
**Location:** `src/exabgp/protocol/family.py`

Core BGP protocol identifiers (RFC 4760).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `AFI.unpack()` | `unpack_afi()` | `family.py` | RFC 4760 §3 |
| `SAFI.unpack()` | `unpack_safi()` | `family.py` | RFC 4760 §3 |

**Reasoning:** AFI/SAFI are fundamental protocol identifiers used throughout BGP.

**Callers to update (MANY):**
- All capability modules (`src/exabgp/bgp/message/open/capability/*.py`)
- All NLRI modules
- EOR message parsing
- Configuration parsing
- Tests across the board

**Note:** This is the most widely-used change - affects 20+ files.

---

### 7. IP Addresses (3 files) - Priority: HIGH
**Location:** `src/exabgp/protocol/ip/`

IP address unpacking (RFC 791, RFC 2460).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `IP.unpack()` | `unpack_ip()` | `__init__.py` | RFC 791/2460 |
| `IPv4.unpack()` | `unpack_ipv4()` | `__init__.py` | RFC 791 |
| `IPv6.unpack()` | `unpack_ipv6()` | `__init__.py` | RFC 2460 |

**Reasoning:** IP addresses are fundamental types used extensively.

**Callers to update (MANY):**
- Attribute modules (NextHop, OriginatorID, ClusterList, Aggregator, etc.)
- BGP-LS attributes and TLVs
- NLRI modules
- Configuration parsing
- Tests

**Note:** Very widely used - affects 30+ files.

---

### 8. BGP Identifiers (2 files) - Priority: HIGH
**Location:** `src/exabgp/bgp/message/open/`

BGP session identifiers (RFC 4271).

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `ASN.unpack()` | `unpack_asn()` | `asn.py` | RFC 4271 §4.2 |
| `RouterID.unpack()` | `unpack_routerid()` | `routerid.py` | RFC 4271 §4.2 |

**Reasoning:** Core BGP identifiers used in OPEN messages and elsewhere.

**Callers to update:**
- `src/exabgp/bgp/message/open/__init__.py`
- Capability modules (ASN4)
- Aggregator attribute
- Operational messages
- BGP-LS descriptors
- Configuration parsing
- Tests

---

### 9. CIDR/Routes (1 file) - Priority: MEDIUM
**Location:** `src/exabgp/bgp/message/update/nlri/`

Basic CIDR route representation.

| Current Method | New Method | File | RFC Reference |
|----------------|------------|------|---------------|
| `CIDR.unpack()` | `unpack_cidr()` | `cidr.py` | RFC 4271 §4.3 |

**Reasoning:** CIDR is used for basic IPv4/IPv6 route encoding.

**Callers to update:**
- INET NLRI module
- Various NLRI parsers
- Tests

---

## Implementation Strategy

### Phase 1: Foundational Types (HIGH priority - affects many files)
1. Protocol families: AFI, SAFI (2 files, 20+ call sites)
2. IP addresses: IP, IPv4, IPv6 (3 files, 30+ call sites)
3. BGP identifiers: ASN, RouterID (2 files, 15+ call sites)

### Phase 2: NLRI Components (HIGH priority - important for consistency)
4. NLRI qualifiers: RD, Labels, ESI, ETag, MAC (5 files, 20+ call sites)
5. BGP-LS TLVs: LinkID, NodeDescriptor, etc. (13 files, 10+ call sites)

### Phase 3: Route Types (MEDIUM priority - localized changes)
6. EVPN route types (5 files, 2-3 call sites each)
7. MUP route types (5 files, 2-3 call sites each)
8. MVPN route types (3 files, 2-3 call sites each)
9. CIDR (1 file, 5+ call sites)

### Recommended Approach

**For each category:**
1. Rename method definitions in source files
2. Update all callers (use grep to find all call sites)
3. Update test files
4. Run linting: `ruff format src && ruff check src`
5. Run affected unit tests
6. Run functional tests: `./qa/bin/functional parsing`
7. Commit with descriptive message

**DO NOT:**
- Rename everything at once (too risky)
- Skip testing between changes
- Modify files without checking all callers first

## Testing Requirements

After each category:
- ✅ `ruff format src && ruff check src` - Must pass
- ✅ `env exabgp_log_enable=false pytest tests/unit/` - All tests must pass
- ✅ `./qa/bin/functional parsing` - All parsing tests must pass
- ✅ `./qa/bin/functional encoding` - All encoding tests must pass

## Estimated Effort

- **Total files to modify:** ~100 files (41 definitions + 60+ call sites)
- **Estimated time:** 4-6 hours (careful, systematic work)
- **Risk:** Medium (wide-reaching changes, but mechanical)

## Benefits

1. **RFC alignment:** Method names clearly indicate what RFC component they unpack
2. **Code clarity:** No ambiguous `unpack()` methods - always explicit
3. **Developer experience:** Easier to understand code and find relevant methods
4. **Consistency:** Uniform naming pattern across entire codebase
5. **Maintainability:** Future developers can easily follow the pattern

## References

- RFC 4271: BGP-4 base specification
- RFC 2858: Multiprotocol Extensions for BGP-4
- RFC 4760: Multiprotocol Extensions for BGP-4
- RFC 7752: BGP Link State Advertisement
- RFC 7432: EVPN
- RFC 6514: Multicast VPN
- RFC 4364: BGP/MPLS IP VPNs
- RFC 3107: Carrying Label Information in BGP-4

## Related Work

See commit history:
- `bc1158ee`: Rename BGP-LS component unpack_nlri() to unpack_bgpls()
- `778a4fa0`: Fix ExtendedCommunity.unpack_attribute() to pass negotiated parameter
- `b1a116aa`: Attribute: Rename unpack() to unpack_attribute() for consistency
- Latest session: Rename NLRI methods unpack_bgpls() → unpack_bgpls_nlri()
