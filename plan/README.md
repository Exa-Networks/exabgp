# ExaBGP Plans Directory

## Naming Convention

### Directory Structure

```
plan/
├── README.md                    # This file - naming conventions
├── todo.md                      # Master TODO list with references
│
├── # Active multi-file projects (directories)
├── type-safety/                 # Type annotations project
│   ├── README.md                # Project overview
│   ├── progress.md              # Current progress
│   └── *.md                     # Sub-plans
│
├── packed-bytes/                # Packed-bytes-first refactoring
│   ├── README.md
│   └── progress.md
│
├── runtime-validation/          # Security: input validation
│   ├── README.md
│   └── *.md
│
├── xxx-cleanup/                 # XXX comment resolution
│   ├── README.md
│   └── TODO.md
│
├── # Single-file plans (standalone .md files)
├── coverage.md                  # Test coverage improvement
├── python312-buffer.md          # Python 3.12 migration
├── addpath-nlri.md              # AddPath feature expansion
├── architecture.md              # Circular dependency fixes
├── security-validation.md       # Config parser validation
├── code-quality.md              # Low-priority improvements
└── family-tuple.md              # FamilyTuple standardization
```

### Naming Rules

1. **Directories** - For multi-file projects with sub-plans
   - Use kebab-case: `type-safety/`, `packed-bytes/`
   - MUST contain `README.md` with overview
   - May contain `progress.md` for tracking
   - Sub-plans use UPPER_SNAKE_CASE: `MYPY_STATUS.md`

2. **Single files** - For standalone plans
   - Use kebab-case: `coverage.md`, `addpath-nlri.md`
   - Short, descriptive names (2-3 words max)
   - No prefixes like `PLAN_` or `TODO_`

3. **Progress/Status files**
   - `progress.md` - Current state tracking (in directories)
   - `TODO.md` - Remaining work items (in directories)

4. **Archive directories**
   - `archive/` subdirectory for historical docs
   - Preserve for context, mark as historical

### File Template

```markdown
# [Title]

**Status:** [emoji] [Active|Planning|Completed|On Hold]
**Started:** YYYY-MM-DD
**Last Updated:** YYYY-MM-DD
**See also:** [related files]

## Goal

[1-2 sentence summary]

## Scope

[What's included/excluded]

## Progress

| Item | Status |
|------|--------|
| ... | ... |

## Files to Modify

[List of affected files]

## Risks

[Known risks and mitigations]

## Recent Failures

| Date | Test | Error | Root Cause | Status |
|------|------|-------|------------|--------|
| 2025-12-04 | test_example | AssertionError: ... | Off-by-one | ✅ Fixed |

## Blockers

| Blocker | Discovered | Status | Notes |
|---------|------------|--------|-------|
| Need API change | 2025-12-03 | 🔴 Blocking | Discuss with team |

## Resume Point

**Last worked:** YYYY-MM-DD
**Last commit:** [hash or "uncommitted"]
**Session ended:** Mid-task / Clean break / Blocked

**To resume:**
1. [Exact next step to take]
2. [Context needed]
3. [Watch out for: potential issues]
```

### Status Emojis

| Emoji | Meaning |
|-------|---------|
| 🔄 | Active - work in progress |
| 📋 | Planning - not started |
| ✅ | Completed |
| ⏸️ | On Hold |
| ❌ | Cancelled |

---

**Last Updated:** 2025-12-04
