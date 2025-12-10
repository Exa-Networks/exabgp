# FlowSpec Round-Trip Limitations

This document explains why certain FlowSpec BGP messages cannot complete a round-trip test (decode → encode → compare). In all cases, the issue is **information loss during decoding** - the wire format contains data that is not preserved in the API command string representation.

---

## 1. Interface-Set Transitive Flag

### The Problem

The interface-set extended community has a **transitive flag** encoded in the wire format, but this flag is **not preserved** in the string representation output by the decoder.

### Wire Format Analysis

**Original message:**
```
1:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:004F:02:000000384001010040020040050400000064C010180702000000FE80FE4702CAFFEE0140018006000000000000800E0C0001850000060220CAFFEE01
```

**Extended Community attribute breakdown (C01018...):**

| Offset | Hex | Meaning |
|--------|-----|---------|
| C010 | Attribute flags + type | Optional, Transitive, Extended Community (type 16) |
| 18 | Length | 24 bytes (3 extended communities × 8 bytes) |
| **0702** 000000FE 80FE | EC #1 | Type 0x0702 = **Transitive** FlowSpec Interface-Set (output:254:254) |
| **4702** CAFFEE01 4001 | EC #2 | Type 0x4702 = **Non-Transitive** FlowSpec Interface-Set (input:3405770241:1) |
| 8006 00000000 0000 | EC #3 | Type 0x8006 = Traffic Rate (rate-limit:0) |

**Key observation:** The first byte of the extended community type encodes transitivity:
- `0x07` = Transitive (high bit = 0)
- `0x47` = Non-Transitive (high bit = 0, but bit 6 = 1, indicating non-transitive)

### Decoder Output

```json
"extended-community": [
  {"value": 504966108235596030, "string": "interface-set:output:254:254"},
  {"value": 5116875327204835329, "string": "interface-set:input:3405770241:1"},
  {"value": 9225060886715039744, "string": "rate-limit:0"}
]
```

**The string `interface-set:output:254:254` does not indicate whether it's transitive or non-transitive.**

### API Command Generated

```
announce ipv4 flow source-ipv4 202.255.238.1/32 extended-community [interface-set:output:254:254 interface-set:input:3405770241:1 rate-limit:0]
```

### Re-encoding Attempt

The encoder must convert `interface-set:output:254:254` back to config syntax. Since the transitive flag is lost, it uses the default:

```
interface-set transitive:output:254:254
```

This produces wire bytes `0702...` (transitive), but the original had `0702...` (transitive) for the first one and `4702...` (non-transitive) for the second.

### Resulting Mismatch

| Community | Original | Re-encoded | Match? |
|-----------|----------|------------|--------|
| output:254:254 | `0702000000FE80FE` | `0702000000FE80FE` | ✓ |
| input:3405770241:1 | `4702CAFFEE014001` | `0702CAFFEE014001` | ✗ |
| rate-limit:0 | `8006000000000000` | `8006000000000000` | ✓ |

**The second interface-set has type byte `47` (non-transitive) in original but `07` (transitive) in re-encoded.**

### Why This Cannot Be Fixed

The decoder's string output format (`interface-set:direction:asn:group`) has no field for the transitive flag. Adding it would require changing the JSON output format, which is a breaking API change.

---

## 2. Withdraw With Attributes

### The Problem

Standard BGP UPDATE messages for route withdrawal contain **only the withdrawn routes** - no path attributes. However, some implementations send withdrawals that include path attributes. The encoder produces standard-compliant withdrawals without attributes.

### Wire Format Analysis

**Original message:**
```
2:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0043:02:0000002C4001010040020040050400000064C01008800600003F800000800F100001850C0120AAAAAAAA0220AAAAAAAA
```

**UPDATE message structure:**

| Offset | Hex | Meaning |
|--------|-----|---------|
| 0000 | Withdrawn Routes Length | 0 bytes (no IPv4 unicast withdrawals) |
| 002C | Path Attributes Length | 44 bytes |
| 4001 0100 | ORIGIN | IGP (0x00) |
| 4002 00 | AS_PATH | Empty |
| 4005 04 00000064 | LOCAL_PREF | 100 |
| C010 08 800600003F800000 | EXTENDED_COMMUNITY | rate-limit:1 |
| 800F 10 0001850C... | MP_UNREACH_NLRI | FlowSpec withdraw |

**The message has path attributes (ORIGIN, LOCAL_PREF, EXTENDED_COMMUNITY) alongside MP_UNREACH_NLRI.**

### JSON Output

```json
{
  "attribute": {
    "origin": "igp",
    "local-preference": 100,
    "extended-community": [{"value": 9225060887780392960, "string": "rate-limit:1"}]
  },
  "withdraw": {
    "ipv4 flow": [...]
  }
}
```

### API Command Generated

```
withdraw ipv4 flow destination-ipv4 170.170.170.170/32 source-ipv4 170.170.170.170/32 next-hop 0.0.0.0 extended-community [rate-limit:1]
```

### Re-encoding Behavior

The encoder follows RFC 4271 Section 4.3:
> "An UPDATE message SHOULD NOT include the same address prefix in the WITHDRAWN ROUTES and Network Layer Reachability Information fields."

For withdrawals, the encoder produces:
- MP_UNREACH_NLRI with the withdrawn routes
- **No path attributes** (empty attribute section)

### Resulting Mismatch

| Field | Original | Re-encoded |
|-------|----------|------------|
| Path Attrs Length | 44 bytes | 0 bytes |
| ORIGIN | Present | Absent |
| LOCAL_PREF | Present | Absent |
| EXTENDED_COMMUNITY | Present | Absent |
| MP_UNREACH_NLRI | Present | Present |

**The re-encoded message is 44 bytes shorter because it omits path attributes.**

### Why This Is Correct Behavior

1. **RFC 4271 compliance:** Withdrawals should not carry path attributes
2. **Semantic equivalence:** Both messages withdraw the same routes
3. **Receiver behavior:** Any BGP speaker will process both identically (remove the route)

The original message is technically valid but unusual. The encoder produces the canonical form.

---

## 3. Partially-Decoded Generic Attributes

### The Problem

Some BGP attributes are partially decoded by ExaBGP - they're recognized enough to be given a human-readable representation, but the raw bytes are not preserved. These appear as `attribute-0xNN-0xNN` in JSON but with a **string value** (not hex).

**Note:** Pure generic attributes (those with hex values like `"0x00000064"`) **are now supported** for round-trip using the `attribute [0xNN 0xNN 0xHEX]` syntax.

### Example: redirect-to-nexthop-ietf

**Original message:**
```
1:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0051:02:0000003A4001010040020040050400000064C01914000C2A020B800000000100000000000000010000800E1200018500000C0120C0A8000202200A000001
```

**Attribute 0x19 (type 25):**
- Recognized as redirect-to-nexthop-ietf
- Decoded to human-readable: `"redirect-to-nexthop-ietf 2a02:b80:0:1::1"`
- Raw bytes NOT preserved

### JSON Output

```json
{
  "attribute": {
    "origin": "igp",
    "local-preference": 100,
    "attribute-0x19-0xC0": "redirect-to-nexthop-ietf 2a02:b80:0:1::1"
  }
}
```

**Note:** The value is a human-readable string, not hex (`0x...`).

### Why This Cannot Round-Trip

The attribute value is a parsed representation, not raw bytes. To re-encode, we would need to:
1. Parse the human-readable string
2. Reconstruct the original wire format

This is the opposite of what we want for generic attributes.

### Workaround

For attributes that need exact round-trip preservation, ensure they're stored as pure hex:
```json
"attribute-0x19-0xC0": "0x000C2A020B800000000100000000000000010000"
```

This format round-trips correctly using `attribute [0x19 0xc0 0x000C2A02...]`.

---

## 4. Pure Generic Attributes (RESOLVED)

**Status: ✅ Fixed in API v4**

Pure generic attributes with hex values now round-trip correctly:

| JSON Format | API Command | Round-Trip |
|-------------|-------------|------------|
| `"attribute-0x99-0x60": "0x00000064"` | `attribute [0x99 0x60 0x00000064]` | ✅ Works |
| `"attribute-0x19-0xC0": "redirect-to-nexthop-ietf ..."` | N/A | ❌ Partial decode |

The `attribute [...]` syntax is now supported for all family types:
- IPv4/IPv6 unicast routes
- FlowSpec routes
- MCAST-VPN routes
- MUP routes
- VPLS routes

---

## Summary Table

| Case | Information Lost | Wire Location | Status |
|------|------------------|---------------|--------|
| Interface-set transitive | Transitive/Non-transitive flag | EC type byte (0x07 vs 0x47) | ❌ v6 feature |
| Withdraw with attrs | All path attributes | Attribute section | ✅ RFC-correct normalization |
| Pure generic attrs | None | Path attribute list | ✅ Fixed in v4 |
| Partial-decode attrs | Original wire bytes | Path attribute list | ❌ Human-readable format |

---

## Implications

Most limitations are **by design** - the API command format is intended for human readability and common operations, not for lossless packet reproduction. For cases requiring exact packet reproduction, use the `raw:` hex format directly.

The test framework handles non-round-trippable cases by marking them with `# No cmd:` comments, which causes both the verification and round-trip tests to skip them.
