# ExaBGP Plans Directory

## Current Plans

| Plan | Status | Description |
|------|--------|-------------|
| `todo.md` | 🔄 Active | Master TODO list with project tracking |
| `nlri-immutability.md` | 🔄 Active | Make NLRI immutable (action → Route) |
| `nlri-immutability-phase2-3.md` | 🔄 Active | NLRI immutability phases 2-3 |
| `fix-resolve-self-deepcopy.md` | 📋 Planning | Fix resolve_self() memory duplication |
| `rib-optimisation.md` | 📋 Planning | RIB memory optimization |
| `coverage.md` | 🔄 Active | Test coverage improvement (59.71%) |
| `comment-cleanup/` | 🔄 Active | XXX/TODO comment cleanup (Phase 6-7) |
| `update-context-attachment.md` | 📋 Planning | Global Update cache with SHA256 IDs |
| `type-identification-review.md` | 📋 Planning | hasattr() → ClassVar review |
| `addpath-nlri.md` | 📋 Planning | ADD-PATH for more NLRI types |
| `architecture.md` | 📋 Planning | Circular dependency fixes |
| `code-quality.md` | 📋 Planning | Misc improvements (low priority) |
| `rib-improvement-proposals.md` | 📋 Discussion | RIB improvement ideas |
| `security-validation.md` | 📋 Planning | Security validation |

## Recently Completed (to be archived/deleted)

| Plan | Completed | Description |
|------|-----------|-------------|
| `testing-improvement-plan.md` | 2025-12-09 | Testing improvements (Phases 1-3, 6) |
| ~~`wire-semantic-separation.md`~~ | 2025-12-08 | Wire vs Semantic separation (deleted) |
| ~~`nexthop-self-refactor.md`~~ | 2025-12-08 | NextHopSelf refactoring (deleted) |
| ~~`phase4-rename-negotiated-opencontext.md`~~ | 2025-12-09 | Remove OpenContext class (deleted) |
| ~~`runtime-validation-plan.md`~~ | 2025-12-05 | Runtime validation (deleted) |

## Naming Convention

### Naming Rules

1. **Single files** - kebab-case: `coverage.md`, `addpath-nlri.md`
2. **Short names** - 2-3 words max, descriptive
3. **No prefixes** - Don't use `PLAN_` or `TODO_`

### File Template

```markdown
# [Title]

**Status:** [emoji] [Active|Planning|Completed|On Hold]
**Created:** YYYY-MM-DD
**Updated:** YYYY-MM-DD

## Goal

[1-2 sentence summary]

## Progress

- [x] Completed item
- [ ] Pending item

## Files to Modify

| File | Change |
|------|--------|
| ... | ... |
```

### Status Emojis

| Emoji | Meaning |
|-------|---------|
| 🔄 | Active - work in progress |
| 📋 | Planning - not started |
| ✅ | Completed (delete when done) |
| ⏸️ | On Hold |

---

**Updated:** 2025-12-09
