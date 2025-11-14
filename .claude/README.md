# Claude AI Assistant Resources

This directory contains documentation and resources specifically for Claude Code AI assistant interactions with this repository.

---

## Directory Structure

```
.claude/
├── README.md                     # This file - directory overview
├── PLANNING_GUIDE.md             # How to structure planning documents
├── TESTING_DISCIPLINE.md         # Testing requirements
├── settings.local.json           # Local settings
│
├── docs/                         # General technical documentation
│   └── CI_TESTING_GUIDE.md       # CI testing requirements
│
├── type-annotations/             # Type annotation improvement project
│   ├── README.md
│   ├── ANY_REPLACEMENT_PLAN.md
│   ├── ANALYSIS.md
│   └── PROGRESS.md
│
└── archive/                      # Deprecated/superseded documentation
    ├── TYPE_ANNOTATION_PLAN.md
    ├── TYPE_ANNOTATION_PROGRESS.md
    └── ...
```

---

## Active Projects

### Type Annotations (`type-annotations/`)
Systematic replacement of `Any` type annotations with proper, specific types.

**Status:** Planning complete, ready to implement
**See:** `.claude/type-annotations/README.md`

---

## Documentation Files

### Root Level

- **`CODING_STANDARDS.md`** - **CRITICAL:** Python 3.8+ compatibility requirements, type annotation standards, and coding conventions. **READ THIS FIRST** before making any code changes.
- **`PLANNING_GUIDE.md`** - Standards for organizing planning documentation. Read this before creating new project plans.
- **`TESTING_DISCIPLINE.md`** - Testing requirements and discipline
- **`settings.local.json`** - Local configuration

### `/docs` Directory

General technical documentation:

- **`CI_TESTING_GUIDE.md`** - Comprehensive CI testing requirements including:
  - Linting requirements (ruff)
  - Unit tests (pytest)
  - Functional tests (encoding, parsing)
  - Legacy Python version support
  - Pre-merge checklist
  - Debugging tips

---

## Purpose

This directory helps Claude:
1. **Understand project structure** - Navigate and work with ExaBGP codebase
2. **Follow testing discipline** - Validate all changes before declaring them ready
3. **Organize planning work** - Keep project documentation well-structured
4. **Track progress** - Maintain clear records of ongoing work
5. **Provide accurate guidance** - Reference technical details and patterns

---

## For Human Developers

These resources are primarily for AI assistant use, but are helpful for developers as well:

- **CI_TESTING_GUIDE.md** - Comprehensive overview of running tests locally
- **Type annotation plans** - Understanding the type system improvements
- **Project progress tracking** - See what's been done and what's next

---

## Planning New Work

When planning new projects, follow the structure in `PLANNING_GUIDE.md`:

1. Create project directory: `.claude/<project-name>/`
2. Create required files: `README.md`, `PLAN.md`, `ANALYSIS.md`, `PROGRESS.md`
3. Use provided templates
4. Update this README to list the new project

**See `PLANNING_GUIDE.md` for detailed templates and examples.**

---

## Archive

The `archive/` directory contains deprecated planning documents that have been superseded by better-structured versions. These are kept for historical reference only.
