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

## Wave 4: MP Attributes + BGP-LS + SR ⏳ PENDING

### MP Attributes

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/mprnlri.py` | MPRNLRI | ⏳ | Takes `(afi, safi, nlris)` not packed |
| `attribute/mpurnlri.py` | MPURNLRI | ⏳ | Takes `(afi, safi, nlris)` not packed |

### SR Attributes

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/sr/prefixsid.py` | PrefixSid | ✅ | Already correct |
| `attribute/sr/labelindex.py` | SrLabelIndex | ⏳ | Has `packed` param but ignores it |
| `attribute/sr/srgb.py` | SrGb | ⏳ | Has `packed` param but ignores it |

### SRv6 Attributes

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/sr/srv6/generic.py` | GenericSrv6ServiceSubTlv | ⏳ | Reorder params |
| `attribute/sr/srv6/generic.py` | GenericSrv6ServiceDataSubSubTlv | ⏳ | Reorder params |
| `attribute/sr/srv6/l2service.py` | Srv6L2Service | ⏳ | Has `packed` param but ignores it |
| `attribute/sr/srv6/l3service.py` | Srv6L3Service | ⏳ | Has `packed` param but ignores it |
| `attribute/sr/srv6/sidinformation.py` | Srv6SidInformation | ⏳ | Has `packed` param but ignores it |
| `attribute/sr/srv6/sidstructure.py` | Srv6SidStructure | ⏳ | Has `packed` param but ignores it |

### BGP-LS Base Classes

| File | Class | Status | Notes |
|------|-------|--------|-------|
| `attribute/bgpls/linkstate.py` | LinkState | ⏳ | Container - takes `list[BaseLS]` |
| `attribute/bgpls/linkstate.py` | BaseLS | ⏳ | Base class for all LS attributes |
| `attribute/bgpls/linkstate.py` | FlagLS | ⏳ | Base class for flag-based LS |
| `attribute/bgpls/linkstate.py` | GenericLSID | ⏳ | Takes `content: bytes` |

### BGP-LS Link Attributes

| File | Class | Status |
|------|-------|--------|
| `attribute/bgpls/link/admingroup.py` | AdminGroup | ⏳ |
| `attribute/bgpls/link/igpmetric.py` | IgpMetric | ⏳ |
| `attribute/bgpls/link/linkname.py` | LinkName | ⏳ |
| `attribute/bgpls/link/maxbw.py` | MaxBw | ⏳ |
| `attribute/bgpls/link/mplsmask.py` | MplsMask | ⏳ |
| `attribute/bgpls/link/opaque.py` | LinkOpaque | ⏳ |
| `attribute/bgpls/link/protection.py` | Protection | ⏳ |
| `attribute/bgpls/link/rsvpbw.py` | RsvpBw | ⏳ |
| `attribute/bgpls/link/rterid.py` | RouterId | ⏳ |
| `attribute/bgpls/link/sradj.py` | SrAdjacency | ⏳ |
| `attribute/bgpls/link/sradjlan.py` | SrAdjacencyLan | ⏳ |
| `attribute/bgpls/link/srlg.py` | Srlg | ⏳ |
| `attribute/bgpls/link/srv6capabilities.py` | Srv6Capabilities | ⏳ |
| `attribute/bgpls/link/srv6endpointbehavior.py` | Srv6EndpointBehavior | ⏳ |
| `attribute/bgpls/link/srv6endx.py` | Srv6EndX | ⏳ |
| `attribute/bgpls/link/srv6lanendx.py` | Srv6LanEndX | ⏳ |
| `attribute/bgpls/link/srv6locator.py` | Srv6Locator | ⏳ |
| `attribute/bgpls/link/srv6sidstructure.py` | Srv6SidStructure | ⏳ |
| `attribute/bgpls/link/temetric.py` | TeMetric | ⏳ |
| `attribute/bgpls/link/unrsvpbw.py` | UnrsvpBw | ⏳ |

### BGP-LS Node Attributes

| File | Class | Status |
|------|-------|--------|
| `attribute/bgpls/node/isisarea.py` | IsisArea | ⏳ |
| `attribute/bgpls/node/lterid.py` | LterID | ⏳ |
| `attribute/bgpls/node/nodeflags.py` | NodeFlags | ⏳ |
| `attribute/bgpls/node/nodename.py` | NodeName | ⏳ |
| `attribute/bgpls/node/opaque.py` | NodeOpaque | ⏳ |
| `attribute/bgpls/node/sralgo.py` | SrAlgorithm | ⏳ |
| `attribute/bgpls/node/srcap.py` | SrCapabilities | ⏳ |

### BGP-LS Prefix Attributes

| File | Class | Status |
|------|-------|--------|
| `attribute/bgpls/prefix/igpextags.py` | IgpExTags | ⏳ |
| `attribute/bgpls/prefix/igpflags.py` | IgpFlags | ⏳ |
| `attribute/bgpls/prefix/igptags.py` | IgpTags | ⏳ |
| `attribute/bgpls/prefix/opaque.py` | PrefixOpaque | ⏳ |
| `attribute/bgpls/prefix/ospfaddr.py` | OspfAddr | ⏳ |
| `attribute/bgpls/prefix/prefixmetric.py` | PrefixMetric | ⏳ |
| `attribute/bgpls/prefix/srigpprefixattr.py` | SrIgpPrefixAttr | ⏳ |
| `attribute/bgpls/prefix/srprefix.py` | SrPrefix | ⏳ |
| `attribute/bgpls/prefix/srrid.py` | SrRid | ⏳ |

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
| Wave 4 | 1 | 0 | 49 | 0 | 50 |
| Wave 5 | 5 | 0 | 0 | 0 | 5 |
| Wave 6 | 5 | 1 | 0 | 3 | 9 |
| Wave 7 | ~20 | 0 | 0 | 0 | ~20 |
| Wave 8 | 6 | 0 | 0 | 0 | 6 |
| **TOTAL** | **~71** | **1** | **49** | **4** | **~125** |

**Completion: ~58%** (71 done + 1 partial out of ~121 convertible classes)

---

## Next Priority

**Wave 4** contains the remaining 49 classes to convert:
1. Start with base classes (`BaseLS`, `FlagLS`) - enables cascade to subclasses
2. Then MP attributes (`MPRNLRI`, `MPURNLRI`)
3. Then SR attributes (8 classes)
4. Then BGP-LS subclasses (~40 classes) - mostly mechanical once base is done
