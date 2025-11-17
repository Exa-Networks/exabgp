# AsyncIO Migration Project

**Status:** Planning Phase
**Started:** 2025-11-16
**Approach:** Exploratory - start with easy wins, build patterns

---

## Quick Start

1. Read `CURRENT_ARCHITECTURE.md` - understand existing generator system
2. Read `MIGRATION_STRATEGY.md` - overall approach and phases
3. Read `CONVERSION_PATTERNS.md` - before/after examples
4. Track progress in `PROGRESS.md`

---

## Goals

Convert ExaBGP's custom generator-based async to Python asyncio:
- ✅ Phase 1.1 complete: ASYNC class supports both modes
- 🔄 Phase 0: Convert simple generators (3-5), establish patterns
- ⏳ Phase 1: Event loop integration (asyncio.run())
- ⏳ Phase 2: Medium complexity (network, protocol helpers)
- ⏳ Phase 3: Complex nested (API handlers)
- ⏭️ Parsing/config generators stay as-is

---

## Scope

**Converting:**
- ~80 generators across critical path
- API handlers, protocol, peer, network layers
- Estimated: 25-30 hours

**NOT converting:**
- Parsing generators (43) - work fine
- Config generators (35) - startup only
- Test generators (3) - stable

---

## Strategy

**Exploratory approach:**
1. Start with simplest single-yield generators
2. Build confidence and establish patterns
3. Document what works/doesn't
4. Progress to medium complexity
5. Finally tackle complex nested generators

**Following MANDATORY_REFACTORING_PROTOCOL:**
- ONE function at a time
- ALL tests must ALWAYS pass
- PASTE proof at every step

---

## Files in This Directory

| File | Purpose |
|------|---------|
| README.md | This file - overview and navigation |
| CURRENT_ARCHITECTURE.md | Existing generator system details |
| MIGRATION_STRATEGY.md | Detailed phase-by-phase plan |
| CONVERSION_PATTERNS.md | Code examples and patterns |
| GENERATOR_INVENTORY.md | Complete list of all generators |
| PROGRESS.md | Track completed work |

---

**Updated:** 2025-11-16
