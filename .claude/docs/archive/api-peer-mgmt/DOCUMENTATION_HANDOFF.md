# Documentation Handoff: Dynamic Peer Management API

**Date:** 2025-11-23
**Feature:** Dynamic BGP peer creation and deletion via API
**Status:** Implementation complete, needs user-facing documentation

---

## Overview for Documentation Team

Two new API commands have been implemented that allow ExaBGP users to create and delete BGP neighbors dynamically at runtime without modifying configuration files:

1. **`neighbor ... create`** - Creates a new BGP peer dynamically
2. **`neighbor ... delete`** - Deletes existing BGP peer(s) using selector syntax

---

## What Needs Documentation

### 1. User Guide / API Reference

**Location to update:** User-facing API documentation (wherever ExaBGP documents API commands)

**New commands to document:**

#### neighbor create

**Purpose:** Create a BGP neighbor dynamically at runtime without configuration file

**Syntax:**
```
neighbor <ip> local-ip <ip> local-as <asn> peer-as <asn> router-id <ip> [family-allowed <families>] create
```

**Required parameters:**
- Peer address (the `<ip>` after `neighbor` keyword)
- `local-ip <ip>` - Local IP address to bind to
- `local-as <asn>` - Local autonomous system number
- `peer-as <asn>` - Peer autonomous system number
- `router-id <ip>` - BGP router ID (must be IPv4 address format)

**Optional parameters:**
- `family-allowed <families>` - Address families (defaults to `ipv4-unicast` only)
  - Format: Single family or slash-separated list
  - Examples: `ipv4-unicast`, `ipv4-unicast/ipv6-unicast`, `ipv4-unicast/ipv6-unicast/vpnv4`

**Examples:**
```bash
# Minimal - IPv4 unicast only
neighbor 192.0.2.1 local-ip 192.0.2.254 local-as 65001 peer-as 65002 router-id 192.0.2.254 create

# With different local and peer IPs
neighbor 192.0.2.1 local-ip 192.0.2.254 local-as 65001 peer-as 65002 router-id 192.0.2.254 create

# With multiple address families
neighbor 192.0.2.1 local-ip 192.0.2.254 local-as 65001 peer-as 65002 router-id 192.0.2.254 family-allowed ipv4-unicast/ipv6-unicast create

# IPv6 peer
neighbor 2001:db8::1 local-ip 2001:db8::2 local-as 65001 peer-as 65002 router-id 192.0.2.254 family-allowed ipv6-unicast create
```

**Behavior:**
- Creates a new BGP neighbor and initiates session establishment
- Peer is "dynamic" (ephemeral) - will be lost if ExaBGP reloads configuration
- Returns error if peer already exists
- Returns error if required parameters missing
- Returns success when peer created (session may still be establishing)

**Use cases:**
- Automated peer provisioning systems
- Dynamic BGP setups where peers come and go
- Testing and development environments
- SDN/automation integrations

#### neighbor delete

**Purpose:** Delete BGP neighbor(s) dynamically at runtime

**Syntax:**
```
neighbor <selector> delete
```

**Selector syntax:** Same as used for `announce`, `withdraw`, `teardown` commands
- By IP: `neighbor <ip> delete`
- By ASN: `neighbor * peer-as <asn> delete`
- By multiple criteria: `neighbor <ip> local-as <asn> peer-as <asn> delete`
- All peers: `neighbor * delete`

**Examples:**
```bash
# Delete specific peer by IP
neighbor 192.0.2.1 delete

# Delete all peers with specific peer-as
neighbor * peer-as 65002 delete

# Delete by multiple criteria
neighbor 192.0.2.1 local-as 65001 peer-as 65002 delete

# Delete all peers (use with caution!)
neighbor * delete
```

**Behavior:**
- Gracefully shuts down matched BGP session(s) (sends NOTIFICATION)
- Removes peer(s) from ExaBGP's internal state
- Returns error if no peers match the selector
- Can delete both static (configured) and dynamic peers

**Warning:** Deleting static (configured) peers may cause issues on configuration reload. Primarily intended for dynamic peers created via `neighbor create`.

---

### 2. Important Notes for Documentation

**Design characteristics:**

1. **Ephemeral by design:** Dynamically created peers are NOT saved to configuration and are lost when ExaBGP reloads. This is intentional to maintain clear separation between static configuration and runtime state.

2. **Default family:** Unlike static neighbors (which default to all known families), dynamic peers default to **IPv4 unicast only**. Users must explicitly specify `family-allowed` for other address families.

3. **Selector syntax consistency:** The `neighbor delete` command uses the same selector syntax as `announce`, `withdraw`, and `teardown` commands. Reference existing selector documentation.

4. **Error on no matches:** The `delete` command returns an error (not success) if no peers match the selector. This helps catch typos and mistakes.

---

### 3. Reference Documentation

**For documentation writers to review:**

1. **`.claude/api/PEER_MANAGEMENT_IMPLEMENTATION.md`** - Complete implementation details
   - Full command syntax
   - All parameters explained
   - Design decisions
   - Examples
   - Known limitations

2. **`.claude/api/NEIGHBOR_SELECTOR_SYNTAX.md`** - Neighbor selector grammar
   - Complete selector syntax reference
   - Matching algorithm
   - Examples across all commands
   - Should be referenced for selector syntax explanation

3. **`src/exabgp/reactor/api/command/peer.py`** - Source code
   - Lines 201-256: `neighbor_create()` function with docstring
   - Lines 260-316: `neighbor_delete()` function with docstring
   - Helper functions with detailed parameter parsing

4. **`tests/unit/reactor/api/command/test_peer.py`** - Unit tests
   - 29 tests showing all valid usage patterns
   - Edge cases and error conditions
   - Can be used as examples

---

### 4. Documentation Structure Suggestions

**Recommended sections:**

```
# API Commands Reference

## Peer Management

### Creating Peers Dynamically

The `neighbor create` command allows...

**Syntax:**
[syntax block]

**Parameters:**
[parameter table]

**Examples:**
[examples with explanations]

**Common Errors:**
- Missing required parameter → Error message shown
- Duplicate peer → Error message shown
- Invalid IP/ASN format → Error message shown

### Deleting Peers Dynamically

The `neighbor delete` command allows...

**Syntax:**
[syntax block]

**Selector Syntax:**
[link to selector documentation or inline explanation]

**Examples:**
[examples with explanations]

**Safety Notes:**
- Always verify selector before deletion
- Error if no matches (prevents accidents)
- Can delete static peers (use with caution)

### Integration Example

[Full workflow showing create, announce routes, delete]

```bash
# Create peer
neighbor 192.0.2.1 local-as 65001 peer-as 65002 router-id 192.0.2.254 create

# Wait for establishment, then announce routes
neighbor 192.0.2.1 announce route 10.0.0.0/24 next-hop 192.0.2.254

# Later, remove peer
neighbor 192.0.2.1 delete
```
```

---

### 5. Comparison with Existing Commands

**For context in documentation:**

These commands follow the same pattern as existing API commands:

| Aspect | Existing (`announce route`) | New (`neighbor create`) |
|--------|----------------------------|------------------------|
| Selector syntax | `neighbor <selector> announce...` | `neighbor <selector> create` |
| Parameter parsing | Reuses `extract_neighbors()` | Reuses `extract_neighbors()` |
| Error handling | Returns error on invalid | Returns error on invalid |
| JSON support | Yes | Yes |
| Async support | Yes | Yes |

**Key difference:** `neighbor create` **requires** parameters (IP, ASNs, router-id), while `announce` operates on **existing** neighbors.

---

### 6. FAQ / Common Questions

**Suggested FAQ entries for documentation:**

**Q: Are dynamically created peers saved to the configuration file?**
A: No. Dynamic peers are ephemeral and lost when ExaBGP reloads its configuration. This is by design to maintain separation between static configuration and runtime state.

**Q: What happens if I create a peer that already exists in the configuration?**
A: You'll receive an error: "peer already exists: [neighbor details]"

**Q: Can I create a peer without specifying families?**
A: Yes. The default is IPv4 unicast only. This differs from static neighbors which default to all known families.

**Q: How do I specify multiple address families?**
A: Use slash-separated format: `family-allowed ipv4-unicast/ipv6-unicast`

**Q: Can I delete static (configured) peers?**
A: Technically yes, but not recommended. The `delete` command works on all peers, but deleting static peers may cause issues on configuration reload.

**Q: What happens if I try to delete a peer that doesn't exist?**
A: You'll receive an error: "no neighbors match the selector"

**Q: Can I create multiple peers at once?**
A: No. Use separate `create` commands for each peer.

**Q: Can I delete multiple peers at once?**
A: Yes. Use selector syntax: `neighbor * peer-as 65002 delete` deletes all peers with peer-as 65002.

**Q: How do I know if the peer created successfully?**
A: The command returns success immediately after creating the peer object. BGP session establishment happens asynchronously. Use `show neighbor` to check session state.

---

### 7. Migration Notes

**For users upgrading:**

No breaking changes. These are new commands that don't affect existing functionality.

**New capability:** Previously, all BGP neighbors had to be defined in configuration files. Now, peers can be created and deleted via API for dynamic environments.

---

### 8. Related Documentation to Update

**Cross-references needed:**

1. **API Commands Overview** - Add `neighbor create` and `neighbor delete` to command list
2. **Neighbor Selector Syntax** - Ensure delete command included in selector examples
3. **Getting Started / Quickstart** - Consider adding dynamic peer example
4. **Automation / SDN Integration** - Highlight this as a key automation feature
5. **Troubleshooting** - Add common errors and solutions
6. **Configuration Reference** - Note that dynamic peers are NOT in config file

---

### 9. Code Examples for Documentation

**Python API example:**
```python
import subprocess

def create_bgp_peer(ip, local_as, peer_as, router_id):
    """Create a BGP peer via ExaBGP API."""
    cmd = f"neighbor {ip} local-as {local_as} peer-as {peer_as} router-id {router_id} create"
    # Send to ExaBGP API (via named pipe, stdin, etc.)
    send_to_exabgp_api(cmd)

def delete_bgp_peer(ip):
    """Delete a BGP peer via ExaBGP API."""
    cmd = f"neighbor {ip} delete"
    send_to_exabgp_api(cmd)

# Usage
create_bgp_peer("192.0.2.1", 65001, 65002, "192.0.2.254")
# ... later ...
delete_bgp_peer("192.0.2.1")
```

**Shell script example:**
```bash
#!/bin/bash
# Send commands to ExaBGP via named pipe

EXABGP_PIPE="/run/exabgp.cmd"

# Create peer
echo "neighbor 192.0.2.1 local-as 65001 peer-as 65002 router-id 192.0.2.254 create" > $EXABGP_PIPE

# Wait for establishment
sleep 2

# Announce route
echo "neighbor 192.0.2.1 announce route 10.0.0.0/24 next-hop 192.0.2.254" > $EXABGP_PIPE

# Later, delete peer
echo "neighbor 192.0.2.1 delete" > $EXABGP_PIPE
```

---

### 10. Visual Diagram Suggestion

**For documentation visuals:**

```
┌─────────────────────────────────────────────────┐
│  Static Configuration (exabgp.conf)             │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Neighbor A   │  │ Neighbor B   │            │
│  │ 192.0.2.1    │  │ 192.0.2.2    │            │
│  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────┘
                      │
                      ▼
           ┌─────────────────────┐
           │   ExaBGP Runtime    │
           │                     │
           │  Static Peers:      │
           │  • 192.0.2.1 ✓      │
           │  • 192.0.2.2 ✓      │
           │                     │
           │  Dynamic Peers:     │  ◄── API: neighbor ... create
           │  • 192.0.2.3 ✓      │  ◄── API: neighbor ... delete
           │  • 192.0.2.4 ✓      │
           └─────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │ BGP Sessions │
              └──────────────┘
```

---

### 11. Version/Changelog Entry

**For changelog/release notes:**

```
### New Features

**Dynamic Peer Management API**

ExaBGP now supports creating and deleting BGP neighbors dynamically at runtime via new API commands:

- `neighbor ... create` - Create BGP peers without configuration files
- `neighbor ... delete` - Remove BGP peers using selector syntax

This enables:
- Automated peer provisioning
- Dynamic BGP configurations
- Better integration with SDN/automation platforms
- Easier testing and development workflows

Dynamic peers are ephemeral (not saved to configuration) by design.

See documentation for complete syntax and examples.
```

---

### 12. Contact for Technical Questions

**Implementation author:** Claude (session 2025-11-23)

**Key implementation files:**
- `src/exabgp/reactor/api/command/peer.py` - Main implementation
- `.claude/api/PEER_MANAGEMENT_IMPLEMENTATION.md` - Complete technical documentation
- `.claude/api/NEIGHBOR_SELECTOR_SYNTAX.md` - Selector syntax reference

**Test coverage:**
- 29 unit tests in `tests/unit/reactor/api/command/test_peer.py`
- All tests passing, no regressions

---

## Summary Checklist for Documentation Team

- [ ] Add `neighbor create` to API command reference
- [ ] Add `neighbor delete` to API command reference
- [ ] Document all parameters with types and defaults
- [ ] Add comprehensive examples for both commands
- [ ] Add integration workflow example (create → announce → delete)
- [ ] Add FAQ section answering common questions
- [ ] Cross-reference neighbor selector syntax documentation
- [ ] Add to API commands overview/index
- [ ] Add to automation/SDN integration guides
- [ ] Update changelog/release notes
- [ ] Add troubleshooting section for common errors
- [ ] Consider adding visual diagrams (static vs dynamic peers)
- [ ] Add code examples (Python, Shell)
- [ ] Note differences from static neighbor configuration
- [ ] Highlight ephemeral nature of dynamic peers

---

**Ready for documentation integration!**
