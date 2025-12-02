# Section Migration Plan

## Summary

The validator infrastructure is complete. This plan covers migrating configuration sections to use schema validators instead of redundant `known` dict entries.

## Completed Infrastructure
- `validator.py` - 733 lines, 18 validators, all 23 ValueTypes mapped
- `Leaf.get_validator()` and `LeafList.get_validator()` - auto-generates validators
- `Section.parse()` - uses schema validators as fallback
- `schema_to_json_schema()` - JSON Schema export working
- `tests/unit/test_configuration_validator.py` - 611 lines, 13 test classes
- CLI command `exabgp schema export` - working

---

## Migration Scope

**11 files with 117 entries** where `known` dict entries can be removed (schema validators handle them):

| File | Entries | Priority | Complexity |
|------|---------|----------|------------|
| `process/__init__.py` | 3 | Phase 1 | Easy |
| `announce/label.py` | 1 | Phase 1 | Easy |
| `announce/vpn.py` | 1 | Phase 1 | Easy |
| `neighbor/api.py` | 9 | Phase 1 | Easy (all BOOLEAN) |
| `capability.py` | 10 | Phase 2 | Medium |
| `operational/__init__.py` | 8 | Phase 2 | Medium |
| `neighbor/family.py` | 5 | Phase 2 | Medium (dynamic init) |
| `neighbor/nexthop.py` | 2 | Phase 2 | Medium (dynamic init) |
| `announce/ip.py` | 18 | Phase 3 | Complex |
| `l2vpn/vpls.py` | 21 | Phase 3 | Complex |
| `neighbor/__init__.py` | 25 | Phase 3 | Complex |

---

## Migration Pattern

### Before (current state):
```python
class ParseProcess(Section):
    schema = Container(children={
        'encoder': Leaf(type=ValueType.ENUMERATION, choices=['text', 'json'], ...),
        'respawn': Leaf(type=ValueType.BOOLEAN, ...),
        'run': Leaf(type=ValueType.STRING, ...),
    })

    known = {
        'encoder': encoder,      # redundant - schema can handle
        'respawn': boolean,      # redundant - schema can handle
        'run': run,              # redundant - schema can handle
    }
    action = {
        'encoder': 'set-command',
        'respawn': 'set-command',
        'run': 'set-command',
    }
```

### After (migrated):
```python
class ParseProcess(Section):
    schema = Container(children={
        'encoder': Leaf(type=ValueType.ENUMERATION, choices=['text', 'json'], action='set-command', ...),
        'respawn': Leaf(type=ValueType.BOOLEAN, action='set-command', ...),
        'run': Leaf(type=ValueType.STRING, action='set-command', ...),
    })

    known = {}   # Empty - all handled by schema
    action = {}  # Empty - derived from schema
```

---

## Implementation Phases

### Phase 1: Quick Wins (14 entries)

**Commit 1: process/__init__.py**
- Remove: encoder, respawn, run from `known`
- Types: ENUMERATION, BOOLEAN, STRING

**Commit 2: announce/label.py + announce/vpn.py**
- Remove: label, rd from `known`
- Types: LABEL, RD

**Commit 3: neighbor/api.py**
- Remove: parsed, packets, consolidate, open, update, notification, keepalive, refresh, operational from `known`
- Types: All BOOLEAN

### Phase 2: Medium Complexity (25 entries)

**Commit 4: capability.py**
- Remove: nexthop, asn4, multi-session, operational, route-refresh, aigp, extended-message, software-version, add-path from `known`
- Keep: graceful-restart (complex validation: max 4095, "disable" keyword)
- Types: BOOLEAN, ENUMERATION

**Commit 5: operational/__init__.py**
- Remove: asm, adm, rpcq, rpcp, apcq, apcp, lpcq, lpcp from `known`
- Types: All STRING with append-name action

**Commit 6: neighbor/family.py + neighbor/nexthop.py**
- Handle dynamic `known` construction in `__init__`
- Types: ENUMERATION, STRING

### Phase 3: Complex Sections (64 entries)

**Commit 7: announce/ip.py**
- Remove: origin, med, as-path, local-preference, atomic-aggregate, aggregator, etc. from `known`
- Keep entries with complex multi-token parsing
- Types: Various BGP attributes

**Commit 8: l2vpn/vpls.py**
- Remove: rd, endpoint, base, offset, size, origin, med, etc. from `known`
- Types: RD, INTEGER, BGP attributes

**Commit 9: neighbor/__init__.py**
- Remove: hold-time, rate-limit, listen, connect, passive, description, etc. from `known`
- Types: INTEGER, PORT, BOOLEAN, STRING, IP_ADDRESS, ASN

---

## Files to Modify

| Phase | File | Action |
|-------|------|--------|
| 1 | `src/exabgp/configuration/process/__init__.py` | Remove 3 known entries |
| 1 | `src/exabgp/configuration/announce/label.py` | Remove 1 known entry |
| 1 | `src/exabgp/configuration/announce/vpn.py` | Remove 1 known entry |
| 1 | `src/exabgp/configuration/neighbor/api.py` | Remove 9 known entries |
| 2 | `src/exabgp/configuration/capability.py` | Remove 9 known entries |
| 2 | `src/exabgp/configuration/operational/__init__.py` | Remove 8 known entries |
| 2 | `src/exabgp/configuration/neighbor/family.py` | Refactor dynamic known |
| 2 | `src/exabgp/configuration/neighbor/nexthop.py` | Refactor dynamic known |
| 3 | `src/exabgp/configuration/announce/ip.py` | Remove 18 known entries |
| 3 | `src/exabgp/configuration/l2vpn/vpls.py` | Remove 21 known entries |
| 3 | `src/exabgp/configuration/neighbor/__init__.py` | Remove 25 known entries |

---

## Validation

```bash
./qa/bin/test_everything  # Must pass after each commit
```

---

## Detailed Migration Per File

### Phase 1 Files

#### `process/__init__.py`
```
known entries to remove:
- 'encoder': encoder
- 'respawn': boolean
- 'run': run

Ensure schema has:
- encoder: Leaf(type=ValueType.ENUMERATION, choices=['text', 'json'], action='set-command')
- respawn: Leaf(type=ValueType.BOOLEAN, action='set-command')
- run: Leaf(type=ValueType.STRING, action='set-command')
```

#### `announce/label.py`
```
known entries to remove:
- 'label': label

Ensure schema has:
- label: Leaf(type=ValueType.LABEL, action='nlri-set')
```

#### `announce/vpn.py`
```
known entries to remove:
- 'rd': route_distinguisher

Ensure schema has:
- rd: Leaf(type=ValueType.RD, action='nlri-set')
```

#### `neighbor/api.py`
```
In ParseSend and ParseReceive classes:
known entries to remove:
- 'parsed': boolean
- 'packets': boolean
- 'consolidate': boolean
- 'open': boolean
- 'update': boolean
- 'notification': boolean
- 'keepalive': boolean
- 'refresh': boolean
- 'operational': boolean

All should be Leaf(type=ValueType.BOOLEAN, action='set-command')
```

### Phase 2 Files

#### `capability.py`
```
known entries to remove:
- 'nexthop': boolean
- 'asn4': boolean
- 'multi-session': boolean
- 'operational': boolean
- 'route-refresh': boolean
- 'aigp': boolean
- 'extended-message': boolean
- 'software-version': boolean
- 'add-path': add_path (ENUMERATION)

KEEP in known (complex validation):
- 'graceful-restart': graceful_restart (special "disable" handling, max 4095)
```

#### `operational/__init__.py`
```
known entries to remove:
- 'asm': asm
- 'adm': adm
- 'rpcq': rpcq
- 'rpcp': rpcp
- 'apcq': apcq
- 'apcp': apcp
- 'lpcq': lpcq
- 'lpcp': lpcp

All should be Leaf(type=ValueType.STRING, action='append-name')
```

#### `neighbor/family.py`
```
Dynamic known construction - refactor to use schema:
- 'ipv4': ENUMERATION with SAFI choices
- 'ipv6': ENUMERATION with SAFI choices
- 'l2vpn': ENUMERATION with SAFI choices
- 'bgp-ls': ENUMERATION with SAFI choices
- 'all': BOOLEAN
```

#### `neighbor/nexthop.py`
```
Dynamic known construction - refactor to use schema:
- 'ipv4': STRING (SAFI with alternate next-hop)
- 'ipv6': STRING (SAFI with alternate next-hop)
```

### Phase 3 Files

#### `announce/ip.py`
```
known entries to remove:
- 'origin': origin
- 'med': med
- 'local-preference': local_preference
- 'atomic-aggregate': atomic_aggregate
- 'aggregator': aggregator
- 'originator-id': originator_id
- 'cluster-list': cluster_list
- 'community': community
- 'large-community': large_community
- 'extended-community': extended_community
- 'aigp': aigp
- 'name': named
- 'split': split
- 'watchdog': watchdog
- 'withdraw': withdraw
- 'label': label
- 'attribute': attribute
- 'as-path': as_path (may need to keep - complex multi-token)
```

#### `l2vpn/vpls.py`
```
known entries to remove:
- 'rd': route_distinguisher
- 'endpoint': integer
- 'base': integer
- 'offset': integer
- 'size': integer
- Plus all BGP attribute entries inherited from announce
```

#### `neighbor/__init__.py`
```
known entries to remove:
- 'hold-time': ttl
- 'rate-limit': rate_limit
- 'incoming-ttl': incoming_ttl
- 'outgoing-ttl': outgoing_ttl
- 'passive': boolean
- 'listen': port
- 'connect': port
- 'auto-flush': boolean
- 'group-updates': boolean
- 'adj-rib-in': boolean
- 'adj-rib-out': boolean
- 'manual-eor': boolean
- 'md5-base64': boolean
- 'description': description
- 'host-name': host_name
- 'domain-name': domain_name
- 'source-interface': source_interface
- 'router-id': ip
- 'local-as': auto_asn
- 'peer-as': auto_asn
- 'local-address': ip
- 'peer-address': peer_ip

Type mappings:
- INTEGER: hold-time, rate-limit, incoming-ttl, outgoing-ttl
- BOOLEAN: passive, auto-flush, group-updates, adj-rib-in, adj-rib-out, manual-eor, md5-base64
- PORT: listen, connect
- STRING: description, host-name, domain-name, source-interface
- IP_ADDRESS: router-id, local-address
- ASN: local-as, peer-as (with auto)
- IP_RANGE: peer-address
```

---

## Success Criteria

1. All migrated entries removed from `known` dict
2. Schema provides validation (via `_validator_from_schema()`)
3. Action derived from schema (via `_action_from_schema()`)
4. All existing tests pass
5. Existing configuration files work unchanged
6. Code is cleaner with less duplication

---

## Notes

- **Keep complex parsers**: Entries like `graceful-restart`, `as-path` with multi-token parsing stay in `known`
- **Dynamic known**: Some sections build `known` in `__init__` - may need refactoring
- **Actions**: Ensure schema Leaf has correct `action` field before removing from `action` dict
- **Test after each commit**: Run `./qa/bin/test_everything` to validate

---

## Implementation Status

### Completed ✅

**Phase 1:**
- `process/__init__.py`: encoder, respawn migrated (kept `run` - returns list[str])
- `neighbor/api.py`: All 9 boolean entries migrated

**Phase 2 (Partial):**
- `capability.py`: 8 boolean entries migrated (kept `add-path` and `graceful-restart`)
- `schema.py`: Fixed `Leaf.get_validator()` to configure BooleanValidator defaults

### Cannot Migrate ❌

After implementation analysis, several sections in the plan cannot be migrated because their parsers return complex objects that schema validators cannot produce:

| File | Reason |
|------|--------|
| `operational/__init__.py` | Parsers return `Advisory`/`Query`/`Response` objects, NOT strings |
| `neighbor/family.py` | Parsers return `(AFI, SAFI)` tuples with state tracking (`_all`, `_seen`) |
| `neighbor/nexthop.py` | Parsers return `(AFI, SAFI, AFI)` tuples |
| `capability.py` `add-path` | Returns int (0,1,2,3), but ENUMERATION validator returns strings |
| `process/__init__.py` `run` | Returns `list[str]` and validates file existence |

### Migration Rule

**Only migrate entries where:**
1. Parser returns same type as schema validator (bool for BOOLEAN, str for STRING/ENUMERATION, int for INTEGER)
2. No complex object creation (AFI, SAFI, Advisory, etc.)
3. No state tracking or side effects

---

**Created:** 2025-12-02
**Updated:** 2025-12-02
**Status:** Phase 1+2 (partial) complete, Phase 3 pending review
