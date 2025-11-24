# Neighbor Selector Syntax

**Reference documentation for ExaBGP API neighbor selector grammar.**

---

## Grammar

```
<neighbor-selector> ::= "neighbor" <ip> [<qualifier>]*

<qualifier> ::= "local-ip" <ip>
              | "local-as" <asn>
              | "peer-as" <asn>
              | "router-id" <ip>
              | "family-allowed" <families>

<ip>  ::= <ipv4> | <ipv6>
<asn> ::= <number>
<families> ::= <family> | <family>/<family> | ...
```

**Special cases:**
- Wildcard: `neighbor *` matches all neighbors
- Multiple selectors: Separate with `,` (comma)
- Order: Qualifiers can appear in any order

---

## Neighbor Name Format

**Implementation:** `src/exabgp/bgp/neighbor.py:194-202`

Neighbor names use this canonical format:

```
neighbor <peer-address> local-ip <local-addr> local-as <local-as> peer-as <peer-as> router-id <router-id> family-allowed <session>
```

**Examples:**
```
neighbor 127.0.0.1 local-ip 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 family-allowed ipv4-unicast
neighbor 10.0.0.2 local-ip auto local-as 65000 peer-as 65002 router-id 2.2.2.2 family-allowed in-open
neighbor 2001:db8::1 local-ip 2001:db8::2 local-as 65000 peer-as 65003 router-id 3.3.3.3 family-allowed ipv4-unicast/ipv6-unicast
```

**Session field (family-allowed):**
- Multi-session enabled: Lists families as `<afi>-<safi>/<afi>-<safi>/...`
- Multi-session disabled: `in-open` (families negotiated in OPEN message)

---

## Matching Algorithm

**Implementation:** `src/exabgp/reactor/api/command/limit.py:64-85`

### Parsing (`extract_neighbors()`)

1. Extract `neighbor <ip>` (mandatory)
2. Parse qualifiers until non-qualifier keyword found
3. Recognized qualifier keys: `neighbor`, `local-ip`, `local-as`, `peer-as`, `router-id`, `family-allowed`
4. Stop parsing when unrecognized keyword encountered
5. Return list of selector components and remaining command

**Example parsing:**
```
Input:  "neighbor 127.0.0.1 local-as 65000 peer-as 65001 announce route 10.0.0.0/24"
Output: (["neighbor 127.0.0.1", "local-as 65000", "peer-as 65001"], "announce route 10.0.0.0/24")
```

### Matching (`match_neighbor()`)

For each selector component:
1. Check wildcard: `neighbor *` → match all
2. Build regex: `(^|\s)<component>($|\s|,)`
3. Search in neighbor name
4. ALL components must match (AND logic)

**Examples:**

| Selector | Neighbor Name | Match? |
|----------|--------------|--------|
| `neighbor 127.0.0.1` | `neighbor 127.0.0.1 local-ip 127.0.0.1 local-as 65000 peer-as 65001 router-id 1.2.3.4 family-allowed ipv4-unicast` | ✅ Yes |
| `neighbor 127.0.0.1 local-as 65000` | Same as above | ✅ Yes |
| `neighbor 127.0.0.1 local-as 65002` | Same as above | ❌ No (local-as doesn't match) |
| `neighbor *` | Any neighbor | ✅ Yes |
| `neighbor * peer-as 65001` | Same as above | ✅ Yes (wildcard + peer-as matches) |

### Multiple Selectors (`match_neighbors()`)

- Selectors separated by `,` use OR logic
- Each selector uses AND logic internally
- Returns list of all matching peer names

**Example:**
```
neighbor 127.0.0.1, neighbor 10.0.0.2 announce route 10.0.0.0/24
→ Matches both 127.0.0.1 AND 10.0.0.2 (OR logic between selectors)
```

---

## Usage in API Commands

### Existing Commands Using Selectors

**Implementation locations:**

1. **announce/withdraw** (`src/exabgp/reactor/api/command/announce.py`, `withdraw.py`)
   ```
   neighbor <selector> announce route 10.0.0.0/24 next-hop 192.168.1.1
   neighbor <selector> withdraw route 10.0.0.0/24
   ```

2. **show neighbor** (`src/exabgp/reactor/api/command/neighbor.py`)
   ```
   show neighbor <selector> [summary|extensive|configuration]
   ```

3. **teardown** (`src/exabgp/reactor/api/command/neighbor.py`)
   ```
   teardown <selector>
   ```

4. **adj-rib operations** (`src/exabgp/reactor/api/command/rib.py`)
   ```
   neighbor <selector> adj-rib in [json]
   neighbor <selector> adj-rib out [json]
   ```

### Pattern: All commands use `extract_neighbors()` + `match_neighbors()`

```python
from exabgp.reactor.api.command.limit import extract_neighbors, match_neighbors

descriptions, command = extract_neighbors(line)
peers = match_neighbors(reactor.peers(service), descriptions)
# ... operate on matched peers
```

---

## Syntax for neighbor create/delete

**Design decision:** Match existing selector syntax for consistency.

### neighbor create

```
neighbor <ip> [local-ip <ip>] [local-as <asn>] [peer-as <asn>] [router-id <ip>] [family-allowed <families>] create
```

**Required parameters:**
- `<ip>` - Peer address (mandatory)
- `local-as <asn>` - Local ASN (mandatory in command or defaults)
- `peer-as <asn>` - Peer ASN (mandatory in command or defaults)
- `router-id <ip>` - Router ID (mandatory in command or defaults)

**Optional parameters:**
- `local-ip <ip>` - Local address (defaults to auto-discovery)
- `family-allowed <families>` - Address families (defaults to `ipv4 unicast` only)

**Examples:**
```bash
# Minimal (requires defaults for ASNs and router-id)
neighbor 127.0.0.2 local-as 65001 peer-as 65002 router-id 2.2.2.2 create

# With local-ip
neighbor 10.0.0.2 local-ip 10.0.0.1 local-as 65001 peer-as 65002 router-id 2.2.2.2 create

# With families
neighbor 10.0.0.2 local-as 65001 peer-as 65002 router-id 2.2.2.2 family-allowed ipv4-unicast/ipv6-unicast create

# IPv6
neighbor 2001:db8::2 local-as 65001 peer-as 65002 router-id 2.2.2.2 family-allowed ipv6-unicast create
```

### neighbor delete

```
neighbor <selector> delete
```

**Full selector support** - Uses `extract_neighbors()` + `match_neighbors()`.

**Examples:**
```bash
# Delete specific peer
neighbor 127.0.0.2 delete

# Delete by peer-as
neighbor * peer-as 65002 delete

# Delete by local-as
neighbor * local-as 65001 delete

# Delete by selector combination
neighbor 10.0.0.2 peer-as 65002 delete

# Delete all (dangerous!)
neighbor * delete
```

---

## Implementation Notes

### Code Reuse

- ✅ Use `extract_neighbors()` for parsing (no duplication)
- ✅ Use `match_neighbors()` for peer matching (consistency)
- ✅ Follow same pattern as announce/withdraw commands

### Validation

For `neighbor create`:
1. Parse parameters from selector qualifiers
2. Validate required fields present
3. Validate types (IP addresses, ASN ranges)
4. Use `Neighbor.missing()` for completeness check

For `neighbor delete`:
1. Parse selector normally
2. Match against existing peers
3. Gracefully handle no matches (not an error)

### Edge Cases

- **Empty selector:** `neighbor delete` → Error (no IP specified)
- **No matches:** `neighbor 1.1.1.1 delete` → Success with 0 deleted
- **Wildcard:** `neighbor * delete` → Delete all peers
- **Duplicate create:** `neighbor 127.0.0.1 ... create` when exists → Error

---

## Testing

### Functional Tests

Existing tests using selectors:
- `qa/encoding/api-announce.*` - Route announcement with selectors
- `qa/encoding/api-withdraw.*` - Route withdrawal with selectors
- `qa/encoding/api-rib.*` - RIB operations with selectors

New test:
- `qa/encoding/api-peer-lifecycle.*` - Create peer, announce route, delete peer

### Unit Tests

Test coverage needed:
- Selector parsing (various combinations)
- Matching logic (wildcards, AND/OR logic)
- Edge cases (no matches, duplicates, etc.)

---

## CLI Review Findings

**All commands correctly implement neighbor selector:**

| Command | File | Uses extract_neighbors? | Uses match_neighbors? |
|---------|------|------------------------|---------------------|
| announce route | `announce.py` | ✅ Yes | ✅ Yes |
| withdraw route | `withdraw.py` | ✅ Yes | ✅ Yes |
| show neighbor | `neighbor.py` | ✅ Yes | ✅ Yes |
| teardown | `neighbor.py` | ✅ Yes | ✅ Yes |
| adj-rib in/out | `rib.py` | ✅ Yes | ✅ Yes |

**Consistency verified:** All commands follow same pattern.

---

**Last Updated:** 2025-11-24
**Implementation:** ExaBGP 5.0+
