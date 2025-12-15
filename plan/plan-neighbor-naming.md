# Neighbor Naming

**Status:** 📋 Planning
**Created:** 2025-12-11
**Updated:** 2025-12-11

## Goal

Allow neighbors to have user-defined names (aliases) that can be used:
1. In configuration files (`name my-peer-1;`)
2. In API commands (`peer my-peer-1 announce route ...`)
3. Managed via API (`peer 10.0.0.1 name set my-peer-1`)

## Requirements

### Name Format
- Characters: `a-zA-Z0-9_-`
- Length: 1-64 characters
- Must be unique across all neighbors
- Optional (neighbors work without names as today)

### Configuration Syntax
```
neighbor 10.0.0.1 {
    name my-upstream;        # NEW: user-defined alias
    peer-as 65001;
    local-as 65000;
    ...
}
```

### API Usage

**Using name in selectors:**
```bash
# Instead of:
neighbor 10.0.0.1 announce route 192.168.0.0/24 next-hop self

# Can use:
peer my-upstream announce route 192.168.0.0/24 next-hop self

# Or with v6 bracket syntax:
peer [my-upstream, my-downstream] announce route ...
```

**Managing names via API:**
```bash
# Set/change name
peer 10.0.0.1 name set my-upstream

# Remove name
peer 10.0.0.1 name unset

# Show name
peer 10.0.0.1 name
peer my-upstream show
```

---

## Current Architecture

### Neighbor Identification

Currently neighbors are identified by a canonical name string:

```python
# src/exabgp/bgp/neighbor/neighbor.py:236-244
def name(self) -> str:
    session = '/'.join(f'{afi.name()}-{safi.name()}' for (afi, safi) in self.families())
    local_addr = 'auto' if self.session.auto_discovery else self.session.local_address
    return f'neighbor {self.session.peer_address} local-ip {local_addr} local-as {local_as} peer-as {peer_as} router-id {self.session.router_id} family-allowed {session}'
```

### Selector Matching

`src/exabgp/reactor/api/command/limit.py` handles neighbor selection:

```python
SELECTOR_KEYS = frozenset(['local-ip', 'local-as', 'peer-as', 'router-id', 'family-allowed'])

def match_neighbor(description: list[str], name: str) -> bool:
    # Matches against canonical name using regex
```

### Peer Registry

`Reactor.peers()` returns dict of `{canonical_name: Peer}`.

---

## Implementation Plan

### Phase 1: Add Name Field to Neighbor

**Files to modify:**

| File | Change |
|------|--------|
| `src/exabgp/bgp/neighbor/neighbor.py` | Add `alias: str` field |
| `src/exabgp/bgp/neighbor/settings.py` | Add `alias` to NeighborSettings |
| `src/exabgp/configuration/neighbor/__init__.py` | Add `name` to schema |
| `src/exabgp/configuration/neighbor/parser.py` | Add name validation |

**Neighbor class changes:**

```python
class Neighbor:
    # Existing fields...
    alias: str  # User-defined name (empty string = no alias)

    def __init__(self) -> None:
        # ...
        self.alias = ''

    def display_name(self) -> str:
        """Return alias if set, otherwise peer IP."""
        if self.alias:
            return self.alias
        return str(self.session.peer_address)
```

**Schema addition:**

```python
'name': Leaf(
    type=ValueType.STRING,
    description='User-defined neighbor name/alias',
    action='set-command',
    # Validation: a-zA-Z0-9_- only, 1-64 chars
),
```

### Phase 2: Name Registry and Lookup

**Files to modify:**

| File | Change |
|------|--------|
| `src/exabgp/reactor/loop.py` | Add name→peer lookup |
| `src/exabgp/configuration/configuration.py` | Validate name uniqueness |

**Reactor additions:**

```python
class Reactor:
    # Add name registry
    _peer_names: dict[str, str]  # alias → canonical_name

    def register_peer_name(self, alias: str, canonical: str) -> None:
        """Register alias for a peer."""
        if alias in self._peer_names:
            raise ValueError(f"Name '{alias}' already in use")
        self._peer_names[alias] = canonical

    def unregister_peer_name(self, alias: str) -> None:
        """Remove alias registration."""
        self._peer_names.pop(alias, None)

    def resolve_peer_name(self, name: str) -> str | None:
        """Resolve alias to canonical name, or return None if not found."""
        return self._peer_names.get(name)

    def peer_by_name(self, name: str) -> Peer | None:
        """Get peer by alias or canonical name."""
        # Try alias first
        canonical = self._peer_names.get(name)
        if canonical:
            return self._peers.get(canonical)
        # Fall back to canonical name lookup
        return self._peers.get(name)
```

### Phase 3: Update Selector Matching

**Files to modify:**

| File | Change |
|------|--------|
| `src/exabgp/reactor/api/command/limit.py` | Support name in selectors |

**Changes to `extract_neighbors()`:**

```python
# Add 'name' to selector keys
SELECTOR_KEYS = frozenset(['local-ip', 'local-as', 'peer-as', 'router-id', 'family-allowed', 'name'])

def _parse_single_selector(sel_str: str) -> list[str]:
    words = sel_str.split()
    if not words:
        return []

    first = words[0]

    # Check if first word is a name (not IP, not wildcard)
    if first != '*' and not _is_ip_address(first):
        # Assume it's a name - return as name selector
        return [f'name {first}']

    # Existing IP-based parsing...
```

**Changes to `match_neighbor()`:**

Add name matching:

```python
def match_neighbor(description: list[str], name: str, alias: str = '') -> bool:
    for string in description:
        stripped = string.strip()

        # Wildcard matches all
        if stripped in ('neighbor *', 'peer *'):
            return True

        # Name/alias matching (exact match)
        if stripped.startswith('name '):
            requested_name = stripped[5:].strip()
            if alias and alias == requested_name:
                return True
            # No alias match - check if requested name is in canonical name
            # (this allows partial IP matching to still work)
            if requested_name not in name:
                return False
            continue

        # Existing regex matching for canonical name components
        pattern = rf'(^|\s){re.escape(string)}($|\s|,)'
        if re.search(pattern, name) is None:
            return False

    return True
```

### Phase 4: API Commands for Name Management

**Files to modify:**

| File | Change |
|------|--------|
| `src/exabgp/reactor/api/command/peer.py` | Add name commands |
| `src/exabgp/reactor/api/command/registry.py` | Register name commands |

**New commands:**

```python
# peer <selector> name
# peer <selector> name set <name>
# peer <selector> name unset

def peer_name(
    self: 'API', reactor: 'Reactor', service: str, peers: list[str], command: str, use_json: bool
) -> bool:
    """Get or set peer name/alias."""
    words = command.split()

    if not words:
        # Show current name
        for peer_key in peers:
            neighbor = reactor.neighbor(peer_key)
            if neighbor:
                name = neighbor.alias or '(none)'
                reactor.processes.write(service, f'{peer_key}: {name}')
        reactor.processes.answer_done(service)
        return True

    if words[0] == 'set' and len(words) >= 2:
        new_name = words[1]
        # Validate name format
        if not _is_valid_name(new_name):
            reactor.processes.answer_error(service, f"Invalid name: {new_name}")
            return False

        for peer_key in peers:
            neighbor = reactor.neighbor(peer_key)
            if neighbor:
                # Unregister old name if exists
                if neighbor.alias:
                    reactor.unregister_peer_name(neighbor.alias)
                # Set new name
                neighbor.alias = new_name
                reactor.register_peer_name(new_name, peer_key)
        reactor.processes.answer_done(service)
        return True

    if words[0] == 'unset':
        for peer_key in peers:
            neighbor = reactor.neighbor(peer_key)
            if neighbor and neighbor.alias:
                reactor.unregister_peer_name(neighbor.alias)
                neighbor.alias = ''
        reactor.processes.answer_done(service)
        return True

    reactor.processes.answer_error(service, 'usage: peer <selector> name [set <name>|unset]')
    return False


def _is_valid_name(name: str) -> bool:
    """Validate name format: a-zA-Z0-9_- only, 1-64 chars."""
    if not name or len(name) > 64:
        return False
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))
```

### Phase 5: Include Name in JSON Output

**Files to modify:**

| File | Change |
|------|--------|
| `src/exabgp/bgp/neighbor/neighbor.py` | Add alias to JSON output |
| `src/exabgp/reactor/api/command/neighbor.py` | Include name in show output |

**JSON output:**

```json
{
    "peer-address": "10.0.0.1",
    "name": "my-upstream",
    "peer-as": 65001,
    "local-as": 65000,
    "state": "established"
}
```

### Phase 6: Configuration Persistence (Optional)

If name changes via API should persist:

**Option A: Runtime only** (simpler)
- Names set via API lost on restart
- Configuration file is source of truth

**Option B: Persist to state file**
- Save name→peer mappings to state file
- Load on startup after config

**Recommendation:** Start with Option A, add persistence later if needed.

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/bgp/neighbor/test_neighbor_alias.py

def test_neighbor_alias_default_empty():
    n = Neighbor()
    assert n.alias == ''

def test_neighbor_display_name_without_alias():
    n = Neighbor()
    n.session.peer_address = IP.from_string('10.0.0.1')
    assert n.display_name() == '10.0.0.1'

def test_neighbor_display_name_with_alias():
    n = Neighbor()
    n.alias = 'my-peer'
    assert n.display_name() == 'my-peer'

def test_alias_validation():
    assert _is_valid_name('my-peer-1') == True
    assert _is_valid_name('MY_PEER') == True
    assert _is_valid_name('peer.name') == False  # dot not allowed
    assert _is_valid_name('peer name') == False  # space not allowed
    assert _is_valid_name('') == False
    assert _is_valid_name('a' * 65) == False  # too long
```

### Functional Tests

```
# qa/encoding/api-peer-name.ci

# Test name in config
neighbor 127.0.0.1 {
    name test-peer;
    peer-as 65001;
    local-as 65000;
    router-id 1.1.1.1;
}

# Test API commands
peer test-peer announce route 10.0.0.0/24 next-hop self;
peer test-peer name;
peer 127.0.0.1 name set new-name;
peer new-name show;
peer new-name name unset;
```

---

## Migration / Backward Compatibility

- **No breaking changes** - existing configs work without `name`
- **Existing selectors work** - IP-based selection unchanged
- **New feature is additive** - names are optional

---

## Open Questions

### Q1: Should names be case-sensitive?

- (a) Yes - `MyPeer` and `mypeer` are different
- (b) No - normalize to lowercase

**Recommendation:** (b) Normalize to lowercase for consistency.

### Q2: What happens if name conflicts with IP address format?

Example: user names a peer `127.0.0.1` (same as another peer's IP)

- (a) Allow it - name lookup takes priority
- (b) Reject names that look like IPs
- (c) Require names to start with letter

**Recommendation:** (c) Require names to start with a letter (`^[a-zA-Z][a-zA-Z0-9_-]*$`)

### Q3: Should name appear in canonical `name()` output?

Current: `neighbor 10.0.0.1 local-ip auto local-as 65000 ...`
With name: `neighbor 10.0.0.1 name my-peer local-ip auto local-as 65000 ...`

- (a) Yes - include in canonical name
- (b) No - keep canonical name unchanged, alias is separate

**Recommendation:** (b) Keep canonical name unchanged for backward compatibility.

---

## Success Criteria

- [ ] `name my-peer;` works in neighbor config
- [ ] `peer my-peer announce route ...` works
- [ ] `peer 10.0.0.1 name set foo` works
- [ ] `peer foo name unset` works
- [ ] Names are unique (error on duplicate)
- [ ] JSON output includes `name` field
- [ ] All existing tests pass
- [ ] New unit + functional tests pass

---

## Files Summary

| File | Phase | Change |
|------|-------|--------|
| `src/exabgp/bgp/neighbor/neighbor.py` | 1, 5 | Add alias field, JSON output |
| `src/exabgp/bgp/neighbor/settings.py` | 1 | Add alias to settings |
| `src/exabgp/configuration/neighbor/__init__.py` | 1 | Add name to schema |
| `src/exabgp/configuration/neighbor/parser.py` | 1 | Add name validation |
| `src/exabgp/reactor/loop.py` | 2 | Add name registry |
| `src/exabgp/configuration/configuration.py` | 2 | Validate uniqueness |
| `src/exabgp/reactor/api/command/limit.py` | 3 | Support name selectors |
| `src/exabgp/reactor/api/command/peer.py` | 4 | Add name commands |
| `src/exabgp/reactor/api/command/registry.py` | 4 | Register commands |
| `src/exabgp/reactor/api/command/neighbor.py` | 5 | Include name in show |

---

**Dependencies:** None
**Blocked by:** None
**Blocks:** None
