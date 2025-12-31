# ExaBGP Fix: ip-reachability-tlv format

## Issue

In BGP-LS Prefix NLRI JSON output, `ip-reachability-tlv` currently outputs the IP address without the prefix length, but RFC 7752 Section 3.2.3.2 specifies that TLV 265 (IP Reachability Information) contains both prefix-length and prefix-bytes.

## Current Behavior (incorrect)

```json
"ip-reachability-tlv": "10.134.2.88",
"ip-reach-prefix": "10.134.2.88/30"
```

## Expected Behavior (correct per RFC)

```json
"ip-reachability-tlv": "10.134.2.88/30",
"ip-reach-prefix": "10.134.2.88/30"
```

## Why

The TLV itself contains the prefix length as part of its structure. Showing `ip-reachability-tlv` without the prefix length discards information that is actually present in the TLV. Both fields should show the complete prefix in CIDR notation.

## Where to Fix

Search for where `ip-reachability-tlv` is set in the BGP-LS NLRI JSON formatting code. The fix is to include the prefix length (e.g., `/30`) when formatting this field, same as `ip-reach-prefix`.

Likely location: `src/exabgp/bgp/message/update/nlri/bgpls/` or similar BGP-LS NLRI handling code.

## Verification

After fix, decode this BGP-LS Prefix UPDATE and verify both fields show `/30`:

```
FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF0075020000005E900E003D40044704C0A8640200000300300200000000000002BC0100001A0200000400003E34020100040000000002030006010135000041010900051E0A86025840010100400206020100003E34801D0D04830004000000640492000100
```

Expected output should include:
```json
"ip-reachability-tlv": "10.134.2.88/30",
"ip-reach-prefix": "10.134.2.88/30"
```
