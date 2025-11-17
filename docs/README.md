# ExaBGP Documentation

Project documentation for completed work, major features, and historical development.

**For AI assistant instructions:** See `.claude/` directory
**For active work in progress:** See `.claude/wip/` directory

---

## Structure

### `projects/`

All project documentation organized by project name.

**Major projects:**
- **asyncio-migration/** - Dual-mode sync/async architecture (✅ complete)
- **type-annotations/** - Type annotation work (🔄 in progress, see `.claude/wip/`)

**Refactorings:**
- **pack-method-standardization/** - Utility pack() method renaming (✅ complete)
- **rfc-alignment/** - RFC-compliant method naming (✅ complete)
- **incremental-pack-rename/** - Alternative approach (superseded)

**Infrastructure:**
- **testing-improvements/** - Testing infrastructure enhancements (✅ complete)

**See:** `projects/README.md` for complete project list and details

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

When completing work from `.claude/wip/`:

1. Create `docs/projects/<project-name>/` directory
2. Move/create appropriate documentation files
3. Add `README.md` with project overview and status
4. Update `docs/projects/README.md` index
5. Link from active work (`.claude/wip/`) to completed docs if ongoing

---

## Separation of Concerns

**`.claude/`** = AI assistant instructions
- How to write code (protocols, standards, guides)
- What rules to follow (refactoring, git, testing)
- Communication styles and conventions

**`.claude/wip/`** = Active development work
- Current projects in progress
- Work not yet completed
- Updated frequently

**`docs/`** = Project documentation
- Completed projects and features
- Historical development records
- Technical documentation
- Updated when projects complete

---

**Last Updated:** 2025-11-17
