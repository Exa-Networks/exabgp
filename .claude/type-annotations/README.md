# Type Annotations Project

This directory contains all documentation related to improving type annotations in ExaBGP.

## Directory Structure

```
.claude/type-annotations/
├── README.md                    # This file - overview and navigation
├── ANY_REPLACEMENT_PLAN.md      # Comprehensive plan to replace all Any types
├── ANALYSIS.md                  # Detailed analysis of all Any usage in codebase
├── PROGRESS.md                  # Progress tracking for type annotation work
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

## Goals

Replace all `Any` type annotations with proper, specific types to:
- Improve type safety and catch errors earlier
- Better IDE autocomplete and development experience
- Document the codebase architecture through types
- Enable better static analysis with mypy/pyright

## Testing Requirements

After each change:
1. ✅ `ruff format src && ruff check src`
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/`
3. ✅ `./qa/bin/functional encoding` (for affected components)

## Related Documentation

- Main project instructions: `/CLAUDE.md`
- Testing guide: `.claude/docs/CI_TESTING_GUIDE.md`
- Legacy type annotation work: `.claude/TYPE_ANNOTATION_PROGRESS.md` (deprecated, kept for reference)
