# Plan: Centralize Log Lambda Functions with lazymsg()

**Status:** Planning
**Priority:** 🟢 Low

## Overview

The codebase has ~245 log statements using lambdas for lazy evaluation. Replace with a single `lazymsg()` helper for:
- Better type safety (mypy struggles with lambda default arguments)
- Cleaner code
- Consistent pattern

## Current Pattern

```python
# Simple f-string
log.debug(lambda: f'duplicate AFI/SAFI: {afi}/{safi}', 'parser')

# With captured variables (problematic for mypy)
log.debug(lambda afi=afi, safi=safi: f'duplicate AFI/SAFI: {afi}/{safi}', 'parser')
```

## Problem

Mypy doesn't handle lambda with default arguments well. Current workaround is verbose:

```python
def _log_dup(afi: AFI = afi, safi: SAFI = safi) -> str:
    return f'duplicate AFI/SAFI: {afi}/{safi}'
log.debug(_log_dup, 'parser')
```

## Solution: lazymsg()

Add helper in `src/exabgp/logger/__init__.py`:

```python
from typing import Any, Callable

def lazymsg(template: str, **kwargs: Any) -> Callable[[], str]:
    """Create a lazy log message from a format string template."""
    def _format() -> str:
        return template.format(**kwargs)
    return _format
```

### Usage

```python
# Before
log.debug(lambda afi=afi, safi=safi: f'duplicate AFI/SAFI: {afi}/{safi}', 'parser')

# After
from exabgp.logger import lazymsg
log.debug(lazymsg('duplicate AFI/SAFI: {afi}/{safi}', afi=afi, safi=safi), 'parser')
```

## Implementation Steps

1. Add `lazymsg()` to `src/exabgp/logger/__init__.py`
2. Refactor one file at a time, testing after each
3. Remove inline `_log_*` functions created for mypy workarounds

## Testing

After each file refactor:
```bash
./qa/bin/test_everything
```

---

**Created:** 2025-11-26
