# ExaBGP Documentation

**Location:** `.claude/docs/`

Project documentation for completed work, historical development, and reference materials.

**For AI assistant instructions:** See `.claude/` (protocols) and `.claude/exabgp/` (codebase reference)
**For active work plans:** See `plan/` directory (project root)

**Before creating docs:** Read `.claude/DOCUMENTATION_PLACEMENT_GUIDE.md`

---

## Active Work Plans

**All active project plans are now in `plan/` (project root):**

- `plan/todo.md` - Central TODO tracking
- `plan/packed-attribute.md` - Packed-bytes-first refactoring
- `plan/coverage.md` - Test coverage audit
- `plan/type-annotations/` - Type annotation detailed plans
- `plan/comment-cleanup/` - XXX comment cleanup (✅ Complete)

---

## Documentation Structure

```
docs/
├── projects/          Completed Projects
│   ├── asyncio-migration/    COMPLETE - Dual async/generator support
│   ├── cli-dual-transport/   COMPLETE - CLI socket transport
│   └── schema-validators-api-backpressure.md
├── archive/           Historical/Superseded
│   ├── asyncio-investigation-2025-11/
│   ├── testing-improvements/
│   ├── cli-enhancement/
│   ├── api-peer-mgmt/
│   └── dual-transport/
└── INDEX.md           Complete file listing
```

---

## `projects/` - Completed Work

All completed project documentation organized by project name.

**Completed projects:**
- **asyncio-migration/** - Dual-mode sync/async architecture (Phase 2: Production Validation)
- **cli-dual-transport/** - CLI Unix socket + stdio dual transport

**See:** `projects/README.md` for complete project list and details

---

## `archive/` - Superseded Work

Superseded or obsolete experiments.

**Contains:**
- **asyncio-investigation-2025-11/** - AsyncIO debugging sessions
- **testing-improvements/** - Early testing improvement work
- **api-peer-mgmt/** - Early API peer management experiments
- **cli-enhancement/** - Early CLI enhancement attempts
- **dual-transport/** - Dual transport exploration

---

## Documentation Patterns

**Each project directory contains:**
- `README.md` - Overview, status, context
- `plan.md` - Original planning document (if applicable)
- Technical documentation as needed

**No loose .md files:** All documentation must be in subdirectories for organization.

---

## Separation of Concerns

**`.claude/`** = AI assistant instructions + codebase reference
- Protocols: How to write code, git workflow, testing requirements
- Codebase reference (`exabgp/`): Architecture, patterns, BGP mappings
- Reference docs: Test architecture, file conventions

**`.claude/docs/`** = Completed project documentation (this directory)
- `projects/`: Completed projects and features
- `archive/`: Superseded experiments

**`plan/`** = Active work plans (project root)
- `todo.md`: Central TODO tracking
- Project-specific plans and progress

---

**Last Updated:** 2025-12-04
