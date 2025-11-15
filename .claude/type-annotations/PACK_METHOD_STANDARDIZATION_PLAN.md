# Pack Method Standardization Plan

## Objective

Standardize all `pack()` method naming conventions following the pattern established for `unpack()` methods:
- **BGP Protocol Elements** (Messages, Attributes, NLRIs): `pack(negotiated: Negotiated)` - REQUIRED
- **Utility/Data Classes** (ESI, Labels, TLVs, etc.): `pack_X()` where X describes what is being packed - NO negotiated

## Current State Analysis

**Total pack() methods found:** 67

### Category 1: Message Classes (37) - ✅ ALREADY CORRECT

These classes correctly implement `pack(negotiated: Negotiated)`:

**Attributes (15):**
- LocalPreference, MED, GenericAttribute, MPRNLRI, AIGP
- Aggregator, Aggregator4, ASPath, AS4Path, NextHop, NextHopSelf
- MPURNLRI, AtomicAggregate, Origin, PMSI

**Communities (4):**
- LargeCommunity, Communities, Community, ExtendedCommunity

**Route Reflection (2):**
- OriginatorId, ClusterList

**Segment Routing (1):**
- PrefixSid (has default None - should be reviewed)

**NLRIs (6):**
- IPVPN, NodeNLRI, LinkNLRI, PrefixNLRI, PrefixIPv4NLRI, PrefixIPv6NLRI

**Messages/Capabilities (4):**
- OperationalAdvisory, OperationalQuery, OperationalCounter, OperationalResponse

**IP Classes (3):**
- IP, IP (second instance), _NoNextHop (anomaly - takes data parameter)

**Attributes Container (2):**
- Attribute (base class with signature `pack(_: Any = None)`)
- Attributes (collection with `pack(negotiated: Negotiated, with_default: bool = True)`)

**Action: NONE** - These are correct as-is.

---

### Category 2: Utility/Data Classes (28) - ⚠️ NEEDS RENAME

These classes should rename `pack()` to `pack_X()`:

#### NLRI Qualifiers (7)

| File | Class | Current | Rename To | Purpose |
|------|-------|---------|-----------|---------|
| `nlri/qualifier/esi.py:58` | ESI | `pack()` | `pack_esi()` | Ethernet Segment Identifier |
| `nlri/qualifier/labels.py:73` | Labels | `pack()` | `pack_labels()` | MPLS Labels |
| `nlri/qualifier/etag.py:53` | EthernetTag | `pack()` | `pack_etag()` | EVPN Ethernet Tag |
| `nlri/qualifier/rd.py:191` | RouteDistinguisher | `pack()` | `pack_rd()` | Route Distinguisher |
| `nlri/qualifier/path.py:44` | PathInfo | `pack()` | `pack_path()` | Path Information |
| `nlri/qualifier/mac.py:78` | MACQUAL | `pack()` | `pack_mac()` | MAC Address |
| `nlri/qualifier/protocol.py:23` | ProtocolQualifier | `pack()` | `pack_protocol()` | Protocol Qualifier |

#### Flow Components (3)

| File | Class | Current | Rename To | Purpose |
|------|-------|---------|-----------|---------|
| `nlri/flow/ipv4.py:51` | IPrefix4 | `pack()` | `pack_prefix()` | IPv4 Prefix |
| `nlri/flow/ipv6.py:51` | IPrefix6 | `pack()` | `pack_prefix()` | IPv6 Prefix |
| `nlri/flow/actions.py:100` | IOperation | `pack()` | `pack_operation()` | Flow Operation |

#### SR Sub-TLVs (7)

| File | Class | Current | Rename To | Purpose |
|------|-------|---------|-----------|---------|
| `attribute/sr/labelindex.py:40` | LabelIndex | `pack()` | `pack_tlv()` | SR Label Index TLV |
| `attribute/sr/srgb.py:56` | SrGb | `pack()` | `pack_tlv()` | SR Global Block TLV |
| `attribute/sr/srv6/l2service.py:74` | SRv6L2Service | `pack()` | `pack_tlv()` | SRv6 L2 Service TLV |
| `attribute/sr/srv6/l3service.py:74` | SRv6L3Service | `pack()` | `pack_tlv()` | SRv6 L3 Service TLV |
| `attribute/sr/srv6/generic.py:24` | SRv6EndpointBehavior | `pack()` | `pack_tlv()` | SRv6 Endpoint Behavior |
| `attribute/sr/srv6/generic.py:40` | SRv6BGPPeerNode | `pack()` | `pack_tlv()` | SRv6 BGP Peer Node |
| `attribute/sr/srv6/sidstructure.py:76` | SRv6SIDStructure | `pack()` | `pack_tlv()` | SRv6 SID Structure |

#### BGP-LS TLVs (8)

| File | Class | Current | Rename To | Purpose |
|------|-------|---------|-----------|---------|
| `nlri/bgpls/tlvs/igpflags.py:80` | IGPFlags | `pack()` | `pack_tlv()` | IGP Flags TLV |
| `nlri/bgpls/tlvs/linkidentifier.py:75` | LinkIdentifiers | `pack()` | `pack_tlv()` | Link Identifiers TLV |
| `nlri/bgpls/tlvs/areaid.py:45` | AreaID | `pack()` | `pack_tlv()` | Area ID TLV |
| `nlri/bgpls/tlvs/ipreach.py:48` | IPReach | `pack()` | `pack_tlv()` | IP Reachability TLV |
| `nlri/bgpls/tlvs/asn.py:47` | ASN | `pack()` | `pack_tlv()` | ASN TLV |
| `nlri/bgpls/tlvs/nodename.py:44` | NodeName | `pack()` | `pack_tlv()` | Node Name TLV |
| `nlri/bgpls/tlvs/routerid.py:47` | RouterID | `pack()` | `pack_tlv()` | Router ID TLV |
| `nlri/bgpls/tlvs/opaque.py:39` | OpaqueTLV | `pack()` | `pack_tlv()` | Opaque TLV |

#### AIGP Sub-TLV (1)

| File | Class | Current | Rename To | Purpose |
|------|-------|---------|-----------|---------|
| `attribute/aigp.py:32` | AIGPValue | `pack()` | `pack_tlv()` | AIGP Value TLV |

#### Protocol (1)

| File | Class | Current | Rename To | Purpose |
|------|-------|---------|-----------|---------|
| `protocol/__init__.py:55` | Protocol | `pack()` | `pack_protocol()` | Protocol Identifier |

#### Anomaly (1)

| File | Class | Current | Issue |
|------|-------|---------|-------|
| `attribute/sr/srv6/sidinformation.py:93` | SRv6SID | `pack(packed: Any = None)` | Unusual signature - investigate |

**Action: RENAME** all 28 classes from `pack()` to appropriate `pack_X()`.

---

### Category 3: Special Cases to Review (2)

1. **Attribute (base class)** - `pack(_: Any = None)` - Uses underscore parameter name, subclasses override
2. **_NoNextHop** - `pack(data: Any, negotiated: Optional[Negotiated] = None)` - Sentinel object with unusual signature

---

## Implementation Plan

### Phase 1: Rename NLRI Qualifiers (7 classes)
**Files to modify:** 7 files
**Estimated impact:** LOW - self-contained data structures
**Priority:** HIGH - most commonly used utility classes

1. ESI.pack() → ESI.pack_esi()
2. Labels.pack() → Labels.pack_labels()
3. EthernetTag.pack() → EthernetTag.pack_etag()
4. RouteDistinguisher.pack() → RouteDistinguisher.pack_rd()
5. PathInfo.pack() → PathInfo.pack_path()
6. MACQUAL.pack() → MACQUAL.pack_mac()
7. ProtocolQualifier.pack() → ProtocolQualifier.pack_protocol()

**Impact Analysis:**
- Search for all `.pack()` calls on these types
- Update all call sites
- Update tests

### Phase 2: Rename Flow Components (3 classes)
**Files to modify:** 3 files
**Estimated impact:** LOW - used within flow module
**Priority:** MEDIUM

1. IPrefix4.pack() → IPrefix4.pack_prefix()
2. IPrefix6.pack() → IPrefix6.pack_prefix()
3. IOperation.pack() → IOperation.pack_operation()

### Phase 3: Rename SR Sub-TLVs (7 classes)
**Files to modify:** 7 files
**Estimated impact:** LOW - SR-specific code
**Priority:** MEDIUM

All rename to `pack_tlv()`:
- LabelIndex, SrGb, SRv6L2Service, SRv6L3Service, SRv6EndpointBehavior, SRv6BGPPeerNode, SRv6SIDStructure

### Phase 4: Rename BGP-LS TLVs (8 classes)
**Files to modify:** 8 files
**Estimated impact:** LOW - BGP-LS specific code
**Priority:** MEDIUM

All rename to `pack_tlv()`:
- IGPFlags, LinkIdentifiers, AreaID, IPReach, ASN, NodeName, RouterID, OpaqueTLV

### Phase 5: Rename Remaining Classes (3 classes)
**Files to modify:** 3 files
**Estimated impact:** LOW
**Priority:** LOW

1. AIGPValue.pack() → AIGPValue.pack_tlv()
2. Protocol.pack() → Protocol.pack_protocol()
3. SRv6SID.pack() → SRv6SID.pack_tlv() (investigate unusual signature first)

---

## Benefits

1. **Type Safety**: MyPy can enforce that Message classes take negotiated
2. **Clear Intent**: Method name indicates what is being packed
3. **Consistency**: Matches unpack pattern (unpack_attribute, unpack_nlri, etc.)
4. **Easier Maintenance**: Clear separation between protocol elements and data structures
5. **Better Documentation**: Self-documenting code

---

## Risk Assessment

**LOW RISK:**
- Most changes are in self-contained utility classes
- Strong test coverage will catch issues
- Changes are mechanical and straightforward

**MEDIUM RISK:**
- Need to find and update all call sites
- Some classes may have many callers

**MITIGATION:**
- Use grep/search to find all call sites
- Update in small batches with testing
- Run full test suite after each phase

---

## Testing Strategy

After each phase:
1. ✅ `ruff format src && ruff check src` - Linting
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/ -x -q` - Unit tests
3. ✅ `./qa/bin/functional encoding` - Functional tests
4. ✅ `python3 -m mypy src/exabgp --show-error-codes 2>&1 | grep "error:" | wc -l` - Check mypy errors

---

## Execution Order

1. **Phase 1**: NLRI Qualifiers (highest impact, most commonly used)
2. **Phase 2**: Flow Components
3. **Phase 3**: SR Sub-TLVs
4. **Phase 4**: BGP-LS TLVs
5. **Phase 5**: Remaining classes

Each phase:
- Rename method in class definition
- Find and update all call sites
- Run tests
- Commit

---

## Estimated Timeline

- **Phase 1**: 30-45 minutes (7 classes + testing)
- **Phase 2**: 15-20 minutes (3 classes + testing)
- **Phase 3**: 25-35 minutes (7 classes + testing)
- **Phase 4**: 30-40 minutes (8 classes + testing)
- **Phase 5**: 15-25 minutes (3 classes + testing)

**Total**: 2-3 hours

---

## Current MyPy Status

- Baseline: 1,149 errors
- Current: 576 errors (50% reduction)
- Expected after completion: Further reduction as pack signatures become more strict
