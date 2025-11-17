# Type Annotations Project

This directory contains all documentation related to improving type annotations in ExaBGP.

## Directory Structure

```
.claude/type-annotations/
├── README.md                    # This file - overview and navigation
├── ANY_REPLACEMENT_PLAN.md      # Comprehensive plan to replace all Any types
├── ANALYSIS.md                  # Detailed analysis of all Any usage in codebase
├── PROGRESS.md                  # Progress tracking for type annotation work
├── PYTHON38_COMPATIBILITY.md    # ⚠️  Python 3.8+ compatibility requirements
└── phases/                      # Phase-specific documentation
    ├── phase1-core-architecture.md
    ├── phase2-generators.md
    ├── phase3-messages.md
    ├── phase4-configuration.md
    ├── phase5-registries.md
    ├── phase6-logging.md
    ├── phase7-flow-parsers.md
    └── phase8-miscellaneous.md
```

## Quick Start

1. **Read the analysis**: `ANALYSIS.md` - Comprehensive breakdown of all 150+ Any usages
2. **Review the plan**: `ANY_REPLACEMENT_PLAN.md` - 8-phase structured approach
3. **Track progress**: `PROGRESS.md` - Current status and completed work
4. **⚠️  Check compatibility**: `PYTHON38_COMPATIBILITY.md` - REQUIRED reading before modifying types

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
