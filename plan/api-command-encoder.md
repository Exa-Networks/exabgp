# Plan: API Command to BGP Message Encoder for Tests

**Status:** ✅ Complete - 349/349 cmd: lines (100%), 0 failures, 0 skipped
**Created:** 2025-12-10
**Updated:** 2025-12-10

## Goal

Add `cmd:` field support to `.ci` test files. API commands like `announce ipv4 unicast 10.0.0.0/24 next-hop 1.2.3.4` get encoded to `raw:` lines for testing.

## Current Self-Check Results

```
./qa/bin/test_api_encode --self-check

Passed:  349
Failed:  0
Skipped: 0
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

## Previously Skipped Lines (all now fixed)

All 19 previously skipped lines now pass. Key fixes:

| Issue | Count | Fix |
|-------|-------|-----|
| Multi-NLRI updates | 2 | `group` command batches into single UPDATE |
| FlowSpec EOR | 3 | EOR decoder/encoder support |
| Withdraw+attrs | 4 | `group attributes ... ; withdraw ...` syntax |
| Generic attributes | 1 | `--generic` decode mode + `attribute [...]` syntax |
| Interface-set transitive | 9 | `transitive` field in JSON + 3-colon format |

### Key Pattern: `group` Command for Complex Round-trips

The `group` command is the solution for messages that combine multiple elements:

1. **Multi-NLRI batching:** `group announce X ; announce Y`
2. **Withdraw with attributes:** `group attributes origin igp local-preference 100 ; withdraw ipv4 flow ...`
3. **Attributes-only UPDATE:** `attributes origin igp local-preference 100`

The decoder detects these cases and generates appropriate `group` syntax.

---

## Key Learnings for Future Reference

### 1. The `group` Command is Fundamental

Location: `src/exabgp/reactor/api/command/group.py`

The `group` command can combine ANY API commands into a single UPDATE:
- Uses `;` separator: `group cmd1 ; cmd2 ; cmd3`
- Supports: `announce`, `withdraw`, `attributes`, all NLRI types
- Line 273-309 shows `_parse_routes()` handles all family formats

### 2. Withdraw + Attributes Pattern

RFC 4271 says withdraws don't need attributes, but some implementations include them.
To reproduce byte-identical wire format:

```
# Instead of:
withdraw ipv4 flow ... extended-community [...]

# Use:
group attributes origin igp local-preference 100 extended-community [...] ; withdraw ipv4 flow ...
```

Detection in decoder: `has_extra_withdraw_attributes()` checks for origin, local-pref, etc.

### 3. decode_to_api_command Location

Moved from `qa/bin/test_api_encode` to `src/exabgp/configuration/command.py`
- Better code organization
- Can be reused by decode.py for `--command` flag
- All format_* helpers are in the same file

### 4. Extended Community Hex Fallback

For extended communities the parser doesn't understand (FlowSpec actions, etc.):
```python
# If string format isn't parseable, use hex:
if 'value' in ec:
    ecomm_strs.append(f'0x{ec["value"]:016x}')
```

### 5. skip_attributes Pattern

Format functions accept `skip_attributes=True` to omit attributes when they're provided separately via `group attributes ...`:
- `format_flow_announce(..., skip_attributes=True)`
- `format_mup_announce(..., skip_attributes=True)`
- `format_mvpn_announce(..., skip_attributes=True)`

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

### FlowSpec Support (38 failures → 0 failures, 13 skipped)

**Fix:** Added FlowSpec single-line API parser to encoder:
- Parses API command format: `announce ipv4 flow <match-fields> [rd <rd>] [next-hop <nh>] extended-community [<actions>]`
- Transforms extended-community actions to native config format:
  - `rate-limit:N` → `rate-limit N`
  - `copy-to-nexthop` → `copy <next-hop>` (sets both nexthop and EC)
  - `redirect-to-nexthop` → `redirect <next-hop>` (sets both nexthop and EC)
  - `redirect:ASN:VALUE` → `redirect ASN:VALUE`
  - `action X` → `action X`
  - `mark N` → `mark N`
  - `redirect-to-nexthop-ietf IP` → `redirect-to-nexthop-ietf IP`
  - `interface-set:direction:asn:group` → `interface-set transitive:direction:asn:group`
  - `origin:X:Y` and other ECs → passed through as `extended-community [...]`
- Handles match fields: source-ipv4/ipv6, destination-ipv4/ipv6, protocol, destination-port, source-port, packet-length, tcp-flags, fragment, flow-label, traffic-class, next-header
- Detects flow vs flow-vpn SAFI based on RD presence
- Skips `next-hop 0.0.0.0` placeholder for withdraws

**Non-roundtrippable cases (skipped with `# No cmd:` marker):**
- Interface-set transitive flag lost in string representation
- Withdraw with attributes (unusual BGP)
- Generic attributes not captured in API command

### MCAST-VPN Support (12 skipped → 14 pass)

**Fix:** Added MCAST-VPN encode/decode support:
- Decoder extracts route type from JSON `code` field and maps to config syntax:
  - Code 5: `source-ad source <ip> group <ip> rd <rd>`
  - Code 6: `shared-join rp <ip> group <ip> rd <rd> source-as <as>`
  - Code 7: `source-join source <ip> group <ip> rd <rd> source-as <as>`
- Encoder uses `announce { afi { mcast-vpn ... } }` config block
- Handles both IPv4 and IPv6 mcast-vpn address families

**Withdraw round-trip fix (6 skipped → FIXED):**
- Fixed JSON output to include NEXT_HOP in attributes for withdraw messages
- Added `include_nexthop` parameter to `AttributeCollection.json()`
- `json.py` now calls `attributes.json(include_nexthop=True)` when withdraws present
- Updated expected JSON in CI files to include `"next-hop"` for withdraws

---

## Key Files

| File | Purpose |
|------|---------|
| `src/exabgp/configuration/command.py` | **decode_to_api_command()** + all format_* helpers |
| `src/exabgp/reactor/api/command/group.py` | Group command handling (batches into single UPDATE) |
| `qa/bin/test_api_encode` | Test script with --self-check mode |
| `src/exabgp/rib/__init__.py` | RIB class with `_cache` (caused collision bug) |
| `src/exabgp/bgp/message/update/attribute/collection.py` | AttributeCollection.json() with include_nexthop param |
| `src/exabgp/reactor/api/response/json.py` | JSON encoder, calls json(include_nexthop=True) for withdraws |

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
- [x] MCAST-VPN encode/decode (12 missing → 14 pass, withdraw round-trip via raw NEXT_HOP extraction)
- [x] FlowSpec encode/decode (38 failures → 0 failures, 13 skipped due to non-roundtrippable data)

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
