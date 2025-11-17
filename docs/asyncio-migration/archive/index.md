# Async Migration Reference Index

This folder contains all planning and reference documents for the generator to async/await migration.

---

## Primary Planning Documents

### 1. ASYNC_MIGRATION_PLAN.md
**The Master Plan** - Complete detailed plan with all 28 PRs

**Read this for:**
- Full PR-by-PR breakdown
- Detailed time estimates
- Testing strategy
- Risk mitigation
- Common conversion patterns (Appendix B)
- Session handoff protocols (Appendix D)

**Size:** ~12,000 words | **Read time:** 30-40 minutes

---

### 2. MIGRATION_QUICK_START.md
**Getting Started Guide** - How to begin immediately

**Read this for:**
- Pre-migration checklist
- Step-by-step PR #1 implementation
- Code examples for first changes
- Testing checklist
- Common issues & solutions

**Size:** ~3,000 words | **Read time:** 10-15 minutes

---

### 3. MIGRATION_PROGRESS.md
**Progress Tracker** - Live tracking document

**Update this:**
- After completing each PR
- At end of each session
- When tests run
- When blockers occur

**Contains:**
- Overall progress metrics
- Phase status
- PR completion checklist
- Session log
- Test results
- Handoff templates

---

### 4. MIGRATION_SUMMARY.md
**Executive Overview** - Quick reference

**Read this for:**
- Visual roadmap
- Quick facts and numbers
- Critical success factors
- Top 5 files to convert
- Document index
- Session workflow

**Size:** ~2,000 words | **Read time:** 5-10 minutes

---

## Supporting Analysis (Reference Only)

These files were generated during initial codebase analysis:

### generator_analysis.md
Location: `/tmp/generator_analysis.md`
- Comprehensive analysis of all 44 files with generators
- Categorized by module and purpose
- Code examples and patterns
- Architecture documentation
- ~12,000 words

### files_summary.txt
Location: `/tmp/files_summary.txt`
- Organized file listing by module
- Generator counts per file
- Priority rankings
- Quick statistics

### quick_reference.md
Location: `/tmp/quick_reference.md`
- 4-phase migration plan overview
- Timeline estimates
- Migration checklist
- Decision trees
- File priority reference

---

## How to Use This Reference

### Starting Out?
1. Read `MIGRATION_SUMMARY.md` (5 min) for overview
2. Read `MIGRATION_QUICK_START.md` (15 min) for instructions
3. Start PR #1 following the guide

### During Work?
1. Reference `ASYNC_MIGRATION_PLAN.md` for PR details
2. Update `MIGRATION_PROGRESS.md` as you go
3. Check conversion patterns in Plan Appendix B

### Between Sessions?
1. Update `MIGRATION_PROGRESS.md` with handoff notes
2. Document blockers and next steps
3. Review plan for next PR in sequence

### Need Quick Info?
1. `MIGRATION_SUMMARY.md` has the essentials
2. Check the visual roadmap
3. See the phase dependencies

---

## Current Status

**Last Updated:** 2025-11-08

**Phase:** Pre-Migration
**PRs Completed:** 0/28
**Generators Converted:** 0/150
**Current Task:** Review plan and run baseline tests

**Next Steps:**
1. Run baseline test suite
2. Create PR #1 branch
3. Start implementing PR #1 (Async Infrastructure)

---

## Quick Stats

- **Total Generator Functions:** 150
- **Files Affected:** 44 (41 production, 3 test)
- **PRs Planned:** 28 (23 required, 5 optional)
- **Phases:** 5
- **Estimated Time:** 40-60 hours
- **Test Files to Keep Stable:** 3

---

## Critical Reminders

### DO NOT MODIFY - Keep Stable
These test files must remain unchanged:
- `tests/unit/test_connection_advanced.py`
- `tests/fuzz/test_connection_reader.py`
- `tests/unit/test_route_refresh.py`

### Must Complete in Order
1. PR #1 → PR #2 → PR #3 (Infrastructure)
2. PR #4 → PR #5 → PR #6 (Announce)
3. PR #7 (Protocol)
4. PR #8 (Peer)

After that, PRs can be done in any order or parallel.

---

## PR Progress Checklist

### Phase 1: Infrastructure
- [ ] PR #1: Async Infrastructure
- [ ] PR #2: Event Loop
- [ ] PR #3: Test Utilities

### Phase 2: Critical Path
- [ ] PR #4: Announce Part 1
- [ ] PR #5: Announce Part 2
- [ ] PR #6: Announce Part 3
- [ ] PR #7: Protocol
- [ ] PR #8: Peer

### Phase 3: Supporting (10 PRs)
- [ ] PRs #9-18

### Phase 4: Parsing (5 PRs)
- [ ] PRs #19-23

### Phase 5: Utilities - Optional (5 PRs)
- [ ] PRs #24-28

---

## File Locations

### In Repository Root
```
/home/user/exabgp/
├── ASYNC_MIGRATION_PLAN.md
├── MIGRATION_QUICK_START.md
├── MIGRATION_PROGRESS.md
├── MIGRATION_SUMMARY.md
└── .github/
    └── PULL_REQUEST_TEMPLATE_ASYNC_MIGRATION.md
```

### In .claude/async-migration (This Folder)
```
/home/user/exabgp/.claude/async-migration/
├── INDEX.md (this file)
├── ASYNC_MIGRATION_PLAN.md (copy)
├── MIGRATION_QUICK_START.md (copy)
├── MIGRATION_PROGRESS.md (copy)
└── MIGRATION_SUMMARY.md (copy)
```

### Analysis Files
```
/tmp/
├── generator_analysis.md
├── files_summary.txt
├── quick_reference.md
└── INDEX.md
```

---

## Session Workflow Template

### Start of Session
```bash
# 1. Navigate to project
cd /home/user/exabgp

# 2. Check current status
cat .claude/async-migration/MIGRATION_PROGRESS.md | grep "Next Steps" -A 5

# 3. Pull latest
git pull origin claude/convert-generators-to-async-011CUwFUB42rVxbv6Uf6XFQw

# 4. Review plan for current PR
cat .claude/async-migration/ASYNC_MIGRATION_PLAN.md | grep "PR #X" -A 20
```

### During Session
- Follow PR instructions from ASYNC_MIGRATION_PLAN.md
- Update MIGRATION_PROGRESS.md as you complete tasks
- Run tests frequently

### End of Session
```bash
# 1. Update progress
vim .claude/async-migration/MIGRATION_PROGRESS.md

# 2. Commit work
git add .
git commit -m "[async-migration] PR #X: [description]"

# 3. Push to remote
git push origin [branch-name]

# 4. Document handoff
# Add session notes to MIGRATION_PROGRESS.md
```

---

## Quick Commands

### Run All Tests
```bash
PYTHONPATH=src python -m pytest tests/ -v
```

### Run with Coverage
```bash
PYTHONPATH=src python -m pytest tests/ -v --cov=src/exabgp
```

### Check Current Branch
```bash
git status
git branch
```

### View Recent Commits
```bash
git log --oneline -10
```

---

## Resources

- **Python Asyncio Docs:** https://docs.python.org/3/library/asyncio.html
- **PEP 492 (async/await):** https://peps.python.org/pep-0492/
- **Pytest-asyncio:** https://pytest-asyncio.readthedocs.io/

---

**This index last updated:** 2025-11-08
**Plan version:** 1.0
