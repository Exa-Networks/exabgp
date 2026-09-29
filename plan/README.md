# ExaBGP Plans Directory

## Quick Status

| Item | Status | Notes |
|------|--------|-------|
| Unit Tests | 3,404 | +149 since last update |
| Test Coverage | ~60% | Target: 60%+ |
| MyPy Errors | 244 | Mostly in `cli/completer.py` |
| TODO/FIXME Comments | 15 | Valid feature gaps/tech debt markers |
| AsyncIO Mode | Phase 2 | 100% test parity, not default yet |

---

## Current Plans

### Active (wip-)

| Plan | Description |
|------|-------------|
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
| `plan-asn-conversion-refactor.md` | Consolidate ASN handling in aspath/aggregator |
| `plan-extended-community-types.md` | Missing extended community types |
| `plan-flowspec-improvements.md` | FlowSpec AFI/EOL bits refactoring |
| `plan-validation-improvements.md` | Data validation enhancements |
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
| `plan-llgr.md` | Long-Lived Graceful Restart (RFC 9494, issue #292) |
| `plan-mypyc.md` | Compile the hot path with mypyc, pure Python kept as reference |
| `plan-connection-reader-removal.md` | Delete the dead sync `Connection.reader()`, retarget 68 test calls (before mypyc phase 7) |
| `plan-gtsm-shared-listener.md` | `incoming-ttl` on a listening socket shared by several neighbours |
| `plan-agent-instructions.md` | AGENTS.md, evidence rule, plan journal, `.claude/backups` cleanup (decisions needed) |
| `plan-multisession.md` | Cisco code 131 (fixed); one session per family (main fixed, 5.0 won't fix) |
| `wip-flowspec-wide-value.md` | One-octet flow components decoded from a wider value crash on `pack()` |

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
| Add Class Documentation | ~60% of classes lack docstrings (improved from 94%) |
| Refactor NLRI Duplication | 186+ lines of duplicated code |
| Consolidate Test Fixtures | Reduce fixture duplication |
| Performance Regression Tests | pytest-benchmark integration |
| Cache Compiled Regexes | Performance improvement |
| Community Caching | Re-add community object caching in config parsing |

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
| `done-large-function-decomposition.md` | 2026-09-29 | The ten largest functions split, `long_function` 69 → 58 |
| `done-rfc9234-roles-otc.md` | 2026-09-29 | BGP Roles and OTC, ingress insertion included; outcome note added, cleanup moved on |
| `done-dns-domain-name.md` | 2026-09-29 | `domain()` returned the host label; fixed, never reached the wire |
| `done-testing-gaps.md` | 2026-09-29 | Gaps #1425/#1426 exposed; RIB cache and DNS cache leaking between tests |
| `done-attribute-json-signature.md` | 2026-09-29 | `Attribute.json(*args, **kwargs)` typed as `json(compact: bool = False)`; dead `multiple` branches removed |
| `done-review-quality-sweep.md` | 2026-09-29 | In depth review: RFC 7606/8669 fixes, CLI exit codes, GTSM, ADD-PATH decode, RFC ledger; open items moved to their own plans |
| `done-hostname-length.md` | 2026-09-29 | HostName truncation split UTF-8 characters, Software length counted characters; 64 byte cap kept |
| `done-cve-exa-style-followup.md` | 2026-09-29 | GHSA-jcrv-p53f-v5w5 follow-up: the rest of the CWE-116 class, 19 findings across the API stream |
| `done-config-grammar.md` | 2026-09-29 | The configuration grammar replaces the hand parsers; syntax, man page, wiki, JSON Schema and YANG from it |
| `done-route-refresh-length.md` | 2026-09-29 | RFC 7313 5 Invalid Message Length was answered 1/2 by the header check; now 7/1 |
| `done-message-interface.md` | 2026-09-29 | One tested contract for every BGP message class; Notify by composition, Operational bytes-first |
| `done-rfc-gap-fixes.md` | 2026-09-29 | Every RFC ledger gap outside multisession closed: 8 areas, from outgoing policy to BGP-LS |
| `done-route-refresh-borr.md` | 2026-09-27 | Received End-of-RIB reset the session; RFC 7313 section 4 BoRR/EoRR |
| `done-unsent-notifications.md` | 2026-09-27 | (2,7) via `capability require`, (6,1) via `family prefix-limit`, RFC 4486 enrolled |
| `done-notification-text.md` | 2026-09-27 | NOTIFICATION names per IANA, RFC-defined Data field, wrong subcodes, API teardown |
| `done-paths-limit.md` | 2026-09-09 | PATHS-LIMIT capability (#1218): enforcement across batches, bounded audit, wire test |
| `done-attribute-cache-per-session.md` | 2026-08-22 | Attribute cache was process-wide and ignored negotiated state; scoped to the session |
| `done-read-cancellation-desync.md` | 2026-08-22 | A read cancelled by the 100ms deadline lost its bytes and desynced the session |
| `done-code-docstrings.md` | 2025-12-16 | Module/class docstrings for 15 core files |
| `done-claude-code-improvements.md` | 2025-12-16 | Auto-linter hook, /validate, /review commands |
| `done-runtime-validation/` | 2025-12-16 | Runtime crash prevention (BGP-LS complete) |
| `done-comment-cleanup/` | 2025-12-15 | XXX/TODO comment cleanup (Phase 1-7) |
| `done-nlri-immutability.md` | 2025-12-15 | NLRI immutability - remove nexthop from NLRI |
| `done-rib-testing-comprehensive.md` | 2025-12-15 | 230 new RIB tests (8 files, P0-P3 complete) |
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
| Active (in progress) | `wip-` | `wip-feature-name.md` |
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

**Updated:** 2025-12-16
