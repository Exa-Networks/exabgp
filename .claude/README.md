# Claude AI Assistant Resources

Documentation and protocols for Claude Code interactions with ExaBGP.

---

## 🚨 START OF EVERY SESSION - READ ALL PROTOCOLS 🚨

**BEFORE doing ANYTHING, you MUST read ALL Core Protocols below.**

**NONE are optional. NONE are "nice to have". ALL are MANDATORY.**

You have NO memory between sessions - you MUST read them EVERY time.

**Start with these (apply to ALL interactions):**
1. **COMMUNICATION_STYLE.md** - How to communicate (terse, direct, emojis)
2. **EMOJI_GUIDE.md** - Which emojis to use and when
3. **GIT_VERIFICATION_PROTOCOL.md** - Check for pre-existing git changes

**Then READ THE REST below.**

**Then check git state:**
```bash
git status
git diff
git diff --staged
```

If ANY files modified/staged: ASK user how to handle before starting work.

---

## Core Protocols (ALL MANDATORY - READ EVERY SESSION)

| File | Purpose | Size |
|------|---------|------|
| **MANDATORY_REFACTORING_PROTOCOL.md** | Step-by-step verification for ALL refactoring | 3.7 KB |
| **ERROR_RECOVERY_PROTOCOL.md** | NEVER rush after mistakes - slow down and follow protocols | 2.2 KB |
| **GIT_VERIFICATION_PROTOCOL.md** | NEVER make git claims without fresh verification | 0.7 KB |
| **CODING_STANDARDS.md** | Python 3.8+ compatibility, type annotations, BGP APIs | 3.5 KB |
| **TESTING_DISCIPLINE.md** | NEVER claim success without testing ALL | 1.1 KB |
| **COMMUNICATION_STYLE.md** | Terse, direct communication. Use agents. | 2.1 KB |
| **EMOJI_GUIDE.md** | Systematic emoji usage for clarity | 1.8 KB |
| **PLANNING_GUIDE.md** | Standards for project planning docs | 1.5 KB |
| **CI_TESTING.md** | Complete testing requirements and commands | 3.2 KB |

**Total core protocols: ~20 KB**

---

## Active Work (`wip/`)

Active development projects. Completed work moves to `docs/projects/`.

### Type Annotations (`wip/type-annotations/`)
**Status:** Phase 3 - MyPy error reduction
**Progress:** 605 errors (47% ↓ from 1,149 baseline)

**Files:**
- README.md - Project overview
- MYPY_STATUS.md - Current error analysis
- PROGRESS.md - Phase tracking
- See full structure in `wip/type-annotations/`

**Historical docs:** `docs/projects/type-annotations/` (early planning)

---

## Completed Projects

**All completed work moved to:** `docs/projects/`

Major completed projects:
- AsyncIO Migration (100% test parity)
- Pack Method Standardization
- RFC Alignment
- Testing Improvements

**See:** `docs/projects/README.md` for full project list

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

**At session start:**
1. Read ALL Core Protocols above (ALL mandatory, see top of file)
2. Check `git status`, `git diff`, `git diff --staged`
3. If files modified: ASK user before proceeding

**For any code changes:**
1. Make changes following CODING_STANDARDS.md
2. Follow MANDATORY_REFACTORING_PROTOCOL.md if refactoring
3. Run ALL tests per TESTING_DISCIPLINE.md
4. Only THEN claim success

**Remember:**
- COMMUNICATION_STYLE.md + EMOJI_GUIDE.md apply to EVERY response
- GIT_VERIFICATION_PROTOCOL.md applies to EVERY git operation
- ERROR_RECOVERY_PROTOCOL.md applies when mistakes happen

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

## Recent Changes (2025-11-17)

✅ Reorganized documentation structure
✅ Created `wip/` for active work (clear separation from protocols)
✅ Moved all completed projects to `docs/projects/`
✅ Removed `archive/` directory (all content moved to appropriate locations)
✅ Added Git Verification Protocol (prevent false claims about repo state)
✅ No .md files directly in docs/ - all in subdirectories

**Previous (2025-11-16):**
✅ Compressed core protocols (59 KB → 14 KB, 77% ↓)
✅ Updated baselines (605 MyPy, 1376 tests)
✅ Total reduction: 640 KB → ~150 KB (76% ↓)

---

**Current Status:** ✅ Clean separation: protocols / active work / completed projects
**Last Updated:** 2025-11-17
