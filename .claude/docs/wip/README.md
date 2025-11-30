# Work in Progress

Active development projects. When completed, move to `docs/projects/`.

## Active Projects

### Type Annotations
**Location:** `type-annotations/`
**Status:** In progress - Phase 3 (MyPy error reduction)
**Current:** 605 errors (47% ↓ from 1,149 baseline)
**Goal:** Full type coverage with MyPy validation

**Files:**
- `MYPY_STATUS.md` - Current error analysis
- `PROGRESS.md` - Phase tracking
- `README.md` - Project overview

**Historical docs:** See `docs/projects/type-annotations/` for planning archives

### Type Ignore Elimination
**Location:** `type-ignore-elimination/`
**Status:** Active - Systematic removal of type: ignore comments
**Goal:** Achieve full mypy compliance without suppressions

**Files:**
- `TYPE_IGNORE_ELIMINATION.md` - Complete inventory and plan
- `README.md` - Project overview

### XXX Comment Cleanup
**Location:** `xxx-cleanup/`
**Status:** Active - Resolution of XXX comments
**Goal:** Review and resolve all XXX markers in codebase

**Files:**
- `TODO.md` - XXX inventory and tracking
- `README.md` - Project overview

---

## Adding New WIP Projects

When starting new work:
1. Create `wip/<project-name>/` directory
2. Add `README.md` with status, goals, current work
3. Update this file with project entry
4. When complete, move to `docs/projects/<project-name>/`
