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

## Refactorings

### Pack Method Standardization
**Location:** `pack-method-standardization/`
**Status:** ✅ Complete
**Summary:** Renamed utility `pack()` methods to `pack_<type>()` to avoid conflicts with BGP message packing

### RFC Alignment
**Location:** `rfc-alignment/`
**Status:** ✅ Complete
**Summary:** Renamed all `unpack()` methods to match RFC terminology

### ExtendedCommunity API Improvements
**Location:** `extended-community-api-improvements/`
**Status:** ✅ Complete
**Summary:** Removed unused `direction` parameter and converted to @classmethod pattern for better inheritance

### Incremental Pack Rename
**Location:** `incremental-pack-rename/`
**Status:** ✅ Complete
**Summary:** Incremental approach to pack method renaming

---

## Infrastructure Improvements

### Testing Improvements
**Location:** `testing-improvements/`
**Status:** ✅ Complete
**Summary:** Testing infrastructure improvements including logging, functional tests, coverage

### .claude Directory Organization
**Location:** `claude-directory-organization/`
**Status:** ✅ Complete
**Summary:** Optimized `.claude/` directory structure for AI assistants (76% size reduction, clear separation of protocols/active work/completed work)

### Type Annotations
**Location:** `type-annotations/`
**Status:** 🔄 In Progress (see `.claude/wip/type-annotations/`)
**Summary:** Adding comprehensive type annotations and MyPy validation

**Historical:** Planning docs from early phases
**Current:** Active work in `.claude/wip/type-annotations/`

---

## Project Structure Pattern

Each project directory contains:
- `README.md` - Overview, status, context
- `plan.md` - Original planning document (if applicable)
- `status.md` - Completion status (if applicable)
- `progress.md` - Historical progress tracking (if applicable)
- `analysis.md` - Technical analysis (if applicable)
- Subdirectories as needed

---

## Adding Completed Projects

When finishing work from `.claude/wip/`:
1. Move project directory to `docs/projects/<project-name>/`
2. Add `README.md` with completion summary
3. Update this index
4. Link from active work to completed docs if ongoing
