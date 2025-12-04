# Packed-Bytes-First Pattern: Progress Tracker

## Legend

- ✅ Done - Converted and tested
- 🔄 Partial - Started but incomplete
- ⏳ Pending - Not started
- ⊘ N/A - Excluded (intentional design)

---

## Wave 1: Simple Attributes ✅ COMPLETE

| File | Class | Status | Factory Method |
|------|-------|--------|----------------|
| `attribute/origin.py` | Origin | ✅ | `make_origin(int)` |
| `attribute/med.py` | MED | ✅ | `make_med(int)` |
| `attribute/localpref.py` | LocalPreference | ✅ | `make_localpref(int)` |
| `attribute/atomicaggregate.py` | AtomicAggregate | ✅ | `make_atomic_aggregate()` |

---

## Wave 2: Complex Attributes ✅ COMPLETE

| File | Class | Status | Factory Method |
|------|-------|--------|----------------|
| `attribute/aspath.py` | ASPath | ✅ | `make_aspath(...)` |
| `attribute/aspath.py` | AS4Path | ✅ | (inherits) |
| `attribute/nexthop.py` | NextHop | ✅ | `make_nexthop(...)` |
| `attribute/nexthop.py` | NextHopSelf | ⊘ N/A | Special proxy - intentional |
| `attribute/aggregator.py` | Aggregator | ✅ | `make_aggregator(...)` |
| `attribute/aggregator.py` | Aggregator4 | ✅ | (inherits) |
| `attribute/clusterlist.py` | ClusterList | ✅ | `make_clusterlist(...)` |
| `attribute/originatorid.py` | OriginatorId | ✅ | `make_originatorid(...)` |
| `attribute/generic.py` | GenericAttribute | ✅ | `make_generic(...)` |
| `attribute/aigp.py` | AIGP | ✅ | `make_aigp(...)` |
| `attribute/pmsi.py` | PMSI | ✅ | `make_pmsi(...)` |

---

## Wave 3: Community Attributes ✅ COMPLETE

### Initial Communities

| File | Class | Status |
|------|-------|--------|
| `community/initial/community.py` | Community | ✅ |
| `community/initial/communities.py` | Communities | ✅ |

### Large Communities

| File | Class | Status |
|------|-------|--------|
| `community/large/community.py` | LargeCommunity | ✅ |
| `community/large/communities.py` | LargeCommunities | ✅ |

### Extended Communities

| File | Class | Status |
|------|-------|--------|
| `community/extended/community.py` | ExtendedCommunity | ✅ |
| `community/extended/communities.py` | ExtendedCommunities | ✅ |
| `community/extended/rt.py` | RouteTarget* (3 variants) | ✅ |
| `community/extended/origin.py` | OriginExtCommunity | ✅ |
| `community/extended/traffic.py` | TrafficCommunity | ✅ |
| `community/extended/bandwidth.py` | Bandwidth | ✅ |
| `community/extended/encapsulation.py` | Encapsulation | ✅ |
| `community/extended/flowspec_scope.py` | FlowSpecScope | ✅ |
| `community/extended/l2info.py` | L2Info | ✅ |
| `community/extended/mac_mobility.py` | MacMobility | ✅ |
| `community/extended/mup.py` | MUPExtCommunity | ✅ |
| `community/extended/chso.py` | CHSO | ✅ |

---

## Wave 4: MP Attributes + BGP-LS + SR ✅ COMPLETE

### MP Attributes

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/mprnlri.py` | MPRNLRI | ✅ | Hybrid pattern - see below |
| `attribute/mpurnlri.py` | MPURNLRI | ✅ | Hybrid pattern - see below |

#### MPRNLRI/MPURNLRI Design Decision (2025-12-04)

**Problem:** These are container attributes holding multiple NLRIs. The standard packed-bytes-first
pattern (`__init__(packed: bytes)`) doesn't naturally fit because:

1. Wire format is computed dynamically (groups NLRIs by nexthop for MPRNLRI)
2. May yield MULTIPLE wire attributes when NLRIs exceed size limits
3. Packing requires `negotiated` context (for addpath, nexthop encoding)

**Decision:** Hybrid pattern with two modes - unpacked path stores wire bytes + context,
semantic path stores NLRI list. NLRIs are parsed lazily on access.

**Implemented pattern:**
```python
class MPRNLRI(Attribute, Family):
    _MODE_PACKED = 1  # Created from wire bytes (unpack path)
    _MODE_NLRIS = 2   # Created from NLRI list (semantic path)

    def __init__(self, packed: bytes, context: NLRIParseContext) -> None:
        self._packed = packed
        self._context = context
        self._mode = self._MODE_PACKED
        self._nlris_cache: list[NLRI] | None = None

    @classmethod
    def make_mprnlri(cls, afi: AFI, safi: SAFI, nlris: list[NLRI]) -> 'MPRNLRI':
        # Creates instance in semantic mode with NLRIs stored directly
        instance = cls(header, dummy_context)
        instance._mode = cls._MODE_NLRIS
        instance._nlris_cache = nlris
        return instance

    @property
    def nlris(self) -> list[NLRI]:
        # Returns cached NLRIs or parses from _packed lazily
        if self._nlris_cache is not None:
            return self._nlris_cache
        self._nlris_cache = self._parse_nlris()
        return self._nlris_cache
```

**OpenContext:** Class with caching (in `negotiated.py`) containing:
- `afi: AFI` - Address Family Identifier
- `safi: SAFI` - Subsequent Address Family Identifier
- `addpath: bool` - AddPath enabled for this AFI/SAFI
- `asn4: bool` - 4-byte ASN mode
- `msg_size: int` - Max UPDATE size (4096 standard, 65535 extended)

Uses `__slots__` and class-level `_cache` dict. Factory method `make_open_context()` returns
cached instances for identical parameter combinations.

**Negotiated.nlri_context(afi, safi):** Method to build cached `OpenContext` from negotiated state.

**Key changes:**
1. `__init__(packed, context)` - stores wire bytes for unpack path
2. `make_mprnlri(context, nlris)` - factory takes `OpenContext` instead of AFI/SAFI
3. `nlris` property - lazy parsing with caching
4. `packed_attributes()` generator - unchanged, yields multiple bytes as needed
5. Call sites use `negotiated.nlri_context(afi, safi)` to get context

**Tests:** All 9 test suites pass (2689 unit, 74 encoding, 18 decoding)

### SR Attributes

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/sr/prefixsid.py` | PrefixSid | ✅ | Already correct |
| `attribute/sr/labelindex.py` | SrLabelIndex | ✅ | `make_labelindex(int)` |
| `attribute/sr/srgb.py` | SrGb | ✅ | `make_srgb(list[tuple])` |

### SRv6 Attributes

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/sr/srv6/generic.py` | GenericSrv6ServiceSubTlv | ✅ | `__init__(packed, code)` |
| `attribute/sr/srv6/generic.py` | GenericSrv6ServiceDataSubSubTlv | ✅ | `__init__(packed, code)` |
| `attribute/sr/srv6/l2service.py` | Srv6L2Service | ⊘ N/A | Container pattern (like PrefixSid) |
| `attribute/sr/srv6/l3service.py` | Srv6L3Service | ⊘ N/A | Container pattern (like PrefixSid) |
| `attribute/sr/srv6/sidinformation.py` | Srv6SidInformation | ⊘ N/A | Container pattern (like PrefixSid) |
| `attribute/sr/srv6/sidstructure.py` | Srv6SidStructure | ✅ | `make_sid_structure(...)` |

### BGP-LS Base Classes ✅ COMPLETE

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/bgpls/linkstate.py` | LinkState | ✅ | Container - takes `list[BaseLS]` |
| `attribute/bgpls/linkstate.py` | BaseLS | ✅ | `__init__(packed: bytes)` |
| `attribute/bgpls/linkstate.py` | FlagLS | ✅ | `flags` property unpacks from `_packed` |
| `attribute/bgpls/linkstate.py` | GenericLSID | ✅ | `__init__(packed: bytes)` |

### BGP-LS Link Attributes ✅ COMPLETE

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/bgpls/link/admingroup.py` | AdminGroup | ✅ | `make_admingroup(int)` |
| `attribute/bgpls/link/igpmetric.py` | IgpMetric | ✅ | (variable length, use `unpack_bgpls`) |
| `attribute/bgpls/link/linkname.py` | LinkName | ✅ | `make_linkname(str)` |
| `attribute/bgpls/link/maxbw.py` | MaxBw | ✅ | `make_maxbw(float)` |
| `attribute/bgpls/link/mplsmask.py` | MplsMask | ✅ | (FlagLS, use `unpack_bgpls`) |
| `attribute/bgpls/link/opaque.py` | LinkOpaque | ✅ | (raw bytes) |
| `attribute/bgpls/link/protection.py` | LinkProtectionType | ✅ | (FlagLS, use `unpack_bgpls`) |
| `attribute/bgpls/link/rsvpbw.py` | RsvpBw | ✅ | `make_rsvpbw(float)` |
| `attribute/bgpls/link/rterid.py` | RemoteTeRid | ✅ | `make_remoteterid(str)` |
| `attribute/bgpls/link/sradj.py` | SrAdjacency | ✅ | Properties unpack from `_packed` |
| `attribute/bgpls/link/sradjlan.py` | SrAdjacencyLan | ✅ | Properties unpack from `_packed` |
| `attribute/bgpls/link/srlg.py` | Srlg | ✅ | `make_srlg(list[int])` |
| `attribute/bgpls/link/srv6capabilities.py` | Srv6Capabilities | ✅ | `make_srv6_capabilities(flags)` |
| `attribute/bgpls/link/srv6endpointbehavior.py` | Srv6EndpointBehavior | ✅ | `make_srv6_endpoint_behavior(...)` |
| `attribute/bgpls/link/srv6endx.py` | Srv6EndX | ✅ | (complex, stores parsed content) |
| `attribute/bgpls/link/srv6lanendx.py` | Srv6LanEndXISIS | ✅ | (complex, stores parsed content) |
| `attribute/bgpls/link/srv6lanendx.py` | Srv6LanEndXOSPF | ✅ | (complex, stores parsed content) |
| `attribute/bgpls/link/srv6locator.py` | Srv6Locator | ✅ | `make_srv6_locator(...)` |
| `attribute/bgpls/link/srv6sidstructure.py` | Srv6SidStructure | ✅ | `make_srv6_sid_structure(...)` |
| `attribute/bgpls/link/temetric.py` | TeMetric | ✅ | `make_temetric(int)` |
| `attribute/bgpls/link/unrsvpbw.py` | UnRsvpBw | ✅ | `make_unrsvpbw(list[float])` |

### BGP-LS Node Attributes ✅ COMPLETE

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/bgpls/node/isisarea.py` | IsisArea | ✅ | `content` property unpacks int |
| `attribute/bgpls/node/lterid.py` | LocalTeRid | ✅ | `content` property unpacks list[str] |
| `attribute/bgpls/node/nodeflags.py` | NodeFlags | ✅ | (FlagLS, use `unpack_bgpls`) |
| `attribute/bgpls/node/nodename.py` | NodeName | ✅ | `make_nodename(str)` |
| `attribute/bgpls/node/opaque.py` | NodeOpaque | ✅ | `content` property returns bytes |
| `attribute/bgpls/node/sralgo.py` | SrAlgorithm | ✅ | `content` property unpacks list[int] |
| `attribute/bgpls/node/srcap.py` | SrCapabilities | ✅ | Properties unpack from `_packed` |

### BGP-LS Prefix Attributes ✅ COMPLETE

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/bgpls/prefix/igpextags.py` | IgpExTags | ✅ | `content` property unpacks list[int] |
| `attribute/bgpls/prefix/igpflags.py` | IgpFlags | ✅ | (FlagLS, inherits pattern) |
| `attribute/bgpls/prefix/igptags.py` | IgpTags | ✅ | `content` property unpacks list[int] |
| `attribute/bgpls/prefix/opaque.py` | PrefixOpaque | ✅ | `content` property returns bytes |
| `attribute/bgpls/prefix/ospfaddr.py` | OspfForwardingAddress | ✅ | `content` property unpacks IP string |
| `attribute/bgpls/prefix/prefixmetric.py` | PrefixMetric | ✅ | `make_prefixmetric(int)` |
| `attribute/bgpls/prefix/srigpprefixattr.py` | SrIgpPrefixAttr | ✅ | (FlagLS, added LEN=1) |
| `attribute/bgpls/prefix/srprefix.py` | SrPrefix | ✅ | Properties unpack from `_packed` |
| `attribute/bgpls/prefix/srrid.py` | SrSourceRouterID | ✅ | `content` property unpacks IP string |

---

## Wave 5: Qualifiers ✅ COMPLETE

| File | Class | Status | Factory Method |
|------|-------|--------|----------------|
| `nlri/qualifier/path.py` | PathInfo | ✅ | `make_from_integer(int)`, `make_from_ip(str)` |
| `nlri/qualifier/rd.py` | RouteDistinguisher | ✅ | `make_from_elements(prefix, suffix)` |
| `nlri/qualifier/labels.py` | Labels | ✅ | `make_labels(list[int], bos)` |
| `nlri/qualifier/esi.py` | ESI | ✅ | `make_default()`, `make_esi(bytes)` |
| `nlri/qualifier/etag.py` | EthernetTag | ✅ | `make_etag(int)` |

---

## Wave 6: NLRI Types 🔄 PARTIAL

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `nlri/cidr.py` | CIDR | ✅ | `__init__(self, nlri: bytes)` |
| `nlri/inet.py` | INET | ✅ | `__init__(self, packed: bytes, ...)` |
| `nlri/label.py` | Label | ✅ | `__init__(self, packed: bytes, ...)` |
| `nlri/ipvpn.py` | IPVPN | ✅ | `__init__(self, packed: bytes, ...)` |
| `nlri/vpls.py` | VPLS | ✅ | `__init__(self, packed: bytes, ...)` |
| `nlri/rtc.py` | RTC | 🔄 | Origin as packed; RT needs `negotiated` |
| `nlri/flow.py` | Flow | ⊘ N/A | Builder pattern - excluded by design |
| `nlri/flow.py` | IPrefix4 | ⊘ N/A | FlowSpec component - excluded |
| `nlri/flow.py` | IPrefix6 | ⊘ N/A | FlowSpec component - excluded |

---

## Wave 7: EVPN + BGP-LS + MUP + MVPN NLRI ✅ COMPLETE

### EVPN NLRI

| File | Class | Status |
|------|-------|--------|
| `nlri/evpn/nlri.py` | EVPN (base) | ✅ |
| `nlri/evpn/nlri.py` | GenericEVPN | ✅ |
| `nlri/evpn/ethernetad.py` | EthernetAD | ✅ |
| `nlri/evpn/mac.py` | MAC | ✅ |
| `nlri/evpn/multicast.py` | Multicast | ✅ |
| `nlri/evpn/prefix.py` | Prefix | ✅ |
| `nlri/evpn/segment.py` | Segment | ✅ |

### BGP-LS NLRI

| File | Class | Status |
|------|-------|--------|
| `nlri/bgpls/nlri.py` | BGPLS (base) | ✅ |
| `nlri/bgpls/nlri.py` | GenericBGPLS | ✅ |
| `nlri/bgpls/node.py` | Node | ✅ |
| `nlri/bgpls/link.py` | Link | ✅ |
| `nlri/bgpls/prefixv4.py` | PrefixV4 | ✅ |
| `nlri/bgpls/prefixv6.py` | PrefixV6 | ✅ |
| `nlri/bgpls/srv6sid.py` | SRv6SID | ✅ |

### MUP NLRI

| File | Class | Status |
|------|-------|--------|
| `nlri/mup/nlri.py` | MUP (base) | ✅ |
| `nlri/mup/isd.py` | ISD | ✅ |
| `nlri/mup/dsd.py` | DSD | ✅ |
| `nlri/mup/t1st.py` | T1ST | ✅ |
| `nlri/mup/t2st.py` | T2ST | ✅ |

### MVPN NLRI

| File | Class | Status |
|------|-------|--------|
| `nlri/mvpn/nlri.py` | MVPN (base) | ✅ |
| `nlri/mvpn/sourcead.py` | SourceAD | ✅ |
| `nlri/mvpn/sourcejoin.py` | SourceJoin | ✅ |
| `nlri/mvpn/sharedjoin.py` | SharedJoin | ✅ |

---

## Wave 8: Messages ✅ COMPLETE

| File | Class | Status | Factory Method |
|------|-------|--------|----------------|
| `message/keepalive.py` | KeepAlive | ✅ | `make_keepalive()` |
| `message/notification.py` | Notification | ✅ | `make_notification(code, subcode, data)` |
| `message/notification.py` | Notify | ✅ | (subclass) |
| `message/refresh.py` | RouteRefresh | ✅ | `make_route_refresh(afi, safi, reserved)` |
| `message/open/__init__.py` | Open | ✅ | `make_open(...)` |
| `message/update/__init__.py` | Update | ✅ | `make_update(nlris, attributes)` |

---

## Summary Statistics

| Category | Done | Partial | Pending | N/A | Total |
|----------|------|---------|---------|-----|-------|
| Wave 1 | 4 | 0 | 0 | 0 | 4 |
| Wave 2 | 10 | 0 | 0 | 1 | 11 |
| Wave 3 | ~20 | 0 | 0 | 0 | ~20 |
| Wave 4 | ~50 | 0 | 0 | 3 | ~53 |
| Wave 5 | 5 | 0 | 0 | 0 | 5 |
| Wave 6 | 5 | 1 | 0 | 3 | 9 |
| Wave 7 | ~20 | 0 | 0 | 0 | ~20 |
| Wave 8 | 6 | 0 | 0 | 0 | 6 |
| **TOTAL** | **~120** | **1** | **0** | **7** | **~128** |

**Completion: ~99%** (120 done + 1 partial out of ~121 convertible classes)

---

## Recent Progress

### 2025-12-04 (Session 4)
- Converted BGP-LS prefix attributes to packed-bytes-first:
  - IgpTags: `content` property unpacks list of 32-bit tags
  - IgpExTags: `content` property unpacks list of 64-bit tags
  - PrefixOpaque: `content` property returns raw bytes (inherits from BaseLS)
  - OspfForwardingAddress: `content` property unpacks IP string
  - SrSourceRouterID: `content` property unpacks IP string
  - SrIgpPrefixAttr: Added missing LEN=1 (FlagLS pattern)
- Converted BGP-LS link SRv6 attributes to packed-bytes-first:
  - Srv6Capabilities: Properties + `make_srv6_capabilities(flags)` factory
  - Srv6EndpointBehavior: Properties + `make_srv6_endpoint_behavior(...)` factory
  - Srv6Locator: Properties + `make_srv6_locator(...)` factory
  - Srv6SidStructure: Properties + `make_srv6_sid_structure(...)` factory
- Updated tests to use factory methods, enabled previously skipped Srv6Locator test
- All 9 test suites pass (2699 unit, 74 encoding, 18 decoding)
- Wave 4 now complete (all BGP-LS link/node/prefix attributes done)

### 2025-12-04 (Session 3)
- Converted SrLabelIndex to packed-bytes-first: `__init__(packed)` + `make_labelindex(int)` factory
- Converted SrGb to packed-bytes-first: `__init__(packed)` + `make_srgb(list[tuple])` factory
- Converted Srv6SidStructure to packed-bytes-first: `__init__(packed)` + `make_sid_structure(...)` factory
- Updated GenericSrv6* classes: reordered params to `__init__(packed, code)`
- Marked Srv6L2Service/L3Service/SidInformation as N/A (container pattern like PrefixSid)
- Updated call sites in `configuration/static/mpls.py`
- Converted BGP-LS Node attributes (IsisArea, LocalTeRid, NodeOpaque, SrAlgorithm) to use `content` property
- All 9 test suites pass

### 2025-12-04 (Session 2)
- Converted MPRNLRI/MPURNLRI to hybrid packed-bytes pattern
- Added `OpenContext` class with `make_open_context()` caching factory
- Added `Negotiated.nlri_context(afi, safi)` method
- All tests passing: 2689 unit tests, 72 encoding, 18 decoding

### 2025-12-04 (Session 1)
Converted BGP-LS base classes and key subclasses to packed-bytes-first pattern:
- `BaseLS`, `FlagLS`, `GenericLSID` - base classes now use `__init__(packed: bytes)`
- 15+ link attributes (AdminGroup, IgpMetric, MaxBw, SrAdjacency, Srv6EndX, etc.)
- 4 node attributes (NodeFlags, NodeName, SrCapabilities)
- 3 prefix attributes (PrefixMetric, SrPrefix)
- All with proper `@property` accessors and factory methods

---

## Next Priority

**Wave 6 remaining:** RTC partial - needs `negotiated` context for RT encoding.

**Project nearly complete** - only 1 class with partial status (RTC in Wave 6).
