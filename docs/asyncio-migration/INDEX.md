# ExaBGP AsyncIO Migration - Documentation Index

**Quick Navigation:** Find exactly what you need in the AsyncIO migration documentation.

---

## Start Here

### For Understanding the Code

1. **[async-architecture.md](async-architecture.md)** ⭐ **Start here for code understanding**
   - How the async implementation works
   - Dual-mode reactor pattern
   - Event loop integration details
   - API process communication (critical component)
   - Message flow and concurrency model
   - **Audience:** Developers who need to understand or modify async code

2. **[technical/api-integration.md](technical/api-integration.md)** ⭐ **Critical component**
   - Deep dive into API process integration
   - Why `loop.add_reader()` is essential
   - Detailed flow diagrams
   - Common issues and solutions
   - **Audience:** Developers working on API integration

### For Migration History

3. **[README.md](README.md)** - Complete migration overview
   - Timeline and phases
   - What was built
   - How to use async mode
   - Testing results and statistics

4. **[overview/completion.md](overview/completion.md)** - Final completion summary
   - Root cause discovery (zombie processes!)
   - 100% test parity achievement
   - Key insights and lessons

### Quick Reference

5. **[overview/progress.md](overview/progress.md)** - Detailed timeline
   - Phase-by-phase progress
   - Test results at each step
   - Commit history

---

## Documentation Organization

### overview/

**Migration timeline and results:**

| File | Description |
|------|-------------|
| [COMPLETION.md](overview/completion.md) | Final completion summary, root cause discovery |
| [PROGRESS.md](overview/progress.md) | Complete migration timeline, metrics, decisions |

### phases/

**Phase-by-phase documentation:**

| Phase | File | Description |
|-------|------|-------------|
| Phase 1 | [PHASE_1.md](phases/phase-1.md) | Async I/O foundation (connection layer) |
| Phase A | [PHASE_A.md](phases/phase-a.md) | Minimal async conversion (protocol/peer methods) |
| Phase 2 PoC | [PHASE_2_POC.md](phases/phase-2-poc.md) | Proof of concept testing (decided to continue differently) |
| Phase B | [PHASE_B.md](phases/phase-b.md) | Full async architecture implementation |

**Note:** Phase 0 (API handler conversion) documentation is in archive/ as it was an early phase.

### technical/

**Deep technical documentation:**

| File | Description | Importance |
|------|-------------|------------|
| [API_INTEGRATION.md](technical/api-integration.md) | ⭐ API process integration with `loop.add_reader()` | **Critical** |
| [ARCHITECTURE_COMPARISON.md](technical/architecture-comparison.md) | Sync vs async architecture comparison | High |
| [CONVERSION_PATTERNS.md](technical/conversion-patterns.md) | Generator to async/await patterns | High |
| [GENERATOR_INVENTORY.md](technical/generator-inventory.md) | Complete generator analysis | Medium |
| [LESSONS_LEARNED.md](technical/lessons-learned.md) | Key insights and discoveries | Medium |

### sessions/

**Development session summaries:**

| File | Description |
|------|-------------|
| [PHASE_B_SESSION_SUMMARY.md](sessions/phase-b-session-summary.md) | Phase B Part 1 - Initial peer layer work |
| [PHASE_B_PART2_SESSION_SUMMARY.md](sessions/phase-b-part2-session-summary.md) | Phase B Part 2 - Async event loop |
| [SESSION_SUMMARY_IO_OPTIMIZATION.md](sessions/session-summary-io-optimization.md) | I/O layer cleanup session |
| [OPTION_A_SESSION_SUMMARY.md](sessions/option-a-session-summary.md) | Connection async implementation |
| [TIMEOUT_FIX_SESSION_SUMMARY.md](sessions/timeout-fix-session-summary.md) | API blocker discovery |

### archive/

**Historical documentation from earlier attempts:**

| File | Description |
|------|-------------|
| [ASYNC_MIGRATION_PLAN.md](archive/async-migration-plan.md) | Original migration plan |
| [MIGRATION_SUMMARY.md](archive/migration-summary.md) | Early migration summary |
| [MIGRATION_PROGRESS.md](archive/migration-progress.md) | Phase 0 progress tracking |
| [generator_analysis.md](archive/generator_analysis.md) | Early generator analysis |
| [HYBRID_IMPLEMENTATION_PLAN.md](archive/hybrid-implementation-plan.md) | Hybrid approach planning |
| [MIGRATION_STRATEGY.md](archive/migration-strategy.md) | Strategy documentation |

---

## Reading Paths

### Path 1: I Need to Understand the Code

**Goal:** Understand how async mode works so I can work with the code.

1. Read **[async-architecture.md](async-architecture.md)** - Core architecture and patterns
2. Read **[technical/api-integration.md](technical/api-integration.md)** - Critical API integration
3. Read **[technical/conversion-patterns.md](technical/conversion-patterns.md)** - Code patterns
4. Skim **[technical/architecture-comparison.md](technical/architecture-comparison.md)** - Sync vs async
5. Reference source code in `src/exabgp/reactor/`

**Time:** 2-3 hours

### Path 2: I Need Migration History

**Goal:** Understand why changes were made and how we got here.

1. Read **[README.md](README.md)** - Complete migration overview
2. Read **[overview/completion.md](overview/completion.md)** - Final results and discoveries
3. Skim **[overview/progress.md](overview/progress.md)** - Detailed timeline
4. Review phase docs in **[phases/](phases/)** as needed

**Time:** 1-2 hours

### Path 3: I'm Debugging an Issue

**Goal:** Find solutions to specific problems.

1. Check **[technical/api-integration.md](technical/api-integration.md)** - "Common Issues" section
2. Check **[technical/lessons-learned.md](technical/lessons-learned.md)** - Known pitfalls
3. Review **[async-architecture.md](async-architecture.md)** - "Error Handling" section
4. Search session summaries in **[sessions/](sessions/)** for similar issues

**Time:** 30-60 minutes

### Path 4: I Want to Use Async Mode

**Goal:** Run ExaBGP in async mode.

1. Read **[README.md](README.md)** - "How to Use Async Mode" section
2. Read **[README.md](README.md)** - "Quick Reference" section
3. Try it: `exabgp_asyncio_enable=true ./sbin/exabgp your-config.conf`
4. If issues, see Path 3 (Debugging)

**Time:** 15-30 minutes

### Path 5: I Want to Modify Async Code

**Goal:** Add features or fix bugs in async implementation.

1. Read **[async-architecture.md](async-architecture.md)** - Complete understanding
2. Read **[technical/api-integration.md](technical/api-integration.md)** - If touching API code
3. Read **[technical/conversion-patterns.md](technical/conversion-patterns.md)** - Follow patterns
4. Review relevant source files in `src/exabgp/reactor/`
5. Write tests, follow existing patterns
6. Run full test suite before committing

**Time:** 3-4 hours (initial), then as needed

---

## Key Concepts Quick Reference

### Dual-Mode Pattern

```python
# Sync mode (default)
def run(self):
    # Generator-based

# Async mode (opt-in)
async def run_async(self):
    # Async/await based
```

**Controlled by:** `exabgp_asyncio_enable` environment variable

**See:** [async-architecture.md#dual-mode-design-pattern](async-architecture.md#dual-mode-design-pattern)

### API FD Integration

```python
# Register FD with event loop
loop.add_reader(fd, callback, args)

# Callback fires when data available
def callback(args):
    data = os.read(fd, size)
    queue.append(data)
```

**Critical for:** API process communication in async mode

**See:** [technical/api-integration.md](technical/api-integration.md)

### Conversion Patterns

```python
# Generator pattern
def method(self):
    for item in items:
        yield ACTION.NOW

# Async pattern
async def method_async(self):
    for item in items:
        await asyncio.sleep(0)
```

**See:** [technical/conversion-patterns.md](technical/conversion-patterns.md)

---

## Files by Importance

### Critical (Read These)

1. **[async-architecture.md](async-architecture.md)** - How it works
2. **[technical/api-integration.md](technical/api-integration.md)** - Critical component
3. **[README.md](README.md)** - Overview and usage

### Important (Reference These)

4. **[technical/conversion-patterns.md](technical/conversion-patterns.md)** - Code patterns
5. **[overview/completion.md](overview/completion.md)** - Final results
6. **[technical/architecture-comparison.md](technical/architecture-comparison.md)** - Sync vs async

### Historical (Optional)

7. **[overview/progress.md](overview/progress.md)** - Timeline
8. **[phases/*.md](phases/)** - Phase documentation
9. **[sessions/*.md](sessions/)** - Session summaries
10. **[archive/*.md](archive/)** - Historical docs

---

## Search Tips

### Finding Topics

**For architecture questions:**
```bash
grep -r "event loop" docs/asyncio-migration/technical/
```

**For error handling:**
```bash
grep -r "exception\|error" docs/asyncio-migration/async-architecture.md
```

**For API integration:**
```bash
grep -r "add_reader\|API" docs/asyncio-migration/technical/
```

**For specific phases:**
```bash
ls docs/asyncio-migration/phases/
```

### Key Terms

- **Dual-mode:** Sync and async implementations side-by-side
- **FD integration:** File descriptor registration with event loop
- **loop.add_reader():** AsyncIO method for monitoring file descriptors
- **Generator bridge:** Pattern to connect callbacks with generators
- **Zombie processes:** Leftover test processes that caused false failures

---

## Contributing

### When Adding Documentation

1. **Technical docs** → `technical/`
2. **Migration history** → `archive/`
3. **Usage guides** → Update `README.md`
4. **Specific issues** → Add to relevant file or create new technical doc

### Documentation Standards

- **Code examples:** Use triple backticks with language
- **Diagrams:** Use ASCII art or mermaid
- **Links:** Use relative links within docs
- **Sections:** Use clear heading hierarchy
- **Audience:** State who the doc is for upfront

---

## FAQ

### Q: Where do I start to understand the code?

**A:** Read **[async-architecture.md](async-architecture.md)** first, then **[technical/api-integration.md](technical/api-integration.md)**.

### Q: How do I use async mode?

**A:** Set `exabgp_asyncio_enable=true` and run normally. See **[README.md#how-to-use-async-mode](README.md#how-to-use-async-mode)**.

### Q: Why did some tests fail before completion?

**A:** Zombie processes from previous runs. See **[overview/completion.md#root-cause-discovery](overview/completion.md#root-cause-discovery)**.

### Q: What's the most important technical component?

**A:** API FD integration using `loop.add_reader()`. See **[technical/api-integration.md](technical/api-integration.md)**.

### Q: Where's the migration timeline?

**A:** See **[overview/progress.md](overview/progress.md)** for complete timeline.

### Q: What conversion patterns were used?

**A:** See **[technical/conversion-patterns.md](technical/conversion-patterns.md)** for all patterns.

### Q: How do I debug async mode issues?

**A:** See **[async-architecture.md#error-handling](async-architecture.md#error-handling)** and **[technical/api-integration.md#common-issues-and-solutions](technical/api-integration.md#common-issues-and-solutions)**.

---

## Document Statistics

| Category | Files | Total Lines |
|----------|-------|-------------|
| Overview | 2 | ~1,500 |
| Phases | 4 | ~2,000 |
| Technical | 5 | ~2,500 |
| Sessions | 5 | ~2,000 |
| Archive | 10 | ~3,000 |
| Main Docs | 3 | ~2,000 |
| **Total** | **29** | **~13,000** |

---

## Quick Links

- [Main README](README.md)
- [Architecture Guide](async-architecture.md)
- [API Integration](technical/api-integration.md)
- [Conversion Patterns](technical/conversion-patterns.md)
- [Completion Summary](overview/completion.md)
- [Source Code](../../src/exabgp/reactor/)

---

**Last Updated:** 2025-11-17
**Documentation Version:** 1.0
**Status:** Complete
