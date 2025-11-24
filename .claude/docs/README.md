# ExaBGP Documentation

**Location:** `.claude/docs/`

Project documentation for completed work, historical development, plans, and reference materials.

**For AI assistant instructions:** See `.claude/` (protocols) and `.claude/exabgp/` (codebase reference)
**For active work in progress:** See `wip/` subdirectory (this location)

**⚠️ Before creating docs:** Read `.claude/DOCUMENTATION_PLACEMENT_GUIDE.md`

---

## Structure

### `projects/` - Completed Work

All completed project documentation organized by project name.

**Major projects:**
- **asyncio-migration/** - Dual-mode sync/async architecture (✅ complete)
- **type-annotations/** - Type annotation work (🔄 in progress, active: `../wip/`)
- **claude-directory-organization/** - Documentation structure (✅ complete)

**Refactorings:**
- **pack-method-standardization/** - Utility pack() method renaming (✅ complete)
- **rfc-alignment/** - RFC-compliant method naming (✅ complete)
- **cli-dual-transport/** - CLI transport improvements (✅ complete)

**Infrastructure:**
- **testing-improvements/** - Testing infrastructure enhancements (✅ complete)

**Superseded:**
- **incremental-pack-rename/** - Alternative approach (not used)
- **extended-community-api-improvements/** - API improvements

**See:** `projects/README.md` for complete project list and details

---

### `reference/` - API & Reference Docs

Reference documentation and API guides.

**Contains:**
- **NEIGHBOR_SELECTOR_SYNTAX.md** - Neighbor selector syntax reference

---

### `plans/` - Future Implementation Plans

Future implementation plans and proposals.

**Currently empty** - active plans should be tracked in `../wip/`

---

### `wip/` - Active Work In Progress

Work currently being developed. Moves to `projects/` when complete.

**Contains:**
- **type-annotations/** - Type annotation work (Phase 3)

---

### `archive/` - Superseded Work

Superseded or obsolete experiments.

**Contains:**
- **api-peer-mgmt/** - Early API peer management experiments
- **cli-enhancement/** - Early CLI enhancement attempts
- **dual-transport/** - Dual transport exploration

---

## Documentation Patterns

**Each project directory contains:**
- `README.md` - Overview, status, context
- `plan.md` - Original planning document (if applicable)
- `status.md` - Completion status (if applicable)
- `progress.md` - Historical progress (if applicable)
- `analysis.md` - Technical analysis (if applicable)
- Subdirectories as needed (archive/, technical/, etc.)

**No loose .md files:** All documentation must be in subdirectories for organization.

---

## Adding New Documentation

When completing work from `wip/`:

1. Create `projects/<project-name>/` directory
2. Move/create appropriate documentation files
3. Add `README.md` with project overview and status
4. Update `projects/README.md` index
5. Remove from `wip/` or update to point to completed docs

---

## Separation of Concerns

**`.claude/`** = AI assistant instructions + codebase reference
- Protocols: How to write code, git workflow, testing requirements
- Codebase reference (`exabgp/`): Architecture, patterns, BGP mappings
- Reference docs: Test architecture, file conventions

**`.claude/docs/`** = Project documentation (this directory)
- `projects/`: Completed projects and features
- `wip/`: Active work in progress
- `reference/`: API and reference documentation
- `plans/`: Future implementation plans (mostly empty, use wip/)
- `archive/`: Superseded experiments

---

**Last Updated:** 2025-11-24
