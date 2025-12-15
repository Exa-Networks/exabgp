# ExaBGP Plans Directory

## Quick Status

| Item | Status | Notes |
|------|--------|-------|
| Unit Tests | 3,223 | Up from 2,540 (Dec 3) |
| Test Coverage | ~60% | Target: 60%+ |
| MyPy Errors | 244 | Mostly in `cli/completer.py` |
| TODO/FIXME Comments | 33 | Down from 48 |
| AsyncIO Mode | Phase 2 | 100% test parity, not default yet |

---

## Current Plans

### Active (wip-)

| Plan | Description |
|------|-------------|
| `wip-nlri-immutability.md` | Phase 4 steps 6-7 remaining (remove nexthop from NLRI) |
| `comment-cleanup/` | XXX/TODO comment cleanup (Phase 6-7) |
| `runtime-validation/` | Runtime crash prevention (BGP-LS done) |
| `type-safety/` | MyPy error reduction |

### Planning (plan-)

| Plan | Description |
|------|-------------|
| `plan-github-setup-improvements.md` | GitHub templates, SECURITY.md, PR template |
| `plan-fix-resolve-self-deepcopy.md` | Fix resolve_self() memory duplication |
| `plan-rib-optimisation.md` | RIB memory optimization |
| `plan-announce-cancels-withdraw-optimization.md` | Re-add announce-cancels-withdraw optimization |
| `plan-coverage.md` | Test coverage audit (metrics stale) |
| `plan-update-context-attachment.md` | Global Update cache with SHA256 IDs |
| `plan-type-identification-review.md` | hasattr() → ClassVar review |
| `plan-addpath-nlri.md` | ADD-PATH for more NLRI types |
| `plan-architecture.md` | Circular dependency fixes |
| `plan-code-quality.md` | Misc improvements (low priority) |
| `plan-rib-improvement-proposals.md` | RIB improvement ideas (discussion) |
| `plan-security-validation.md` | Security validation |
| `plan-from-settings-config.md` | from_settings() for Configuration/Neighbor |
| `plan-neighbor-naming.md` | User-defined neighbor names/aliases |
| `plan-optional-trailing-semicolon.md` | Make trailing semicolons optional |
| `plan-mup-json-name-format.md` | API v6 MUP naming |
| `plan-api-v6-nexthop-removal.md` | Remove nexthop from NLRI JSON |
| `plan-documentation-review.md` | Documentation review |

### Completed (done-) and Directories

| Plan | Description |
|------|-------------|
| `packed-bytes/` | Packed-bytes-first pattern (architecture) |
| `done-*.md` | See "Recently Completed Plans" below |

---

## Unplanned Work Items

### High Priority

| Item | Description | File(s) |
|------|-------------|---------|
| Refactor Giant Methods | peer.py (951 lines), configuration.py (809 lines), loop.py (604 lines) | `reactor/peer/peer.py`, `configuration/configuration.py`, `reactor/loop.py` |
| Per-IP Connection Limits | DoS protection | `reactor/listener.py` |
| Respawn Dict Leak | `_respawning` dict never cleaned | `reactor/api/processes.py:310-331` |
| Runtime Validation Phase 3-4 | NLRI types and Protocol layer | See `runtime-validation/TODO.md` |

### Medium Priority

| Item | Description |
|------|-------------|
| Make AsyncIO Default | Currently opt-in with `exabgp_reactor_asyncio=true` |
| Coverage Reporting in CI | Codecov/Coveralls integration |
| RIB Size Limits | Prevent unbounded memory growth |
| Async Config Reload | Non-blocking reload |
| Pre-commit Hooks | Automated linting on commit |
| Dependabot | Automated dependency updates |

### Low Priority (Technical Debt)

| Item | Description |
|------|-------------|
| Add Class Documentation | 94.2% of classes lack docstrings |
| Refactor NLRI Duplication | 186+ lines of duplicated code |
| Consolidate Test Fixtures | Reduce fixture duplication |
| Performance Regression Tests | pytest-benchmark integration |
| Cache Compiled Regexes | Performance improvement |

---

## Completed (2025)

### Major Completions

| Item | Date | Description |
|------|------|-------------|
| Action Enum Refactor | 2025-12-15 | Type-safe enums for configuration actions |
| BGP-LS RFC Naming | 2025-12-11 | Renamed 9 classes to match IANA/RFC |
| BGP-LS Packed-Bytes | 2025-12-12 | Packed-bytes-first + MERGE refactor |
| Int Validator Factory | 2025-12-11 | Factory pattern for integer validation |
| API Command Encoder | 2025-12-10 | cmd: field support in tests (349/349) |
| Packed-Bytes Pattern | 2025-12-04 | Architecture done (~124 classes store `_packed`) |
| Wire vs Semantic Separation | 2025-12-08 | Update/Attributes containers |
| Change → Route Refactoring | 2025-12 | Renamed across 36 files |
| Buffer Protocol Audit | 2025-12-15 | bytes→Buffer migration (117 files, 250 replacements) |
| Python 3.12+ Buffer Protocol | 2025-12 | Zero-copy with `recv_into()`, `memoryview` |
| FSM.STATE IntEnum | 2025-12 | Converted to IntEnum |
| Type Safety Issues | 2025-12 | Removed all `type: ignore` |

### Critical Fixes (2025)

- Attribute Cache Size Limit - Removed unused dead code
- Blocking Write Deadlock - c7b2f94d
- Race Conditions - Config reload, RIB iterator/cache
- Application Layer Tests - 112 new tests
- Logging dictConfig - b389975b
- netlink/old.py - Cleaned up (file removed)

---

## Recently Completed Plans (delete after 30 days)

| Plan | Completed | Description |
|------|-----------|-------------|
| `done-buffer-protocol-audit.md` | 2025-12-15 | Migrate bytes→Buffer (117 files, 250 replacements) |
| `done-action-enum-refactor.md` | 2025-12-15 | Replace action= strings with type-safe enums |
| `done-bgpls-rfc-naming.md` | 2025-12-11 | Rename BGP-LS classes to match RFC/IANA |
| `done-bgpls-packed-bytes-first.md` | 2025-12-12 | BGP-LS packed-bytes-first + MERGE refactor |
| `done-int-validator-factory.md` | 2025-12-11 | Factory pattern for integer validation |
| `done-api-command-encoder.md` | 2025-12-10 | cmd: field support in .ci test files |
| `done-from-settings-conversion.md` | 2025-12-11 | Programmatic config API + route indexing |
| `done-raw-attribute-api-v4.md` | 2025-12-10 | Generic attribute round-trip for all families |
| `done-api-group-command.md` | 2025-12-10 | Batch commands into single UPDATE |

---

## Naming Convention

### File Naming Rules

| Status | Prefix | Example |
|--------|--------|---------|
| Active (in progress) | `wip-` | `wip-nlri-immutability.md` |
| Planning (not started) | `plan-` | `plan-addpath-nlri.md` |
| Completed | `done-` | `done-action-enum-refactor.md` |
| On Hold | `hold-` | `hold-async-migration.md` |

**Other rules:**
- Use kebab-case: `wip-buffer-protocol-audit.md`
- Keep names short: 2-4 words max
- Be descriptive: name should hint at the goal

**When status changes:**
- Started work: `git mv plan-foo.md wip-foo.md`
- Completed: `git mv wip-foo.md done-foo.md`
- On hold: `git mv wip-foo.md hold-foo.md`

**Cleanup:** Periodically delete `done-*.md` files older than 30 days.

### Status Emojis (in file headers)

| Emoji | Meaning |
|-------|---------|
| 🔄 | Active - work in progress |
| 📋 | Planning - not started |
| ✅ | Completed |
| ⏸️ | On Hold |

---

**Updated:** 2025-12-15
