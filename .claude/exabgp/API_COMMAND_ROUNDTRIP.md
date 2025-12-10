# API Command Round-Trip Testing

This document explains the API command encode/decode round-trip testing system.

---

## Overview

The round-trip test verifies that:
1. **raw→cmd→raw**: Decode wire format to API command, encode back to wire, compare bytes
2. **cmd→raw**: Verify API commands encode to expected wire format

**Current coverage:** 349/349 (100%)

---

## Test Commands

```bash
# Verify cmd: lines encode to raw: lines
./qa/bin/test_api_encode

# Round-trip test: raw→cmd→raw
./qa/bin/test_api_encode --self-check

# Generate cmd: from raw: (decode)
./qa/bin/test_api_encode --generate

# Write generated cmd: to files
./qa/bin/test_api_encode --generate --write

# Replace existing cmd: lines
./qa/bin/test_api_encode --generate --inline --write
```

---

## CI File Format

```
option:file:config.conf
option:asn:65000           # Optional: peer-as for eBGP tests
1:cmd:announce route 10.0.0.0/24 next-hop 1.2.3.4
1:raw:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:0030:02:...
# No cmd: reason for skip   # Skip marker for non-roundtrippable messages
2:raw:...                   # This raw line will be skipped
```

---

## Key Files

| File | Purpose |
|------|---------|
| `qa/bin/test_api_encode` | Main test script |
| `src/exabgp/configuration/command.py` | `decode_to_api_command()` + format helpers |
| `src/exabgp/reactor/api/command/group.py` | Group command handling |

---

## The `group` Command

The `group` command is essential for round-trip testing of complex messages:

### Multi-NLRI Batching
```
group announce ipv4 mcast-vpn source-ad ... ; announce ipv4 mcast-vpn shared-join ...
```

### Withdraw with Attributes
RFC 4271 says withdraws don't need attributes, but some implementations include them.
To reproduce byte-identical wire format:
```
group attributes origin igp local-preference 100 extended-community [...] ; withdraw ipv4 flow ...
```

### Attributes-Only UPDATE
```
attributes origin igp local-preference 100
```

---

## Supported Families

All families support round-trip testing:
- IPv4/IPv6 unicast
- IPv4/IPv6 mpls-vpn
- IPv4/IPv6 nlri-mpls
- FlowSpec (ipv4/ipv6 flow, flow-vpn)
- MCAST-VPN
- MUP (Mobile User Plane)
- VPLS

---

## Adding New Family Support

1. Add `format_<family>_announce()` function in `command.py`
2. Handle both announce and withdraw actions
3. Add `skip_attributes` parameter for `group` support
4. Update `decode_to_api_command()` to call the new formatter
5. Add encoder support in `test_api_encode`

---

## Common Issues

### Extended Community Parsing
Some extended communities can't be parsed back to their original format.
Use hex fallback:
```python
if 'value' in ec:
    ecomm_strs.append(f'0x{ec["value"]:016x}')
```

### Withdraw Detection
Check `has_extra_withdraw_attributes()` to detect when a withdraw needs `group`:
```python
extra_attrs = {'origin', 'as-path', 'local-preference', ...}
if extra_attrs.intersection(attributes.keys()):
    # Use 'group attributes ... ; withdraw ...'
```

---

## Related Documentation

- `.claude/exabgp/FLOWSPEC_ROUNDTRIP_LIMITATIONS.md` - Resolved limitations
- `plan/api-command-encoder.md` - Implementation plan and history
