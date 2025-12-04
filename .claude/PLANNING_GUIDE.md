# Planning Guide

**All project plans live in `plan/` directory (project root), tracked in git.**

---

## Plan Location

**IMPORTANT:** All plans MUST be saved to the `plan/` directory in the project root, NOT in `.claude/` or `~/.claude/plans/`.

```
plan/                              # Project root
├── todo.md                        # Central TODO tracking
├── packed-attribute.md            # Packed-bytes-first refactoring
├── coverage.md                    # Test coverage audit
├── python312-buffer-protocol.md   # Future: Python 3.12 + memoryview
├── type-annotations/              # Type annotation detailed plans
└── xxx-cleanup/                   # XXX comment cleanup
```

**Naming:** Lowercase with hyphens: `type-annotations/`, `python312-buffer-protocol.md`

---

## Required Files

### README.md
```markdown
# Project Name

Brief description.

## Directory Structure
[Show structure]

## Quick Start
1. Read ANALYSIS.md
2. Review PLAN.md
3. Track PROGRESS.md

## Goals
- Goal 1
- Goal 2
```

### PLAN.md
```markdown
# Plan: Project Name

**Status:** Ready | In progress | Complete
**Priority:** 🔴 🟡 🟢

## Overview
[What and why]

## Phase 1: Name 🔴
**Goal:** [What]
**Files:** [Paths]
**Testing:** [Commands]

## Phase 2: Name 🟡
[Repeat]
```

### PROGRESS.md
```markdown
# Progress

**Status:** [status]

## Overall
- [ ] Phase 1 (count items)
- [ ] Phase 2 (count items)

## Phase 1
- [ ] file1.py
- [ ] file2.py

**Tests:** [Last run results]
```

---

## File Size Limits

- Core protocols: < 5 KB
- Reference docs: < 8 KB
- Status/progress: < 5 KB
- READMEs: < 3 KB

**If exceeding: split or archive**

---

## Archiving

**When complete:**
1. Keep completed plan in `plan/` with status "Complete"
2. Or move to `.claude/docs/archive/<project>/` if no longer relevant
3. Update `plan/todo.md` to mark as complete

---

## Examples

**Active plans:** `plan/` directory
**Archived docs:** `.claude/docs/archive/`

---

**Updated:** 2025-12-04
