# Plan: API Command to BGP Message Encoder for Tests

**Status:** 🔄 In Progress - 295/349 cmd: lines (85%), 54 skipped (FlowSpec + non-roundtrippable)
**Created:** 2025-12-10
**Updated:** 2025-12-10

## Goal

Add `cmd:` field support to `.ci` test files. API commands like `announce ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4` get encoded to `raw:` lines for testing.

## Current Self-Check Results

```
./qa/bin/test_api_encode --self-check

Passed:  295
Failed:  0
Skipped: 54
```

---

## Completed Fixes

### 1. Missing Attributes in decode_to_api_command()

**Fixed:** Added support for:
- `atomic-aggregate`
- `aggregator` (format: "asn:ip")
- `extended-community` (extracts string representation)
- `originator-id`
- `cluster-list`
- Generic attributes (`attribute-0xNN-0xNN` format)

### 2. RIB Cache Collision Bug

**Problem:** RIB uses class-level `_cache` dict keyed by neighbor name. Multiple encodes with same neighbor IP (127.0.0.1) reused cached routes.

**Fix:** Use unique neighbor IP per encode call (`127.0.{n>>8}.{n&255}`) and call `neighbor.rib.uncache()` after encoding.

### 3. Path-information/Add-path Support

**Problem:** Original messages with add-path had 4 extra bytes but re-encoded without.

**Fix:**
- Extract `path-information` from decoded JSON
- Enable add-path capability in config when `path-information` is in command

### 4. eBGP vs iBGP Handling

**Problem:** eBGP messages don't have LOCAL_PREF attribute, but encoder used iBGP defaults.

**Fix:** Parse `option:asn:` from CI files and use correct peer-as for encoding.

### 5. Withdraw Encoding

**Problem:** Withdraw commands failed because config parser requires next-hop.

**Fix:**
- Add dummy next-hop for withdraw commands
- Use `UpdateCollection([], [route.nlri], AttributeCollection())` for withdraws
- Skip complex families (flow, vpls, mup, mcast-vpn) in withdraw decode

### 6. VPN Family Support

**Fixed:** Extract `rd` and `label` from JSON and include in decoded command.

### 7. API Command Format

**Fixed:** Decoder now outputs correct API format per convention:
- IPv4: `announce route 10.0.0.0/24 next-hop 1.2.3.4`
- IPv6: `announce ipv6 unicast 2001:db8::/32 next-hop 2001:db8::1`
- Encoder handles both `route` format and `afi safi` format
- Proper handling of VPN routes (with rd/label detection)

---

## Skipped Lines (54 total)

The following raw: lines are skipped for round-trip testing:

| File | Skipped | Reason |
|------|---------|--------|
| conf-flow.ci | 13 | FlowSpec (complex match/then syntax) |
| conf-flow-redirect.ci | 5 | FlowSpec |
| api-flow-merge.ci | 11 | FlowSpec |
| api-broken-flow.ci | 8 | FlowSpec |
| api-flow.ci | 6 | FlowSpec |
| api-mvpn.ci | 6 | MCAST-VPN withdraws (NEXT_HOP attr not in JSON) |
| conf-mvpn.ci | 2 | Multi-NLRI updates |
| api-ipv4.ci | 1 | FlowSpec |
| api-ipv6.ci | 1 | FlowSpec |
| api-vpnv4.ci | 1 | Withdraw+attrs |
| **Total** | **54** | |

### Why These Can't Round-Trip

**FlowSpec** uses complex match/then syntax:
```
flow route source 10.0.0.0/24 {
    match { protocol tcp; destination-port 80; }
    then { rate-limit 1000; discard; }
}
```

**MCAST-VPN withdraws** include NEXT_HOP attribute in wire format, but JSON output doesn't expose it.

**Multi-NLRI** updates have multiple NLRIs bundled; encoder produces separate messages.

### Future Work

To achieve higher coverage, would need:
1. FlowSpec encoder/decoder with match/then syntax

---

## Recently Fixed (Session 2025-12-10)

### MUP (Mobile User Plane) Support (10 skipped → FIXED)

**Fix:** Added full MUP encode/decode support:
- Decoder extracts route type from JSON `name` field and maps to config syntax:
  - `InterworkSegmentDiscoveryRoute` → `mup-isd`
  - `DirectSegmentDiscoveryRoute` → `mup-dsd`
  - `Type1SessionTransformedRoute` → `mup-t1st`
  - `Type2SessionTransformedRoute` → `mup-t2st`
- Handles all MUP-specific fields: `rd`, `teid`, `qfi`, `endpoint_ip`, `source_ip`, `prefix_ip`
- T2ST calculates `teid_len` from `endpoint_len - ip_bits`
- Added `bgp-prefix-sid-srv6` attribute support for MUP routes

**Bug fixes in exabgp core:**
1. Fixed T1ST JSON missing comma before `source_ip_len` (`src/exabgp/bgp/message/update/nlri/mup/t1st.py:277`)
2. Fixed SRv6 SID Information JSON with unformatted `%s/%d` placeholders (`src/exabgp/bgp/message/update/attribute/sr/srv6/sidinformation.py:127`)

### L2VPN/VPLS Support (5 skipped → FIXED)

**Fix:** Added VPLS encode/decode support:
- Decoder extracts `rd`, `endpoint`, `base`, `offset`, `size` from JSON
- Generates API command: `announce vpls rd X endpoint Y base Z offset A size B next-hop NH ...attrs`
- Encoder parses VPLS commands using `l2vpn { vpls ... }` config block
- Supports both announce and withdraw operations

### Multi-NLRI Messages (7 failures → FIXED)

**Fix:** Added `announce attributes ... nlri X Y Z` syntax support:
- Decode now returns `list[str]` instead of `str | None`
- When multiple NLRIs in UPDATE, decoder outputs `announce attributes next-hop Y ... nlri X1 X2 X3`
- Encoder handles this syntax by creating all routes with same attributes

### AS4 Capability (1 failure → FIXED)

**Fix:** Added `asn4_disabled` parameter to `encode_api_command()`:
- Detect ASN4 capability status from neighbor config
- Pass to encoder to use `asn4 disable;` in capability section when needed

### BGP-Prefix-SID (2 failures → FIXED)

**Fix:** Added `bgp-prefix-sid` attribute extraction in `format_attributes()`:
- Extracts `sr-label-index` and `sr-srgbs` from JSON
- Formats as `bgp-prefix-sid [ index, [ ( base,range ) ] ]`

### EOR (End-of-RIB) Support (81 messages → FIXED)

**Fix:** Added full EOR support in encoder and decoder:
- `announce eor [afi safi]` API syntax
- Legacy IPv4 unicast EOR (empty UPDATE)
- MP EOR for all address families
- Auto-detection in self-check from wire format
- Skip marker for messages that can't round-trip (`# No cmd:`)

### MCAST-VPN Support (12 skipped → 8 pass, 6 skipped)

**Fix:** Added MCAST-VPN encode/decode support:
- Decoder extracts route type from JSON `code` field and maps to config syntax:
  - Code 5: `source-ad source <ip> group <ip> rd <rd>`
  - Code 6: `shared-join rp <ip> group <ip> rd <rd> source-as <as>`
  - Code 7: `source-join source <ip> group <ip> rd <rd> source-as <as>`
- Encoder uses `announce { afi { mcast-vpn ... } }` config block
- Handles both IPv4 and IPv6 mcast-vpn address families
- 6 skipped for non-roundtrippable reasons:
  - Withdraw messages have NEXT_HOP attr in wire format but not in JSON
  - Multi-NLRI updates (encoder produces separate messages)

---

## Key Files

| File | Purpose |
|------|---------|
| `qa/bin/test_api_encode` | Main test script with encode/decode functions |
| `src/exabgp/rib/__init__.py` | RIB class with `_cache` (caused collision bug) |

---

## Resume Context

When resuming, run:
```bash
./qa/bin/test_api_encode --self-check 2>&1 | tail -10
```

To see current failure patterns:
```bash
./qa/bin/test_api_encode --self-check -v 2>&1 | grep -E "(FAIL|cmd:)" | head -40
```

---

## Progress

- [x] Created `qa/bin/test_api_encode` with --self-check mode
- [x] Removed invalid cmd: lines from CI files
- [x] All 14 test_everything tests pass
- [x] Fix missing attributes in decode (aggregator, atomic-aggregate, extended-community)
- [x] Fix RIB cache collision bug (unique neighbor IPs + uncache)
- [x] Fix path-information/add-path support
- [x] Fix eBGP/iBGP peer-as handling
- [x] Fix withdraw encoding
- [x] Fix VPN decode (RD/label extraction)
- [x] Add originator-id and cluster-list support
- [x] Add generic attribute support
- [x] Skip unsupported families (FlowSpec, VPLS, MUP, MCAST-VPN)
- [x] API format: IPv4=route, IPv6=ipv6 unicast
- [x] Multi-NLRI round-trip (fixed via `announce attributes ... nlri X Y Z` syntax)
- [x] AS4 capability handling (fixed via `asn4_disabled` parameter)
- [x] BGP-Prefix-SID attribute (fixed in `format_attributes()`)
- [x] EOR (End-of-RIB) support for all address families
- [x] Skip marker for non-roundtrippable messages (`# No cmd:`)
- [x] Withdraw with attributes (skipped via `# No cmd:` marker)
- [x] L2VPN/VPLS encode/decode (5 skipped → 0)
- [x] MUP encode/decode (10 skipped → 0) + fixed 2 JSON bugs in exabgp core
- [x] MCAST-VPN encode/decode (12 missing → 8 pass, 6 skipped for withdraw/multi-NLRI)
- [ ] FlowSpec encode/decode (43 skipped)

---

## Tests

```bash
# Full test suite - must pass
./qa/bin/test_everything

# Self-check round-trip
./qa/bin/test_api_encode --self-check

# Verbose mode for debugging
./qa/bin/test_api_encode --self-check -v qa/encoding/conf-addpath.ci
```
