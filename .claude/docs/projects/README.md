# ExaBGP Projects

Completed and historical project documentation.

**Active work:** See `.claude/wip/` for in-progress projects.

---

## Major Projects

### AsyncIO Migration
**Location:** `asyncio-migration/`
**Status:** ✅ Complete - 100% test parity
**Summary:** Dual-mode architecture supporting both sync (generator-based) and async (asyncio-based) event loops

**Key docs:**
- `README.md` - Migration overview and usage
- `async-architecture.md` - How async mode works
- `technical/` - Deep technical documentation

---

## Infrastructure Improvements

### CLI Dual Transport
**Location:** `cli-dual-transport/`
**Status:** ✅ Complete
**Summary:** Implemented dual transport support for CLI (named pipes + Unix sockets). Both transports can run simultaneously with socket as default.

### Testing Improvements
**Location:** `testing-improvements/`
**Status:** ✅ Complete
**Summary:** Testing infrastructure improvements including logging, functional tests, coverage

### Type Annotations
**Location:** `type-annotations/`
**Status:** 🔄 In Progress (see `.claude/wip/type-annotations/`)
**Summary:** Adding comprehensive type annotations and MyPy validation

**Historical:** Planning docs from early phases
**Current:** Active work in `.claude/wip/type-annotations/`

---

## Adding Completed Projects

When finishing work from `.claude/wip/`:
1. Move project directory to `docs/projects/<project-name>/`
2. Add `README.md` with completion summary
3. Update this index
4. Link from active work to completed docs if ongoing
