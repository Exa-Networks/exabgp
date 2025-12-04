# Type Annotations Project

🔄 **Status:** ACTIVE - Ongoing type safety improvements

This directory consolidates ALL type annotation work for ExaBGP.

## Directory Structure

```
.claude/docs/wip/type-annotations/
├── README.md                          # This file - overview and navigation
├── INDEX.md                           # Complete file index
├── PROGRESS.md                        # Current progress tracking
│
├── # Active plans
├── ANY_REPLACEMENT_PLAN.md            # Plan to replace all Any types
├── MYPY_ELIMINATION_PLAN.md           # Plan to eliminate type: ignore comments
├── MYPY_STATUS.md                     # Current mypy error status
├── PYTHON38_COMPATIBILITY.md          # ⚠️  Python 3.8+ compatibility requirements
│
├── type-ignore-elimination/           # Sub-project: eliminate type: ignore
│   ├── README.md                      # Sub-project overview
│   └── TYPE_IGNORE_ELIMINATION.md     # Detailed elimination plan
│
└── archive/initial-planning/          # Historical planning docs
    ├── README.md                      # Original project overview
    ├── analysis.md                    # Initial analysis (historical)
    ├── plan.md                        # Original plan (historical)
    └── progress.md                    # Early progress (historical)
```

## Quick Start

1. **⚠️  Check compatibility FIRST**: `PYTHON38_COMPATIBILITY.md` - REQUIRED reading before ANY changes
2. **Current status**: `MYPY_STATUS.md` - Latest mypy error counts and progress
3. **Active work**: `PROGRESS.md` - Current task tracking
4. **Type: ignore elimination**: `type-ignore-elimination/` - Sub-project to remove type: ignore comments
5. **Historical context**: `archive/initial-planning/` - Original planning documents

## Goals

Replace all `Any` type annotations with proper, specific types to:
- Improve type safety and catch errors earlier
- Better IDE autocomplete and development experience
- Document the codebase architecture through types
- Enable better static analysis with mypy/pyright
- **Maintain Python 3.8.1+ compatibility** (required by ExaBGP)

## Python Version Requirements

**⚠️  CRITICAL: All type annotations must be Python 3.8.1+ compatible**

ExaBGP supports Python 3.8.1+ and CI tests run on Python 3.8-3.12. Before making ANY type annotation changes:

1. **Read** `PYTHON38_COMPATIBILITY.md` - Contains full compatibility guidelines
2. **Use** `typing.Optional`, `typing.Union`, `typing.List/Dict/Tuple` (NOT Python 3.9+ built-ins)
3. **Avoid** `|` operator (Python 3.10+), lowercase generics (Python 3.9+)
4. **Ensure** `from __future__ import annotations` is at top of file
5. **Test** with full test suite to catch compatibility issues

## Testing Requirements

After each change:
1. ✅ `ruff format src && ruff check src` (catches many compatibility issues)
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/`
3. ✅ `./qa/bin/functional encoding` (for affected components)

## Related Documentation

- Main project instructions: `/CLAUDE.md`
- **Python 3.8+ compatibility**: `PYTHON38_COMPATIBILITY.md` ⚠️  REQUIRED
- Testing guide: `.claude/docs/CI_TESTING_GUIDE.md`
- Legacy type annotation work: `.claude/archive/TYPE_ANNOTATION_PROGRESS.md` (deprecated)
