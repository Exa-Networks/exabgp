# Type Annotations Project - Quick Index

**Jump to:**
- [Overview](#overview)
- [Files](#files)
- [Quick Start](#quick-start)
- [Statistics](#statistics)

---

## Overview

This project systematically replaces all `Any` type annotations in ExaBGP with proper, specific types to improve type safety, IDE support, and code documentation.

**Current status:** Planning complete, ready to implement

---

## Files

| File | Purpose | Lines |
|------|---------|-------|
| **README.md** | Project overview and navigation | Overview |
| **ANALYSIS.md** | Detailed breakdown of all 150+ `Any` usages | ~1200 |
| **ANY_REPLACEMENT_PLAN.md** | 8-phase implementation plan | ~700 |
| **PROGRESS.md** | Progress tracking and test results | Updated |
| **INDEX.md** | This file - quick reference | Quick ref |

---

## Quick Start

### First Time

1. Read **ANALYSIS.md** (skim categories, focus on patterns)
2. Read **ANY_REPLACEMENT_PLAN.md** Phase 1
3. Start implementation

### Continuing Work

1. Check **PROGRESS.md** for current status
2. Find next uncompleted phase in **ANY_REPLACEMENT_PLAN.md**
3. Implement → Test → Update PROGRESS.md

### Finding Specific Information

**"Where are all the `Any` types?"**
→ ANALYSIS.md - Categorized by pattern and file

**"What's the implementation order?"**
→ ANY_REPLACEMENT_PLAN.md - 8 phases with priorities

**"What's been done?"**
→ PROGRESS.md - Phase-by-phase completion tracking

**"How do I fix circular dependencies?"**
→ ANY_REPLACEMENT_PLAN.md, Phase 1 - TYPE_CHECKING pattern

**"Which `Any` should stay?"**
→ ANALYSIS.md, bottom section - "Files to Keep As `Any`"

---

## Statistics

**Total `Any` instances:** 150+
**To be fixed:** ~140
**To keep as `Any`:** ~15-20 (documented)

### By Category
- Core Architecture: 40 instances (🔴 High Priority)
- Generators: 30 instances (🟡 Medium)
- Messages: 20 instances (🟡 Medium)
- Configuration: 25 instances (🟢 Lower)
- Registries: 15 instances (🟢 Lower)
- Logging: 10 instances (🟢 Lower)
- Flow Parsers: 10 instances (🟢 Lower)
- Miscellaneous: 10 instances (🟢 Lower)

### By Phase
1. Core Architecture - 40 instances (2-3 hours)
2. Generators - 30 instances (1 hour)
3. Messages - 20 instances (45 min)
4. Configuration - 25 instances (1-2 hours)
5. Registries - 15 instances (1 hour)
6. Logging - 10 instances (30 min)
7. Flow Parsers - 10 instances (1 hour)
8. Miscellaneous - 10 instances (30 min)

**Total estimated effort:** 4-7 hours

---

## Testing Checklist

After each change:

```bash
# Quick check
ruff check <file>

# After each phase
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
./qa/bin/functional encoding

# Full validation before completion
ruff format src && ruff check src
env exabgp_log_enable=false pytest --cov ./tests/unit/
./qa/bin/functional encoding
./qa/bin/parsing
```

---

## Common Patterns

### Circular Dependency Fix
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor
    from exabgp.reactor.peer import Peer
    from exabgp.bgp.neighbor import Neighbor
```

### Generator Types
```python
# Before
def read_message(self) -> Generator[Any, None, None]:

# After
def read_message(self) -> Generator[Union[Message, NOP], None, None]:
```

### Optional Types
```python
# Before
self.neighbor: Optional[Any] = None

# After
self.neighbor: Optional['Neighbor'] = None
```

---

## Related Documentation

- Main project instructions: `/CLAUDE.md`
- Testing guide: `.claude/docs/CI_TESTING_GUIDE.md`
- Planning standards: `.claude/PLANNING_GUIDE.md`
- Old type annotation docs: `.claude/archive/` (deprecated)
