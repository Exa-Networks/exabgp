# Claude AI Assistant Resources

Documentation and protocols for Claude Code interactions with ExaBGP.

---

## Core Protocols (CRITICAL - READ FIRST)

| File | Purpose | Size |
|------|---------|------|
| **MANDATORY_REFACTORING_PROTOCOL.md** | Step-by-step verification for ALL refactoring | 3.7 KB |
| **GIT_VERIFICATION_PROTOCOL.md** | NEVER make git claims without fresh verification | 0.7 KB |
| **CODING_STANDARDS.md** | Python 3.8+ compatibility, type annotations, BGP APIs | 3.5 KB |
| **TESTING_DISCIPLINE.md** | NEVER claim success without testing ALL | 1.1 KB |
| **COMMUNICATION_STYLE.md** | Terse, direct communication. Use agents. | 2.1 KB |
| **EMOJI_GUIDE.md** | Systematic emoji usage for clarity | 1.8 KB |
| **PLANNING_GUIDE.md** | Standards for project planning docs | 1.5 KB |
| **CI_TESTING.md** | Complete testing requirements and commands | 3.2 KB |

**Total core protocols: ~17 KB**

---

## Completed Work (Reference)

| File | Status | Size |
|------|--------|------|
| PACK_METHOD_STANDARDIZATION_STATUS.md | ✅ Complete - All utility pack() renamed | 1.5 KB |
| COMPRESSION_PLAN.md | Plan for directory compression | 7 KB |
| .AUDIT_2025_11_16.md | Audit & cleanup summary | 1.5 KB |

---

## Active Projects

### Type Annotations (`type-annotations/`)
**Status:** Phase 3 - MyPy error reduction
**Progress:** 605 errors (47% ↓ from 1,149 baseline)

**Files:**
- README.md - Project overview
- ANY_REPLACEMENT_PLAN.md - Phase 1 plan (complete)
- MYPY_STATUS.md - Current error analysis (605 errors)
- MYPY_ELIMINATION_PLAN.md - Strategy for remaining errors
- PROGRESS.md - Phase tracking and recent improvements
- PYTHON38_COMPATIBILITY.md - Python 3.8+ requirements
- INDEX.md - Navigation

---

## Archive (`archive/`)

**Completed/inactive projects moved here:**
- async-migration/ - Async/await migration planning
- todo/ - Fuzzing and coverage work
- docs/ - Detailed testing guides (consolidated to CI_TESTING.md)
- RFC_ALIGNMENT_REFACTORING.md - ✅ Complete (all unpack() renamed)
- PACK_METHOD_STANDARDIZATION_PLAN.md - ✅ Complete (original plan)
- TYPE_ANNOTATION_ANALYSIS.md - Original Any analysis
- INCREMENTAL_PACK_RENAME_PLAN.md - Superseded
- Various deprecated progress/plan files

**Archive total: ~450 KB** (not loaded in active context)

---

## File Size Policy

**Active files MUST stay under:**
- Core protocols: < 5 KB
- Reference docs: < 8 KB
- Status/progress: < 5 KB
- READMEs: < 3 KB

**If exceeding: compress or archive**

---

## Quick Start

**For any code changes:**
1. Read **CODING_STANDARDS.md**
2. Read **MANDATORY_REFACTORING_PROTOCOL.md** (if refactoring)
3. Read **TESTING_DISCIPLINE.md**
4. Make changes
5. Run ALL tests (see CI_TESTING.md)
6. Only THEN claim success

**For git operations:**
- Read **GIT_VERIFICATION_PROTOCOL.md** (verify before claiming)

**For communication:**
- Read **COMMUNICATION_STYLE.md** (terse, direct)
- Read **EMOJI_GUIDE.md** (visual clarity)

---

## Testing Quick Reference

```bash
# Before claiming "fixed"/"ready"/"complete":
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
./qa/bin/functional encoding <test_id>
```

**All must pass. No exceptions.**

---

## Recent Changes (2025-11-16)

✅ Archived inactive projects (async-migration, todo, docs)
✅ Compressed all core protocols (59 KB → 14 KB, 77% ↓)
✅ Compressed reference docs
✅ Consolidated testing documentation
✅ Updated all baselines (605 MyPy, 1376 tests)
✅ Removed duplicates
✅ **Total reduction: 640 KB → ~150 KB (76% ↓)**

---

**Current Status:** ✅ 100% Accurate, optimized for context efficiency
**Last Updated:** 2025-11-16
