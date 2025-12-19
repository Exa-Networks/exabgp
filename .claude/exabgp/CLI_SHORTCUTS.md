# CLI Shortcuts Reference

Complete reference for ExaBGP CLI command shortcuts and context-aware expansion.

**See also:**
- `CLI_COMMANDS.md` - Complete command reference
- `CLI_IMPLEMENTATION.md` - Internal architecture
- `UNIX_SOCKET_API.md` - Unix socket API protocol

---

## Overview

The CLI supports context-aware shortcuts that expand to full commands based on:
- **Position in command** - First token, middle token, last token
- **Previous tokens** - What words came before
- **Command structure** - Where in the command tree you are

**Key principle:** Same letter can expand to different words depending on context.

**Implementation:** `src/exabgp/application/shortcuts.py`

---

## Single-Letter Shortcuts

### Context-Dependent Shortcuts

| Shortcut | Expands To | Context Rule | Examples |
|----------|-----------|--------------|----------|
| `a` | `announce` | First token OR after IP | `a route ...` → `announce route ...`<br>`n 10.0.0.1 a ...` → `neighbor 10.0.0.1 announce ...` |
| `a` | `attributes` | After `announce` or `withdraw` | `announce a ...` → `announce attributes ...`<br>`withdraw a ...` → `withdraw attributes ...` |
| `a` | `adj-rib` | After `clear`, `flush`, or `show` | `show a in` → `show adj-rib in`<br>`flush a out` → `flush adj-rib out` |
| `c` | `configuration` | Always | `show neighbor c` → `show neighbor configuration` |
| `e` | `eor` | After `announce` | `announce e ipv4 unicast` → `announce eor ipv4 unicast` |
| `e` | `extensive` | If `show` in tokens | `show neighbor e` → `show neighbor extensive` |
| `f` | `flow` | After `announce` or `withdraw` | `announce f ...` → `announce flow ...` |
| `f` | `flush` | First token OR after IP | `f adj-rib out` → `flush adj-rib out` |
| `h` | `help` | First token only | `h` → `help` |
| `i` | `in` | After `adj-rib` | `show adj-rib i` → `show adj-rib in` |
| `n` | `neighbor` | First token only | `n 10.0.0.1 show` → `neighbor 10.0.0.1 show` |
| `o` | `operational` | After `announce` | `announce o ...` → `announce operational ...` |
| `o` | `out` | After `adj-rib` | `show adj-rib o` → `show adj-rib out` |
| `r` | `route` | After `announce` or `withdraw` | `announce r 10.0.0.0/24 ...` → `announce route 10.0.0.0/24 ...` |
| `r` | `route-refresh` | After `announce route` | `announce r r ipv4 unicast` → `announce route route-refresh ipv4 unicast`<br>**Note:** Usually `announce route-refresh` directly |
| `s` | `show` | First token only | `s neighbor` → `show neighbor` |
| `s` | `summary` | NOT first token | `show neighbor s` → `show neighbor summary` |
| `t` | `teardown` | First token OR after IP | `t neighbor 10.0.0.1` → `teardown neighbor 10.0.0.1` |
| `v` | `vpls` | After `announce` or `withdraw` | `announce v ...` → `announce vpls ...` |
| `w` | `withdraw` | First token OR after IP | `w route 10.0.0.0/24` → `withdraw route 10.0.0.0/24` |
| `w` | `watchdog` | After `announce` or `withdraw` | `announce w myapp` → `announce watchdog myapp` |

---

## Multi-Letter Shortcuts

| Shortcut | Expands To | Context Rule | Notes |
|----------|-----------|--------------|-------|
| `id` | `router-id` | In neighbor context only | `show neighbor id 1.1.1.1` → `show neighbor router-id 1.1.1.1` |
| `neighbour` | `neighbor` | Always | Common UK spelling |
| `neigbour` | `neighbor` | Always | Common typo |
| `neigbor` | `neighbor` | Always | Common typo |

---

## Shortcut Examples by Category

### Control Commands

```bash
h                    → help
```

### Neighbor Commands

```bash
s n                  → show neighbor
s n s                → show neighbor summary
s n e                → show neighbor extensive
s n c                → show neighbor configuration

n 10.0.0.1 s         → neighbor 10.0.0.1 show
                       (transforms to: show neighbor 10.0.0.1)

n 10.0.0.1 s e       → neighbor 10.0.0.1 show extensive
                       (transforms to: show neighbor 10.0.0.1 extensive)

t n 10.0.0.1         → teardown neighbor 10.0.0.1
```

### Route Announcements

```bash
# To all neighbors
a r 10.0.0.0/24 next-hop 1.1.1.1
  → announce route 10.0.0.0/24 next-hop 1.1.1.1

# To specific neighbor (neighbor-first)
n 192.168.1.1 a r 10.0.0.0/24 next-hop self
  → neighbor 192.168.1.1 announce route 10.0.0.0/24 next-hop self

# EOR
a e ipv4 unicast     → announce eor ipv4 unicast

# EOR to specific neighbor
n 192.168.1.1 a e ipv4 unicast
  → neighbor 192.168.1.1 announce eor ipv4 unicast

# Route refresh
a route-refresh ipv4 unicast
  → announce route-refresh ipv4 unicast
```

### Route Withdrawals

```bash
# From all neighbors
w r 10.0.0.0/24      → withdraw route 10.0.0.0/24

# From specific neighbor
n 192.168.1.1 w r 10.0.0.0/24
  → neighbor 192.168.1.1 withdraw route 10.0.0.0/24
```

### FlowSpec

```bash
a f route destination 10.0.0.0/24 then discard
  → announce flow route destination 10.0.0.0/24 then discard

w f route destination 10.0.0.0/24
  → withdraw flow route destination 10.0.0.0/24
```

### VPLS

```bash
a v endpoint 10 offset 20 size 8
  → announce vpls endpoint 10 offset 20 size 8
```

### Attributes

```bash
a a next-hop 1.1.1.1
  → announce attributes next-hop 1.1.1.1

w a next-hop 1.1.1.1
  → withdraw attributes next-hop 1.1.1.1
```

### Adj-RIB Operations

```bash
s a in               → show adj-rib in
s a out              → show adj-rib out
s a i                → show adj-rib in
s a o                → show adj-rib out

s a in n 10.0.0.1    → show adj-rib in neighbor 10.0.0.1

f a out              → flush adj-rib out
f a out n 10.0.0.1   → flush adj-rib out neighbor 10.0.0.1
```

### Watchdog

```bash
a w myapp            → announce watchdog myapp
w w myapp            → withdraw watchdog myapp
```

---

## Complex Examples

### Multi-hop shortcuts

```bash
s n s
  → show neighbor summary

s a i e
  → show adj-rib in extensive

n 10.0.0.1 s e
  → neighbor 10.0.0.1 show extensive
  → (transforms to: show neighbor 10.0.0.1 extensive)

a r 10.0.0.0/24 n 192.168.1.1 next-hop self
  → announce route 10.0.0.0/24 neighbor 192.168.1.1 next-hop self
```

### Mixing shortcuts and full words

```bash
s neighbor summary
  → show neighbor summary

announce r 10.0.0.0/24 next-hop 1.1.1.1
  → announce route 10.0.0.0/24 next-hop 1.1.1.1

show a in extensive
  → show adj-rib in extensive
```

---

## Context Resolution Algorithm

**Implemented in:** `src/exabgp/application/shortcuts.py:CommandShortcuts.get_expansion()`

### Decision Tree

1. **Check position:**
   - Is token at position 0? (first token)
   - Is token after neighbor IP?

2. **Check previous tokens:**
   - What command words came before?
   - Is token after specific keywords?

3. **Apply context rules:**
   - Match shortcut against context table
   - Return appropriate expansion

4. **Return token unchanged if:**
   - No matching shortcut for this context
   - Token is already full word

### Example: `a` resolution

```
Input: "a ..."
Position: 0 (first token)
Previous: None
Context: First token
→ Expands to: "announce"

Input: "show a in"
Position: 1 (second token)
Previous: ["show"]
Context: After "show"
→ Expands to: "adj-rib"

Input: "announce a next-hop 1.1.1.1"
Position: 1 (second token)
Previous: ["announce"]
Context: After "announce"
→ Expands to: "attributes"
```

---

## Tab Completion Integration

Shortcuts work seamlessly with tab completion:

```bash
# Type shortcut + TAB
s n<TAB>
  → expands to "show neighbor"
  → shows completions for neighbor options

# Type partial shortcut + TAB
sh<TAB>
  → auto-expands to "show" (unambiguous)
  → shows completions for show subcommands

# Shortcuts expand before completion
a r 10.0.0.0/24<TAB>
  → "announce route 10.0.0.0/24"
  → shows attribute completions (next-hop, as-path, etc.)
```

**Implementation:**
- Shortcuts expand in `CommandCompleter.complete()` before completion lookup
- Auto-expansion happens for unambiguous prefixes
- Metadata (descriptions) shown for all completions

**See:** `CLI_IMPLEMENTATION.md` for tab completion internals

---

## Shortcut Expansion Modes

### Interactive CLI

**When:** User typing in REPL

**Expansion:** Automatic via tab completion + readline

**Example:**
```bash
exabgp> s n<TAB>
  → expands to "show neighbor"
exabgp> show neighbor <cursor>
```

### Programmatic/Script Usage

**When:** Commands sent via socket without CLI

**Expansion:** Must use full commands or handle expansion programmatically

**Example:**
```python
# Raw socket - use full commands
socket.send(b"show neighbor summary\n")

# Using shortcuts - expand first
from exabgp.application.shortcuts import CommandShortcuts
expanded = CommandShortcuts.expand_shortcuts("s n s")
socket.send(expanded.encode() + b"\n")
```

---

## Common Patterns

### Show neighbor status

```bash
s n              # show neighbor
s n s            # show neighbor summary
s n e            # show neighbor extensive
s n c            # show neighbor configuration
```

### Show routes

```bash
s a in           # show adj-rib in
s a out          # show adj-rib out
s a i e          # show adj-rib in extensive
```

### Announce/withdraw routes

```bash
a r <prefix> <attrs>      # announce route
w r <prefix>              # withdraw route
a e <afi> <safi>          # announce eor
```

### Neighbor-targeted commands

```bash
n <ip> s                  # neighbor <ip> show
n <ip> s e                # neighbor <ip> show extensive
n <ip> t                  # neighbor <ip> teardown
n <ip> a r <prefix> ...   # neighbor <ip> announce route
```

---

## Shortcuts vs Full Commands

### When to use shortcuts

✅ Interactive CLI sessions - Save typing
✅ Quick operations - Faster workflow
✅ Familiar patterns - Muscle memory

### When to use full commands

✅ Scripts/automation - Explicit and clear
✅ Documentation - Self-documenting
✅ Shared commands - Team readability
✅ API integration - No expansion needed

---

## Implementation Details

### Shortcut Storage

**File:** `src/exabgp/application/shortcuts.py`

**Data structure:**
```python
SHORTCUTS = {
    'a': [
        {
            'expansion': 'announce',
            'matcher': lambda tokens, pos, prev: pos == 0 or _is_after_ip(tokens, pos)
        },
        {
            'expansion': 'attributes',
            'matcher': lambda tokens, pos, prev: 'announce' in prev or 'withdraw' in prev
        },
        {
            'expansion': 'adj-rib',
            'matcher': lambda tokens, pos, prev: any(x in prev for x in ['clear', 'flush', 'show'])
        }
    ],
    # ... more shortcuts
}
```

### Context Matchers

Each shortcut has matcher functions that check:
- Token position (`pos == 0`)
- Previous tokens (`'show' in prev`)
- Neighboring tokens (`_is_after_ip(tokens, pos)`)
- Command structure (`_in_announce_context(prev)`)

### Expansion Process

```python
# Single command expansion
expanded = CommandShortcuts.expand_shortcuts("s n s")
# Result: "show neighbor summary"

# Token list expansion
tokens = ["s", "n", "s"]
expanded_tokens = CommandShortcuts.expand_token_list(tokens)
# Result: ["show", "neighbor", "summary"]

# Single token with context
expansion = CommandShortcuts.get_expansion(
    token="a",
    position=0,
    previous_tokens=[]
)
# Result: "announce"
```

---

## Typo Corrections

The CLI automatically corrects common typos:

| Typo | Corrects To | Type |
|------|-------------|------|
| `neighbour` | `neighbor` | UK spelling |
| `neigbour` | `neighbor` | Transposition |
| `neigbor` | `neighbor` | Transposition |

**Example:**
```bash
exabgp> show neighbour summary
  → expands to: show neighbor summary

exabgp> neigbor 10.0.0.1 show
  → expands to: neighbor 10.0.0.1 show
  → transforms to: show neighbor 10.0.0.1
```

---

## Cheat Sheet

### Most Common Shortcuts

| Pattern | Shortcut | Expansion |
|---------|----------|-----------|
| Show neighbor | `s n` | `show neighbor` |
| Show summary | `s n s` | `show neighbor summary` |
| Show extensive | `s n e` | `show neighbor extensive` |
| Show adj-rib in | `s a in` | `show adj-rib in` |
| Show adj-rib out | `s a out` | `show adj-rib out` |
| Announce route | `a r` | `announce route` |
| Withdraw route | `w r` | `withdraw route` |
| Announce EOR | `a e` | `announce eor` |
| Teardown | `t n` | `teardown neighbor` |
| Flush adj-rib | `f a out` | `flush adj-rib out` |

### Power User Patterns

```bash
# Quick neighbor check
s n s

# Detailed neighbor info
s n e

# Announce route to specific neighbor
n 192.168.1.1 a r 10.0.0.0/24 next-hop self

# Withdraw route from specific neighbor
n 192.168.1.1 w r 10.0.0.0/24

# Check received routes (both syntaxes work for show)
s a in 192.168.1.1
n 192.168.1.1 a in show

# Teardown neighbor
n 192.168.1.1 t

# Send EOR to specific neighbor
n 192.168.1.1 a e ipv4 unicast

# Request route refresh from specific neighbor
n 192.168.1.1 a route-refresh ipv4 unicast
```

---

## See Also

- **CLI_COMMANDS.md** - Complete command reference
- **CLI_IMPLEMENTATION.md** - Tab completion and expansion internals
- **UNIX_SOCKET_API.md** - Raw API protocol (no shortcuts)
- **`.claude/exabgp/NEIGHBOR_SELECTOR_SYNTAX.md`** - Neighbor selection

---

**Updated:** 2025-12-19
