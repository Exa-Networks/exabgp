# Plan: Standardize on FamilyTuple Type Alias

## Summary

Introduce a `FamilyTuple` type alias to replace all occurrences of `tuple[AFI, SAFI]` throughout the codebase for consistency and maintainability.

## Scope

- **67 type hint occurrences** across **18 files**
- No runtime behavior changes - purely type annotation refactor
- Single new type alias definition

## Type Alias Definition

**Location:** `src/exabgp/protocol/family.py` (after AFI/SAFI class definitions)

```python
from typing import TypeAlias

FamilyTuple: TypeAlias = tuple[AFI, SAFI]
```

**Rationale:** This file already defines AFI and SAFI classes, making it the natural home for family-related types.

## Files to Modify

### Phase 1: Define Type Alias
| File | Change |
|------|--------|
| `src/exabgp/protocol/family.py` | Add `FamilyTuple: TypeAlias = tuple[AFI, SAFI]` |

### Phase 2: High Impact Files (5+ changes each)
| File | Occurrences | Patterns |
|------|-------------|----------|
| `src/exabgp/bgp/message/open/capability/negotiated.py` | 8 | `list[FamilyTuple]`, `set[FamilyTuple]`, `dict[FamilyTuple, bool]` |
| `src/exabgp/bgp/neighbor/neighbor.py` | 6 | `list[FamilyTuple]`, `deque[FamilyTuple]`, `dict[FamilyTuple, Operational]` |
| `src/exabgp/rib/outgoing.py` | 6 | `dict[...]`, `set[FamilyTuple]`, `FamilyTuple \| None` |
| `src/exabgp/rib/cache.py` | 6 | `set[FamilyTuple]`, `dict[FamilyTuple, dict[bytes, Change]]` |

### Phase 3: Medium Impact Files (2-4 changes each)
| File | Occurrences |
|------|-------------|
| `src/exabgp/bgp/message/open/capability/addpath.py` | 2 |
| `src/exabgp/bgp/message/open/capability/capabilities.py` | 2 |
| `src/exabgp/bgp/message/open/capability/graceful.py` | 2 |
| `src/exabgp/bgp/message/update/nlri/nlri.py` | 3 |
| `src/exabgp/configuration/neighbor/__init__.py` | 5 |
| `src/exabgp/protocol/family.py` | 2 |
| `src/exabgp/reactor/peer/peer.py` | 2 |
| `src/exabgp/rib/__init__.py` | 1 |
| `src/exabgp/rib/incoming.py` | 1 |

### Phase 4: Low Impact Files (1 change each)
| File | Occurrences |
|------|-------------|
| `src/exabgp/bgp/message/open/capability/mp.py` | 1 |
| `src/exabgp/bgp/message/operational.py` | 1 |
| `src/exabgp/configuration/configuration.py` | 2 |
| `src/exabgp/configuration/neighbor/family.py` | 1 |
| `src/exabgp/reactor/api/command/peer.py` | 1 |
| `src/exabgp/reactor/peer/handlers/route_refresh.py` | 1 |
| `src/exabgp/rib/change.py` | 1 |

## Replacement Patterns

| Before | After |
|--------|-------|
| `tuple[AFI, SAFI]` | `FamilyTuple` |
| `list[tuple[AFI, SAFI]]` | `list[FamilyTuple]` |
| `set[tuple[AFI, SAFI]]` | `set[FamilyTuple]` |
| `dict[tuple[AFI, SAFI], T]` | `dict[FamilyTuple, T]` |
| `Iterable[tuple[AFI, SAFI]]` | `Iterable[FamilyTuple]` |
| `tuple[AFI, SAFI] \| None` | `FamilyTuple \| None` |

## Import Changes Required

Each file using `FamilyTuple` needs to import it. Most files already import from `family.py`:

```python
# Before (typical)
from exabgp.protocol.family import AFI, SAFI

# After
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
```

## Special Cases

### 1. Class Inheritance
Some classes inherit from `dict[tuple[AFI, SAFI], int]`:

```python
# Before
class AddPath(Capability, dict[tuple[AFI, SAFI], int]):

# After
class AddPath(Capability, dict[FamilyTuple, int]):
```

### 2. Callable Type Hints
```python
# Before
Callable[[bool, tuple[AFI, SAFI]], None]

# After
Callable[[bool, FamilyTuple], None]
```

### 3. Nested Structures
```python
# Before
list[tuple[str, tuple[AFI, SAFI]]]

# After
list[tuple[str, FamilyTuple]]
```

## Testing

1. Run `uv run ruff format src && uv run ruff check src` after each phase
2. Run `uv run mypy src` to verify type consistency
3. Run `./qa/bin/test_everything` after completion

## Verification

After refactor:
```bash
# Should find 0 occurrences (except in comments/strings)
grep -r "tuple\[AFI, SAFI\]" src/exabgp/

# Should find ~67 occurrences
grep -r "FamilyTuple" src/exabgp/
```

## Risks

- **Low risk**: Type alias is purely cosmetic at runtime
- Import additions could cause circular imports (unlikely - family.py is low-level)
- No behavioral changes

## Not In Scope

- Changing function signatures from `(afi, safi)` to `(family: FamilyTuple)`
- Creating a `Family` dataclass to replace tuples
- Modifying the existing `Family` class in family.py

---

**Status:** 📋 Ready for implementation
**Estimated changes:** 67 type hints + 18 import statements
