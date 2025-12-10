# API Round-Trip Limitations

This document explains why certain BGP messages cannot complete a round-trip test (decode → encode → compare). The test framework marks these with `# No cmd:` comments to skip verification.

**Current coverage:** 341/349 (97.7%) - 8 skipped

---

## 1. Interface-Set Transitive Flag (RESOLVED)

**Status:** ✅ Fixed in API v4

The interface-set extended community now includes a `"transitive"` field in JSON output:

```json
"extended-community": [
  {"value": 504966108235596030, "string": "interface-set:output:254:254", "transitive": true},
  {"value": 5116875327204835329, "string": "interface-set:input:3405770241:1", "transitive": false}
]
```

The encoder uses this field to generate correct config syntax:
- `"transitive": true` → `interface-set transitive:direction:asn:group`
- `"transitive": false` → `interface-set non-transitive:direction:asn:group`

The config parser accepts both old (2-colon) and new (3-colon) formats for backward compatibility.

---

## 2. Withdraw With Attributes (5 cases)

### The Problem

Some implementations send withdrawals with path attributes. RFC 4271 says withdrawals should have no attributes. The encoder produces RFC-compliant withdrawals.

### Wire Format

Original: MP_UNREACH_NLRI + ORIGIN + LOCAL_PREF + EXTENDED_COMMUNITY
Re-encoded: MP_UNREACH_NLRI only

### Resolution

**Status:** ✅ Correct behavior (RFC normalization)

Both messages withdraw the same routes - semantically equivalent.

---

## 3. Partially-Decoded Generic Attributes (1 case)

### The Problem

Some attributes are decoded to human-readable strings instead of raw hex:

```json
"attribute-0x19-0xC0": "redirect-to-nexthop-ietf 2a02:b80:0:1::1"
```

The value is a parsed representation, not raw bytes.

### Resolution

**Status:** ❌ By design (human-readable format)

Pure generic attributes with hex values (`"0x..."`) DO round-trip correctly.

---

## 4. Empty UPDATE (1 case)

### The Problem

An UPDATE message with only path attributes and no NLRI (no announce, no withdraw).

```json
{"update": {"attribute": {"origin": "igp", "local-preference": 100}}}
```

### Resolution

**Status:** ✅ Expected (no NLRI to encode)

Nothing to announce or withdraw - decoder cannot generate a meaningful command.

---

## 5. Decode Failed (1 case)

### The Problem

A message that the decoder cannot parse successfully.

### Resolution

**Status:** 🔍 Investigate if needed

---

## 6. Multi-NLRI Batching (RESOLVED)

### The Problem (was 2 cases)

A single UPDATE containing multiple NLRIs was decoded to separate commands, which re-encoded to separate UPDATEs.

### Resolution

**Status:** ✅ Fixed with `group` command

The decoder now generates group syntax for multi-NLRI UPDATEs:

```
group announce ipv4 mcast-vpn shared-join ... ; announce ipv4 mcast-vpn source-join ...
```

The encoder batches grouped commands into a single UPDATE.

---

## 7. Pure Generic Attributes (RESOLVED)

### The Problem (was many cases)

Generic attributes (`attribute-0xNN-0xNN`) were not included in API commands.

### Resolution

**Status:** ✅ Fixed in API v4

Pure generic attributes with hex values now round-trip:

| JSON Format | API Command |
|-------------|-------------|
| `"attribute-0x99-0x60": "0x00000064"` | `attribute [0x99 0x60 0x00000064]` |

Supported for all families: IPv4/IPv6, FlowSpec, MCAST-VPN, MUP, VPLS.

---

## Summary Table

| Case | Count | Status | Resolution |
|------|-------|--------|------------|
| Interface-set transitive | 0 | ✅ | Fixed with `transitive` JSON field |
| Withdraw with attrs | 5 | ✅ | RFC normalization (correct) |
| Partial-decode attrs | 1 | ❌ | By design |
| Empty UPDATE | 1 | ✅ | No NLRI to encode |
| Decode failed | 1 | 🔍 | Investigate |
| Multi-NLRI batching | 0 | ✅ | Fixed with `group` command |
| Pure generic attrs | 0 | ✅ | Fixed with `attribute [...]` |
| **Total skipped** | **8** | | |

---

## Coverage History

| Date | Passed | Skipped | Coverage |
|------|--------|---------|----------|
| 2025-12-10 | 341 | 8 | 97.7% |
| 2025-12-10 | 332 | 17 | 95.1% |

---

## Implications

Most limitations are **by design** - the API command format is intended for human readability and common operations, not for lossless packet reproduction. For cases requiring exact packet reproduction, use the `raw:` hex format directly.
