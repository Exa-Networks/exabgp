# Planning Guide for ExaBGP Documentation

This guide ensures all planning documents follow a consistent, well-structured format.

---

## Directory Structure Standard

All planning documentation must follow this structure:

```
.claude/
├── PLANNING_GUIDE.md           # This file - how to organize plans
├── README.md                   # Overview of .claude directory
├── docs/                       # General technical documentation
│   ├── CI_TESTING_GUIDE.md
│   └── ...
│
└── <project-name>/             # Each major project gets its own directory
    ├── README.md               # Project overview and navigation
    ├── <PROJECT>_PLAN.md       # Main implementation plan
    ├── ANALYSIS.md             # Detailed analysis/findings
    ├── PROGRESS.md             # Progress tracking
    └── phases/                 # Optional: detailed phase docs
        ├── phase1-<name>.md
        ├── phase2-<name>.md
        └── ...
```

---

## Project Directory Naming

**Pattern:** `<project-name>/`

**Examples:**
- `type-annotations/` - Type annotation improvement project
- `async-migration/` - Async/await migration project
- `testing-improvements/` - Testing infrastructure project
- `performance-optimization/` - Performance work
- `refactoring-<component>/` - Component refactoring

**Rules:**
- Use lowercase with hyphens
- Be descriptive but concise
- Group related work under one project

---

## Required Files in Each Project Directory

### 1. README.md

**Purpose:** Project overview and navigation
**Template:**

```markdown
# <Project Name>

<Brief description of the project goals>

## Directory Structure

```
<project-name>/
├── README.md                    # This file
├── <PROJECT>_PLAN.md            # Main plan
├── ANALYSIS.md                  # Analysis/findings
├── PROGRESS.md                  # Progress tracking
└── phases/                      # Phase details (optional)
```

## Quick Start

1. **Read the analysis**: `ANALYSIS.md` - <what's in it>
2. **Review the plan**: `<PROJECT>_PLAN.md` - <what's in it>
3. **Track progress**: `PROGRESS.md` - <what's in it>

## Goals

<Bullet points of main goals>

## Testing Requirements

<Project-specific testing needs>

## Related Documentation

- <Links to related docs>
```

---

### 2. <PROJECT>_PLAN.md

**Purpose:** Detailed implementation plan
**Template:**

```markdown
# Plan: <Project Name>

**Status:** <Ready to start | In progress | Complete>
**Total items:** <count>
**Estimated effort:** <time estimate>
**Approach:** <Brief description>

---

## Overview

<What we're doing and why>

**Key Strategy:**
- <Strategic point 1>
- <Strategic point 2>
- <Strategic point 3>

---

## Phase 1: <Name> <PRIORITY EMOJI>

**Goal:** <What this phase achieves>
**Impact:** <Why it matters>
**Instances/Items:** <count>
**Estimated time:** <time>

### Files to Update

1. **path/to/file1.py**
   - Description of changes
   - Specific line numbers if relevant

2. **path/to/file2.py**
   - Description of changes

### Implementation Approach

<Code examples, patterns, techniques>

### Testing After Phase 1
```bash
# Specific test commands
```

---

## Phase 2: <Name> <PRIORITY>

<Repeat pattern>

---

## Testing Strategy

### After Each File Edit
```bash
# Quick checks
```

### After Each Phase
```bash
# Phase validation
```

### Before Completion
```bash
# Full validation
```

---

## Progress Tracking

<Checklist of phases>

---

## Success Criteria

✅ <Criterion 1>
✅ <Criterion 2>
✅ <Criterion 3>

---

## Notes

<Additional context, decisions, rationale>

## References

- <Links to other documents>
```

**Priority Emojis:**
- 🔴 HIGH PRIORITY
- 🟡 MEDIUM PRIORITY
- 🟢 LOWER PRIORITY

---

### 3. ANALYSIS.md

**Purpose:** Detailed findings and analysis
**Template:**

```markdown
# <Project Name> Analysis

**Generated:** <date>
**Total items found:** <count>
**Files affected:** <count>

## Executive Summary

<Brief overview of findings>

## Pattern Categories

<Categorize findings by type/pattern>

---

## Category 1: <Name>

### path/to/file.py

**Occurrences:**

1. **Line XX** - Description
```python
# Current code
```
**Recommended:** <fix>
**Fix approach:** <how>

2. **Line YY** - Description
<Repeat>

---

## Category 2: <Name>

<Repeat pattern>

---

## Summary by Priority

### High Priority (<count> instances)
- <Description>
- Files: <list>

### Medium Priority (<count> instances)
- <Description>

### Lower Priority (<count> instances)
- <Description>

## Items to Keep As-Is

<Document anything intentionally not changed>
```

---

### 4. PROGRESS.md

**Purpose:** Track implementation progress
**Template:**

```markdown
# <Project Name> Progress

**Started:** <date>
**Status:** <status>
**Current Phase:** <current>

---

## Overall Progress

- [ ] Phase 1: <Name> (<count> items)
- [ ] Phase 2: <Name> (<count> items)
- [ ] Phase 3: <Name> (<count> items)

**Total items:** <count>
**Items fixed:** <count>
**Remaining:** <count>

---

## Phase 1: <Name>

**Status:** <Not started | In progress | Complete>
**Priority:** <emoji>
**Items:** <count>

### Files

- [ ] path/to/file1.py (<count> instances)
- [ ] path/to/file2.py (<count> instances)

### Test Results
```
Last run: <date/time>
Ruff: PASS/FAIL
Pytest: PASS/FAIL
Functional: PASS/FAIL
```

---

## Phase 2: <Name>

<Repeat pattern>

---

## Session Log

### <date>: <Session title>
- <What was accomplished>
- <What was learned>
- <Next steps>

---

## Next Steps

1. <Step 1>
2. <Step 2>

---

## Testing Commands

```bash
# Quick reference for testing
```

---

## Notes

<Ongoing notes, issues, decisions>
```

---

## Deprecated Documentation Cleanup

When creating new structured documentation:

1. **Move old docs to archive:**
   ```bash
   mkdir -p .claude/archive
   mv .claude/OLD_DOC.md .claude/archive/
   ```

2. **Update references:**
   - Update any links in other docs
   - Note in README.md where old content moved

3. **Keep archive docs with note at top:**
   ```markdown
   # ARCHIVED

   **Superseded by:** `.claude/<project-name>/`
   **Date archived:** <date>
   **Reason:** <why>

   <original content>
   ```

---

## Root-Level .claude/ Files

**Only these files belong in .claude/ root:**

- `README.md` - Directory overview
- `PLANNING_GUIDE.md` - This file
- `TESTING_DISCIPLINE.md` - Testing requirements
- `NEXT_SESSION.md` - Session handoff notes (transient)
- `settings.local.json` - Local settings
- **NO PLANNING DOCUMENTS** - All go in project directories

---

## Examples of Good Structure

### Good ✅
```
.claude/type-annotations/
├── README.md
├── ANY_REPLACEMENT_PLAN.md
├── ANALYSIS.md
├── PROGRESS.md
└── phases/
    ├── phase1-core-architecture.md
    └── phase2-generators.md
```

### Bad ❌
```
.claude/
├── TYPE_ANNOTATION_PLAN.md        # Should be in type-annotations/
├── TYPE_ANNOTATION_PROGRESS.md    # Should be in type-annotations/
├── mypy_analysis.md               # Should be in project dir
└── PROGRESS.md                    # Too vague, which project?
```

---

## When Claude Plans New Work

1. **Identify project name:** Choose descriptive directory name
2. **Create project directory:** `.claude/<project-name>/`
3. **Create required files:**
   - `README.md`
   - `<PROJECT>_PLAN.md`
   - `ANALYSIS.md` (if applicable)
   - `PROGRESS.md`
4. **Update `.claude/README.md`:** Add project to index
5. **Clean up old docs:** Archive deprecated planning files

---

## Template Locations

Templates for new documents:
- Project README: See section "Required Files" above
- Plan document: See "<PROJECT>_PLAN.md" template
- Analysis document: See "ANALYSIS.md" template
- Progress document: See "PROGRESS.md" template

---

## Enforcement

When asked to plan work:
1. ✅ Always create project directory
2. ✅ Always use templates
3. ✅ Always create all 4 files (README, PLAN, ANALYSIS, PROGRESS)
4. ✅ Never put planning docs in root
5. ✅ Archive old docs when superseded
