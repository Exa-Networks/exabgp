# TODO

## Quick Items

- [ ] Convert FSM.STATE to use `enum.IntEnum` (src/exabgp/bgp/fsm.py)
  - Current: Custom `class STATE(int)` with ClassVar attributes
  - Target: Python's built-in `enum.IntEnum`
  - Effort: 30 min - 1 hour

- [ ] Make async mode the default reactor
  - Current: Requires `exabgp_reactor_asyncio=true` flag
  - Target: Async by default, legacy mode opt-in
  - Status: AsyncIO Phase 2 complete (100% test parity)
  - See: CLAUDE.md "AsyncIO Support" section

---

## Comprehensive Audit & Action Plan

**Full repository audit with 23 prioritized action items:**

📄 See: `.claude/plans/eventual-yawning-fox.md`

**Summary:**
- Overall Grade: B+ (6.7/10)
- 3 Critical fixes (Week 1-2)
- 5 High priority items (Week 3-4)
- 10 Medium priority items (Next quarter)
- 5 Low priority items (Technical debt)

**Top 3 Critical Items:**
1. Add attribute cache size limit (DoS risk)
2. Fix blocking write deadlock in sync mode
3. Fix known race conditions (config reload, RIB cache)

**Key Weaknesses:**
- 94.2% of classes lack docstrings
- Application layer: 0-35% test coverage
- Giant methods (386-line `_main()`)
- Memory leaks in caches/dicts

---

## Documentation Guides

**Writing documentation:**
- `.claude/DOCUMENTATION_WRITING_GUIDE.md` - Comprehensive guide for adding docstrings
- `.claude/commands/review-docs.md` - Slash command: `/review-docs <file>`

**Target:** 80% class docstring coverage (currently 5.8%)

---

**Last Updated:** 2025-12-01
