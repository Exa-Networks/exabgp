# AsyncIO Migration Documentation

**This directory is now for Claude Code reference only.**

**All comprehensive AsyncIO migration documentation has been moved to:**

## 📚 `docs/asyncio-migration/`

### Start Here:

1. **Code Understanding:** [`docs/asyncio-migration/async-architecture.md`](../../docs/asyncio-migration/async-architecture.md)
2. **Complete Guide:** [`docs/asyncio-migration/README.md`](../../docs/asyncio-migration/README.md)
3. **Documentation Index:** [`docs/asyncio-migration/INDEX.md`](../../docs/asyncio-migration/INDEX.md)

---

## Quick Links

### For Developers

- [How Async Works](../../docs/asyncio-migration/async-architecture.md) - Complete technical guide
- [API Integration](../../docs/asyncio-migration/technical/api-integration.md) - Critical component deep dive
- [Conversion Patterns](../../docs/asyncio-migration/technical/conversion-patterns.md) - Code patterns reference

### For Users

- [How to Use Async Mode](../../docs/asyncio-migration/README.md#how-to-use-async-mode)
- [Quick Reference](../../docs/asyncio-migration/README.md#quick-reference)
- [Testing](../../docs/asyncio-migration/README.md#testing-results)

### For Project History

- [Migration Timeline](../../docs/asyncio-migration/overview/progress.md)
- [Completion Summary](../../docs/asyncio-migration/overview/completion.md)
- [Phase Documentation](../../docs/asyncio-migration/phases/)

---

## What's in This Directory (.claude/asyncio-migration/)

This directory contains **working notes and raw documentation** created during the migration. These files are kept for:

1. **Claude Code context** - Helps Claude understand the migration work
2. **Historical reference** - Original development notes
3. **Session continuity** - Tracks development sessions

**For actual documentation, always refer to `docs/asyncio-migration/`.**

---

## Files Here vs. docs/

| File Location | Purpose | Audience |
|---------------|---------|----------|
| `.claude/asyncio-migration/` | Claude Code working notes, raw documentation | Claude Code |
| `docs/asyncio-migration/` | Polished documentation, organized by topic | Humans (developers, users) |

---

## Migration Status

✅ **COMPLETE** - 100% test parity achieved (2025-11-17)

- Sync mode: 72/72 tests (100%)
- Async mode: 72/72 tests (100%)
- Unit tests: 1376/1376 (100%)
- Zero regressions

**See:** [`docs/asyncio-migration/overview/completion.md`](../../docs/asyncio-migration/overview/completion.md)

---

## How to Use Async Mode

```bash
# Enable async mode
export exabgp_asyncio_enable=true

# Run ExaBGP
./sbin/exabgp ./etc/exabgp/your-config.conf
```

**Full details:** [`docs/asyncio-migration/README.md`](../../docs/asyncio-migration/README.md)

---

## Quick Claude Code Reference

When working on async code, Claude should refer to:

### Understanding Code

```
docs/asyncio-migration/async-architecture.md - How it works
docs/asyncio-migration/technical/api-integration.md - Critical API component
docs/asyncio-migration/technical/conversion-patterns.md - Code patterns
```

### Key Concepts

**Dual-Mode Pattern:**
- Sync: `run()` uses generators
- Async: `run_async()` uses async/await
- Controlled by `exabgp_asyncio_enable` env var

**API Integration:**
- Uses `loop.add_reader(fd, callback)` for event-driven I/O
- Critical for async mode to work with external processes
- See `docs/asyncio-migration/technical/api-integration.md`

**Code Locations:**
- Reactor: `src/exabgp/reactor/loop.py`
- Peer FSM: `src/exabgp/reactor/peer.py`
- Protocol: `src/exabgp/reactor/protocol.py`
- Connection: `src/exabgp/reactor/network/connection.py`
- API Processes: `src/exabgp/reactor/api/processes.py` (critical!)

---

**Always refer developers to `docs/asyncio-migration/` for complete documentation.**

**Last Updated:** 2025-11-17
