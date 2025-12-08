# ExaBGP Plans Directory

## Current Plans

| Plan | Status | Description |
|------|--------|-------------|
| `todo.md` | 🔄 Active | Master TODO list with project tracking |
| `coverage.md` | 🔄 Active | Test coverage improvement (59.71% → 60%) |
| `wire-semantic-separation.md` | 🔄 Phase 1 Complete | Wire vs Semantic container separation |
| `update-context-attachment.md` | 📋 Planning | Global Update cache with SHA256 IDs |
| `type-identification-review.md` | 📋 Planning | hasattr() → ClassVar review |
| `addpath-nlri.md` | 📋 Planning | ADD-PATH for more NLRI types |
| `architecture.md` | 📋 Planning | Circular dependency fixes |
| `code-quality.md` | 📋 Planning | Misc improvements (low priority) |
| `family-tuple.md` | 📋 Planning | FamilyTuple type alias |
| `rib-improvement-proposals.md` | 📋 Discussion | RIB improvement ideas |
| `runtime-validation-plan.md` | 📋 Planning | Runtime validation |
| `security-validation.md` | 📋 Planning | Security validation |

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

**Updated:** 2025-12-07
