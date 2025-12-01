# TODO

## Quick Items

- [x] Convert FSM.STATE to use `enum.IntEnum` (src/exabgp/bgp/fsm.py) ✅
  - Completed: Reduced from 50 lines to 15 lines
  - Benefits: Better type safety, cleaner code, automatic validation
  - All 1,955 tests pass including 87 FSM-specific tests

- [ ] Make async mode the default reactor
  - Current: Requires `exabgp_reactor_asyncio=true` flag
  - Target: Async by default, legacy mode opt-in
  - Status: AsyncIO Phase 2 complete (100% test parity)
  - See: CLAUDE.md "AsyncIO Support" section

---

## 🚨 Critical - Fix Immediately (Week 1-2)

**Overall Grade: B+ (6.7/10)** | Full audit: `~/.claude/plans/eventual-yawning-fox.md`

- [x] **1. Attribute Cache Size Limit** ✅
  - Analyzed: `Attributes.cache` (line 60) was unused dead code - removed
  - `Attribute.cache` already uses `util/cache.py` with LRU eviction (max 2000/type, 1hr TTL)
  - No DoS risk - cache was already bounded

- [x] **2. Fix Blocking Write Deadlock** ✅
  - Fixed: c7b2f94d - Resolved sync mode write deadlock and partial write bug
  - Files: `src/exabgp/reactor/api/processes.py`

- [x] **3. Fix Known Race Conditions** ✅
  - Fixed: Config reload race (086b3ec1), RIB iterator/cache races (48e4405c)
  - Both commits merged to main

---

## ⚠️ High Priority - Next Sprint (Week 3-4)

- [x] **4. Add Application Layer Tests** ✅
  - Completed: c97702b9 - Added 112 new tests in 7 test files
  - Files: `tests/unit/application/` (test_healthcheck.py, test_validate.py, test_version.py, test_environ.py, test_decode_app.py, test_encode_app.py, test_main.py)
  - Coverage: FSM states, CLI argument parsing, encode/decode, subcommand dispatch

- [ ] **5. Refactor Giant Methods** (1 week)
  - Impact: Code comprehension and maintainability
  - Files:
    - `src/exabgp/reactor/peer.py:631` - `_main()` (386 lines)
    - `src/exabgp/configuration/configuration.py:125` - `__init__()` (222 lines)
    - `src/exabgp/reactor/loop.py:450` - `run()` (213 lines)
  - Solution: Extract method refactoring, state pattern for `_main()`

- [ ] **6. Add Class/API Documentation** (2 weeks ongoing)
  - Impact: Developer onboarding and code understanding
  - Current: 94.2% of classes lack docstrings (371 of 394)
  - Files: Start with reactor/, bgp/message/, configuration/
  - Target: 5.8% → 80% class docstring coverage
  - Guides: `.claude/DOCUMENTATION_WRITING_GUIDE.md`, `/review-docs <file>`

- [ ] **7. Implement Per-IP Connection Limits** (1-2 days)
  - Impact: DoS protection
  - Files: `src/exabgp/reactor/listener.py`
  - Solution: Track connections per IP, max 10 default

- [ ] **8. Fix Respawn Tracking Dict Leak** (1 day)
  - Impact: Memory leak in long-running processes
  - Files: `src/exabgp/reactor/api/processes.py:282-302`
  - Solution: Prune entries older than 1 hour

---

## 📋 Medium Priority - Next Quarter

- [ ] **9. Add Configuration System Tests** (1 week)
  - Target: 15% → 50% coverage
  - Files: Expand `tests/unit/configuration/`

- [ ] **10. Enable Coverage Reporting in CI** (4 hours)
  - Solution: Add Codecov/Coveralls upload to GitHub Actions

- [ ] **11. Add RIB Size Limits** (2-3 days)
  - Files: `src/exabgp/rib/`

- [ ] **12. Make Config Reload Async** (2-3 days)
  - Files: `src/exabgp/configuration/configuration.py:142`

- [ ] **13. Optimize Peer Lookup** (1 day)
  - Files: `src/exabgp/reactor/loop.py:332-348`
  - Solution: Dict for exact matches, fallback to iteration

- [ ] **14. Add Pre-commit Hooks** (2 hours)
  - Files: Create `.pre-commit-config.yaml`

- [ ] **15. Add Dependabot** (30 minutes)
  - Files: Create `.github/dependabot.yml`

- [ ] **16. Improve Error Path Cleanup** (3-5 days)
  - Files: Review all resource acquisition points

- [x] **17. Resolve Type Safety Issues** ✅
  - Fixed: 159db1cd - Removed all `type: ignore` comments
  - All 76 files cleaned up

- [ ] **18. Cache Compiled Regexes** (1 day)
  - Files: `src/exabgp/configuration/neighbor/parser.py:187`

- [x] **19. Use logging.dictConfig for Logging** ✅
  - Fixed: b389975b - Refactored to use `logging.config.dictConfig()`
  - Added `_get_syslog_address()` with FreeBSD support and socket check
  - Files: `src/exabgp/logger/handler.py`, `src/exabgp/logger/option.py`

---

## 🔧 Low Priority - Technical Debt

- [ ] **20. Refactor NLRI Duplication** (1 week)
  - Impact: Reduce 186+ lines of duplication
  - Files: 44 NLRI pack/unpack implementations

- [ ] **21. Consolidate Test Fixtures** (4 hours)
  - Files: `tests/unit/conftest.py`

- [ ] **22. Clean Up Legacy Files** (2 days)
  - Audit: `netlink/old.py`, 20 files with "deprecated"

- [ ] **23. Add Performance Regression Testing** (2 days)
  - Solution: pytest-benchmark in CI

- [ ] **24. Address TODO/FIXME Comments** (1 day triage)
  - Count: 48 comments (0.09% of codebase)
  - Create GitHub issues for each

---

## 📊 Audit Summary

**Key Weaknesses:**
- 94.2% of classes lack docstrings
- Giant methods (386-line `_main()`)
- Memory leaks in respawn tracking dict

**Strengths:**
- 50%+ unit test coverage (2,067 tests)
- Zero runtime dependencies (100% stdlib)
- Excellent CI/CD (8 GitHub Actions workflows)
- Active maintenance (recent type safety improvements)

**Full Details:** `~/.claude/plans/eventual-yawning-fox.md` (26KB comprehensive audit)

---

**Last Updated:** 2025-12-01
