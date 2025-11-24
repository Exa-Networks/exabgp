# .claude Directory Compression Plan

## Problem

**Current size:** 640.9 KB across 56 markdown files
**Issue:** Wastes context space, harder to read, less efficient

---

## Compression Strategy

### PRINCIPLE: Maximum information density, minimum verbosity

**Rules:**
1. Remove examples - replace with references
2. Remove repetition - say it once
3. Remove verbose explanations - use terse language
4. Remove template text - keep only essentials
5. Archive inactive projects
6. Consolidate related docs

---

## Target Reductions

### 🔴 HIGH PRIORITY (Active, Frequently Read)

| File | Current | Target | Savings | Action |
|------|---------|--------|---------|--------|
| MANDATORY_REFACTORING_PROTOCOL.md | 19.6 KB | 6 KB | 70% | Cut examples, repetition |
| CODING_STANDARDS.md | 10.9 KB | 4 KB | 63% | Remove verbose examples |
| EMOJI_GUIDE.md | 7.8 KB | 2 KB | 74% | Keep table only |
| PLANNING_GUIDE.md | 8.1 KB | 3 KB | 63% | Remove templates |
| COMMUNICATION_STYLE.md | 9.1 KB | 3 KB | 67% | Cut examples |
| TESTING_DISCIPLINE.md | 3.6 KB | 2 KB | 44% | Already terse, minor cuts |

**Subtotal:** 59.1 KB → 20 KB (66% reduction)

### 🟡 MEDIUM PRIORITY (Reference, Occasionally Read)

| File | Current | Target | Action |
|------|---------|--------|--------|
| RFC_ALIGNMENT_REFACTORING.md | 13.3 KB | DELETE | ✅ Complete, move to archive |
| PACK_METHOD_STANDARDIZATION_STATUS.md | 4.4 KB | 2 KB | Keep status only |
| type-annotations/MYPY_STATUS.md | 7.6 KB | 3 KB | Remove verbose descriptions |
| type-annotations/PROGRESS.md | 31.4 KB | 8 KB | Keep summary only |
| type-annotations/ANY_REPLACEMENT_PLAN.md | 14.8 KB | 5 KB | Remove examples |
| type-annotations/ANALYSIS.md | 20.4 KB | DELETE | Completed analysis, archive |

**Subtotal:** 91.9 KB → 18 KB (80% reduction)

### 🟢 LOW PRIORITY (Archive or Inactive)

| Directory/File | Size | Action |
|----------------|------|--------|
| async-migration/ | 94 KB | ARCHIVE - not active |
| todo/ (fuzz testing) | 113 KB | ARCHIVE - not current focus |
| docs/TESTING_* | 68 KB | CONSOLIDATE to 15 KB |
| archive/ already | 71 KB | KEEP - already archived |

**Subtotal:** 275 KB → DELETE/ARCHIVE (100% from active)

### 📁 New Files (This Session)

| File | Size | Action |
|------|------|--------|
| CLEANUP_2025_11_16.md | 5.0 KB | DELETE - temporary, merge to audit |
| .AUDIT_2025_11_16.md | 7.4 KB | COMPRESS to 2 KB |

**Subtotal:** 12.4 KB → 2 KB (84% reduction)

---

## Projected Results

**Current:** 640.9 KB
**After compression:** ~150 KB
**Reduction:** 76%

**Breakdown:**
- Active core docs: 59 KB → 20 KB (66% ↓)
- Reference docs: 92 KB → 18 KB (80% ↓)
- Inactive → Archive: 275 KB → 0 KB (removed from active)
- New session docs: 12 KB → 2 KB (84% ↓)
- Remaining (archive, etc): ~110 KB (untouched)

---

## Compression Techniques

### 1. Remove Verbose Examples
**Before (29 lines):**
```markdown
### Example 1: Simple Fix
```
❌ BAD:
"I'll help you fix that issue! Let me start by reading..."

✅ GOOD:
"Fixing now."
```

**After (3 lines):**
```markdown
### Examples
❌ Verbose: "I'll help you fix..." → ✅ Terse: "Fixing now"
```

### 2. Remove Template Boilerplate
**Before (50 lines of template):**
```markdown
## Required Files
### 1. README.md
**Purpose:** Project overview
**Template:**
[50 lines of markdown template]
```

**After (5 lines):**
```markdown
## Required Files
README.md, PLAN.md, ANALYSIS.md, PROGRESS.md
See archived example: `.claude/archive/type-annotations/`
```

### 3. Tables Over Lists
**Before (15 lines):**
```markdown
Priority levels:
- 🔴 HIGH priority - Critical work
- 🟡 MEDIUM priority - Important work
- 🟢 LOW priority - Optional work
```

**After (4 lines):**
```markdown
| 🔴 High | 🟡 Med | 🟢 Low |
Critical | Important | Optional
```

### 4. Remove Repetition
**Before:** Same message repeated in 3 sections
**After:** Say it once, reference elsewhere

### 5. Archive Completed Work
**Criteria:**
- Status: COMPLETE
- Not referenced frequently
- Historical value only

**Action:** Move to archive with 2-line notice in main README

---

## Execution Order

### Phase 1: Archive Inactive (Immediate)
1. Move `async-migration/` → `archive/async-migration/`
2. Move `todo/` → `archive/todo/`
3. Move `RFC_ALIGNMENT_REFACTORING.md` → `archive/`
4. Move `type-annotations/ANALYSIS.md` → `archive/`
5. Delete `CLEANUP_2025_11_16.md` (merge to audit)

**Savings:** ~400 KB removed from active

### Phase 2: Compress Core Protocols (High Impact)
6. MANDATORY_REFACTORING_PROTOCOL.md: 19.6 KB → 6 KB
7. CODING_STANDARDS.md: 10.9 KB → 4 KB
8. EMOJI_GUIDE.md: 7.8 KB → 2 KB
9. COMMUNICATION_STYLE.md: 9.1 KB → 3 KB
10. PLANNING_GUIDE.md: 8.1 KB → 3 KB

**Savings:** ~40 KB

### Phase 3: Compress Reference Docs
11. type-annotations/PROGRESS.md: 31.4 KB → 8 KB
12. type-annotations/MYPY_STATUS.md: 7.6 KB → 3 KB
13. docs/TESTING_*: Consolidate 68 KB → 15 KB
14. .AUDIT_2025_11_16.md: 7.4 KB → 2 KB

**Savings:** ~50 KB

---

## Compression Rules (MANDATORY)

When writing ANY .claude/ file:

### ❌ NEVER
- Long examples (max 3 lines per example)
- Repetition (say it once)
- Templates (link to examples)
- Boilerplate (get to the point)
- Conversational tone (terse only)

### ✅ ALWAYS
- Tables over prose
- Bullet points over paragraphs
- Code snippets over descriptions
- References over duplication
- Terse > Verbose

### 📏 Length Limits
- Core protocols: < 5 KB
- Reference docs: < 8 KB
- Status/progress: < 5 KB
- READMEs: < 3 KB

**If exceeding limits:** Split or archive

---

## Success Metrics

✅ Core protocols: All < 5 KB
✅ Total active docs: < 150 KB
✅ No inactive projects in root
✅ No files > 10 KB (except archive)
✅ All info preserved, just compressed

---

## Next Steps

1. **Get approval** for archiving async-migration/ and todo/
2. **Execute Phase 1** (archiving) - 10 min
3. **Execute Phase 2** (core compression) - 30 min
4. **Execute Phase 3** (reference compression) - 20 min
5. **Verify** all tests still pass
6. **Update** README with new structure

**Total time:** ~1 hour
**Result:** 640 KB → 150 KB (76% reduction)

---

**Created:** 2025-11-16
**Status:** Awaiting approval
**Priority:** 🔴 HIGH - impacts all future sessions
