# Planning Guide

**Standard structure for all `.claude/` planning docs.**

---

## Directory Structure

```
.claude/<project-name>/
├── README.md          # Overview and navigation
├── PLAN.md            # Implementation plan
├── ANALYSIS.md        # Findings (optional)
├── PROGRESS.md        # Progress tracking
```

**Naming:** Lowercase with hyphens: `type-annotations/`, `async-migration/`

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
1. Move to `.claude/archive/<project>/`
2. Add notice in main README
3. Keep 2-line summary in active README

---

## Examples

**See:** `.claude/archive/type-annotations/` (archived example)

---

**Updated:** 2025-11-16
