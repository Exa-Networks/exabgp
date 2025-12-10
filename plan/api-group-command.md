# API Group Command for UPDATE Batching

**Status:** ✅ Completed
**Created:** 2025-12-10
**Target:** API v4 (backport-safe, enables round-trip testing)

## Goal

Add `group` command to batch multiple announcements into a single BGP UPDATE message. This enables:
- Exact wire-format reproduction for multi-NLRI UPDATEs
- Atomic updates (all-or-nothing)
- Reduced UPDATE count for bulk operations
- Control over when UPDATEs are sent vs buffered

## Syntax

### Single-line (implicit end at newline)

```
group announce ipv4 mcast-vpn shared-join rp 10.99.199.1 group 239.251.255.228 rd 65000:99999 source-as 65000 next-hop 10.10.6.3 extended-community [target:192.168.94.12:5] ; announce ipv4 mcast-vpn source-join source 10.99.12.2 group 239.251.255.228 rd 65000:99999 source-as 65000 next-hop 10.10.6.3 extended-community [target:192.168.94.12:5]
```

### Multi-line

```
group start
announce ipv4 mcast-vpn shared-join rp 10.99.199.1 group 239.251.255.228 rd 65000:99999 source-as 65000 next-hop 10.10.6.3 extended-community [target:192.168.94.12:5]
announce ipv4 mcast-vpn source-join source 10.99.12.2 group 239.251.255.228 rd 65000:99999 source-as 65000 next-hop 10.10.6.3 extended-community [target:192.168.94.12:5]
group end
```

## Semantics

1. Commands within a group are collected, not sent immediately
2. On `group end` (or newline for single-line):
   - Group by (family, next-hop, attributes)
   - Pack matching NLRIs into single UPDATE messages
   - Send UPDATE(s)
3. If attributes differ, multiple UPDATEs are produced
4. Withdraws can be grouped with announces (standard BGP UPDATE)

## Use Cases

### Multi-NLRI Round-Trip

Currently fails because decoder produces separate commands:
```
# Original: 1 UPDATE with 2 NLRIs
# Decoded: 2 separate commands → 2 UPDATEs
```

With group:
```
# Decoder generates:
group announce ... ; announce ...

# Encoder produces: 1 UPDATE with 2 NLRIs ✓
```

### Bulk Operations

```
group start
announce route 10.0.0.0/24 next-hop 1.2.3.4
announce route 10.0.1.0/24 next-hop 1.2.3.4
announce route 10.0.2.0/24 next-hop 1.2.3.4
# ... 1000 more routes
group end
# Produces minimal UPDATEs instead of 1000+
```

### Mixed Announce/Withdraw

```
group start
withdraw route 10.0.0.0/24
announce route 10.0.0.0/24 next-hop 5.6.7.8
group end
# Single UPDATE with both withdraw and announce sections
```

## Implementation

### Phase 1: API Command Parser

**File:** `src/exabgp/reactor/api/command/`

1. Add `group` command handler
2. Implement command buffering state
3. Handle `group start` / `group end` / single-line syntax

### Phase 2: Encoder Integration

**File:** `src/exabgp/reactor/api/` or encoder logic

1. Collect commands in buffer during group
2. On group end:
   - Parse all buffered commands
   - Group by compatible attributes
   - Build UPDATE(s) using `UpdateCollection`

### Phase 3: Decoder Integration

**File:** `qa/bin/test_api_encode`

1. Detect multi-NLRI UPDATEs in `decode_to_api_command()`
2. Generate `group ... ; ...` syntax for same next-hop NLRIs
3. Update round-trip tests

### Phase 4: Testing

1. Add test cases for group syntax
2. Update conf-mvpn.ci to use group syntax
3. Verify round-trip passes

## Files to Modify

| File | Change |
|------|--------|
| `src/exabgp/reactor/api/command/` | Add group command handler |
| `src/exabgp/reactor/api/` | Command buffering logic |
| `qa/bin/test_api_encode` | Generate group syntax for multi-NLRI |
| `qa/encoding/conf-mvpn.ci` | Update test expectations |

## Considerations

- Error handling: What if group contains incompatible commands?
- Timeout: Should there be a max time for group to complete?
- Nesting: Disallow `group start` inside a group
- Empty group: No-op or error?

## Progress

- [x] Phase 1: API command parser (`src/exabgp/reactor/api/command/group.py`)
- [x] Phase 2: Encoder integration (`qa/bin/test_api_encode` - `encode_group_command()`)
- [x] Phase 3: Decoder integration (`decode_to_api_command()` - MVPN multi-NLRI generates group syntax)
- [x] Phase 4: Testing (all 14 test suites pass, conf-mvpn.ci updated with group commands)

## Implementation Summary

### Files Created/Modified

| File | Change |
|------|--------|
| `src/exabgp/reactor/api/command/group.py` | New file - group command handlers (group_start, group_end, group_inline) |
| `src/exabgp/reactor/api/dispatch/v6.py` | Added group to dispatch tree |
| `src/exabgp/reactor/api/__init__.py` | Added group mode interception in process() |
| `qa/bin/test_api_encode` | Added encode_group_command(), updated decode_to_api_command() for MVPN |
| `qa/encoding/conf-mvpn.ci` | Updated to use group syntax for multi-NLRI tests |

### API Commands Added

- `group start` - Begin buffering commands
- `group end` - Process buffered commands as single UPDATE
- `group <cmd1> ; <cmd2> ; ...` - Single-line batched commands
- `peer * group <cmd1> ; <cmd2>` - Peer-targeted group command

## Related

- Resolves 2 skipped tests in `conf-mvpn.ci` (multi-NLRI batching)
- Could resolve similar issues in other families if they arise
