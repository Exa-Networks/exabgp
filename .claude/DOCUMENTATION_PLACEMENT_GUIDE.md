# Documentation Placement Guide

**When to read:** Before creating ANY new .md file
**Prerequisites:** ESSENTIAL_PROTOCOLS.md
**Size:** 12 KB

---

## Quick Summary

**Use decision tree below to determine correct location:**
- Implementation plans & active work → `plan/` (project root)
- Codebase usage/modification → `.claude/exabgp/`
- Work protocols/rules → `.claude/` (root)
- Completed project history → `.claude/docs/projects/`
- Superseded/obsolete → `.claude/docs/archive/`

**See full decision tree below with examples.**

---

**MANDATORY: Read full guide before creating documentation files.**

This guide tells you EXACTLY where to put documentation based on its purpose.

---

## 🚨 CRITICAL DECISION TREE 🚨

**Before creating a doc, ask:**

### 1. Is this about HOW TO USE/MODIFY the codebase NOW?

**YES** → Goes in `.claude/exabgp/`

Examples:
- "Where is the NLRI code?"
- "How do I add a new attribute?"
- "What files implement BGP messages?"
- "How does data flow through the system?"

**Files:**
- `CODEBASE_ARCHITECTURE.md` - Where things are
- `DATA_FLOW_GUIDE.md` - How data moves
- `REGISTRY_AND_EXTENSION_PATTERNS.md` - How to extend
- `BGP_CONCEPTS_TO_CODE_MAP.md` - BGP concepts → files
- `CRITICAL_FILES_REFERENCE.md` - Most important files

**Update when:** Codebase structure changes, new patterns added

---

### 2. Is this about HOW WE WORK (protocols, rules, standards)?

**YES** → Goes in `.claude/` (root level)

Examples:
- "How should I verify changes?"
- "What's the git workflow?"
- "How should I communicate?"
- "What are the coding standards?"
- "How do I refactor safely?"

**Files:**
- `VERIFICATION_PROTOCOL.md` - Verify before claiming
- `GIT_VERIFICATION_PROTOCOL.md` - Git safety rules
- `MANDATORY_REFACTORING_PROTOCOL.md` - Refactoring steps
- `ERROR_RECOVERY_PROTOCOL.md` - Slow down after mistakes
- `CODING_STANDARDS.md` - Python 3.12+, APIs
- `TIGER_STYLE.md` - Safety rules (bounds, assertions, error handling)
- `TESTING_PROTOCOL.md` - Testing requirements
- `PLANNING_GUIDE.md` - Project planning
- `CI_TESTING.md` - CI test requirements
- `FUNCTIONAL_TEST_DEBUGGING_GUIDE.md` - Debug tests
- `PRE_FLIGHT_CHECKLIST.md` - Session start checklist
- `DOCUMENTATION_PLACEMENT_GUIDE.md` - This file
- `output-styles/exabgp.md` - Communication style

**Update when:** Protocols violated repeatedly, new patterns emerge

---

### 3. Is this about a COMPLETED PROJECT (history, what was done)?

**YES** → Goes in `.claude/docs/projects/{project-name}/`

Examples:
- "How was asyncio migration done?"
- "What decisions were made during pack method rename?"
- "Session summary for timeout fix"
- "Migration strategy analysis"

**Structure:**
```
.claude/docs/projects/{project-name}/
├── README.md           # Overview, status, summary
├── plan.md             # Original plan (if applicable)
├── status.md           # Completion status (if applicable)
├── archive/            # Historical documents
├── sessions/           # Session summaries
├── phases/             # Phase-specific docs
└── technical/          # Technical analysis
```

**Update when:** Project completes, milestones reached

---

### 4. Is this about ACTIVE WORK IN PROGRESS or IMPLEMENTATION PLANS?

**YES** → Goes in `plan/` (project root, tracked in git)

Examples:
- "Type annotation progress tracking"
- "Current mypy error status"
- "Ongoing refactoring plan"
- "Plan to add new NLRI type"
- "API improvement proposal"

**Structure:**
```
plan/                              # Project root
├── todo.md                        # Central TODO tracking
├── packed-attribute.md            # Packed-bytes-first refactoring
├── coverage.md                    # Test coverage audit
├── python312-buffer-protocol.md   # Future: Python 3.12 + memoryview
├── type-annotations/              # Type annotation detailed plans
└── comment-cleanup/               # XXX comment cleanup (✅ Complete)
```

**Format:**
```markdown
# Plan: Feature Name

**Status:** Planning | In Progress | Complete
**Priority:** 🔴 🟡 🟢

## Overview
[What and why]

## Implementation Steps
[Numbered steps with verification]

## Testing
[Required tests]
```

**Update when:** Work progresses, plan changes, implementation starts/completes

**When complete:** Mark status as "Complete" in plan file, update `plan/todo.md`

---

### 5. Is this about CODEBASE API/REFERENCE (commands, syntax, protocols)?

**YES** → Goes in `.claude/exabgp/`

Examples:
- "Neighbor selector syntax"
- "CLI command reference"
- "Unix socket API protocol"
- "Environment variables"

**Existing files:**
- `CLI_COMMANDS.md` - Complete CLI command reference
- `CLI_SHORTCUTS.md` - CLI shortcut reference
- `CLI_IMPLEMENTATION.md` - CLI internal architecture
- `UNIX_SOCKET_API.md` - Unix socket API protocol
- `NEIGHBOR_SELECTOR_SYNTAX.md` - Neighbor selector grammar
- `ENVIRONMENT_VARIABLES.md` - Environment variables reference

**Why `.claude/exabgp/`?** These docs describe how to USE the current codebase APIs.

**Update when:** APIs change, new commands added, syntax modified

---

### 6. Is this ARCHITECTURE or TEST documentation?

**YES** → Goes in `.claude/` with descriptive name

Examples:
- "FUNCTIONAL_TEST_ARCHITECTURE.md" - How tests work
- "FILE_NAMING_CONVENTIONS.md" - Naming patterns

**Update when:** Architecture changes, new patterns

---

## 📁 Complete Directory Structure

```
# PROJECT ROOT
plan/                              # Implementation plans (USER PREFERENCE)
├── {feature-name}.md              # e.g., notification-code-rename.md
├── configuration.md
├── coverage.md
└── todo.md

.claude/
├── # PROTOCOLS (how we work)
├── VERIFICATION_PROTOCOL.md
├── GIT_VERIFICATION_PROTOCOL.md
├── MANDATORY_REFACTORING_PROTOCOL.md
├── ERROR_RECOVERY_PROTOCOL.md
├── CODING_STANDARDS.md
├── TESTING_PROTOCOL.md
├── PLANNING_GUIDE.md
├── CI_TESTING.md
├── FUNCTIONAL_TEST_DEBUGGING_GUIDE.md
├── PRE_FLIGHT_CHECKLIST.md
├── DOCUMENTATION_PLACEMENT_GUIDE.md  # This file
├── output-styles/
│   └── exabgp.md                     # Communication style
├──
├── # REFERENCE (architecture, tests, conventions)
├── FUNCTIONAL_TEST_ARCHITECTURE.md
├── FILE_NAMING_CONVENTIONS.md
├── README.md
├──
├── # CODEBASE REFERENCE (how to use/modify codebase + API docs)
├── exabgp/
│   ├── # Architecture & patterns
│   ├── CODEBASE_ARCHITECTURE.md
│   ├── DATA_FLOW_GUIDE.md
│   ├── REGISTRY_AND_EXTENSION_PATTERNS.md
│   ├── BGP_CONCEPTS_TO_CODE_MAP.md
│   ├── CRITICAL_FILES_REFERENCE.md
│   ├──
│   ├── # API & command reference
│   ├── CLI_COMMANDS.md
│   ├── CLI_SHORTCUTS.md
│   ├── CLI_IMPLEMENTATION.md
│   ├── UNIX_SOCKET_API.md
│   ├── NEIGHBOR_SELECTOR_SYNTAX.md
│   └── ENVIRONMENT_VARIABLES.md
├──
├── # ALL DOCUMENTATION
├── docs/
│   ├── README.md
│   ├── projects/              # Completed work
│   │   ├── README.md
│   │   ├── asyncio-migration/
│   │   ├── type-annotations/
│   │   ├── pack-method-standardization/
│   │   └── {project-name}/
│   ├── wip/                   # Active work in progress
│   │   ├── README.md
│   │   └── {project-name}/
│   └── archive/               # Superseded experiments
│       └── {old-project}/
├──
└── # SPECIAL
    └── settings.local.json     # Local settings
```

---

## 🎯 Quick Reference Table

| Doc Type | Location | Example | When to Update |
|----------|----------|---------|----------------|
| **Implementation plans** | `plan/` | "Refactoring plan" | Plan changes |
| **Codebase structure** | `.claude/exabgp/` | "Where is NLRI code?" | Structure changes |
| **Work protocols** | `.claude/` | "How to verify?" | Protocol violations |
| **Completed projects** | `.claude/docs/projects/` | "AsyncIO migration" | Project completes |
| **Active work** | `.claude/docs/wip/` | "Type annotation progress" | Work progresses |
| **Test architecture** | `.claude/` | "Functional test guide" | Test changes |
| **Archive** | `.claude/docs/archive/` | "Superseded plans" | When obsolete |

---

## ✅ Examples: Where Should This Go?

### Example 1: "I want to document how to add a new path attribute"

**Decision:**
- Is it about HOW TO USE/MODIFY codebase NOW? **YES**
- **Location:** `.claude/exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md`
- **Why:** It's about extending the current codebase

### Example 2: "I want to document the asyncio migration journey"

**Decision:**
- Is it a COMPLETED PROJECT? **YES**
- **Location:** `.claude/docs/projects/asyncio-migration/`
- **Why:** It's historical work that's done

### Example 3: "I want to document git commit rules"

**Decision:**
- Is it about HOW WE WORK? **YES**
- **Location:** `.claude/GIT_VERIFICATION_PROTOCOL.md` (already exists)
- **Why:** It's a protocol for working

### Example 4: "I want to track current type annotation progress"

**Decision:**
- Is it ACTIVE WORK? **YES**
- **Location:** `.claude/docs/wip/type-annotations/STATUS.md`
- **Why:** It's ongoing work

### Example 5: "I want to plan a new health monitoring feature"

**Decision:**
- Is it an IMPLEMENTATION PLAN? **YES**
- **Location:** `plan/health-monitoring.md`
- **Why:** Implementation plans go in the `plan/` folder at project root

### Example 6: "I want to document the socket API protocol"

**Decision:**
- Is it about HOW TO USE/MODIFY the codebase NOW? **YES**
- Is it codebase API/reference info? **YES**
- **Location:** `.claude/exabgp/UNIX_SOCKET_API.md` (already exists)
- **Why:** It's API reference documentation for the current codebase

---

## 🚨 Common Mistakes to Avoid

❌ **DON'T:** Create loose .md files in root directories
✅ **DO:** Put files in appropriate subdirectories

❌ **DON'T:** Mix current codebase docs with project history
✅ **DO:** Separate "how to use" from "how it was built"

❌ **DON'T:** Put active work docs in archive
✅ **DO:** Use wip/ for active, docs/projects/ when complete

❌ **DON'T:** Update project history docs daily
✅ **DO:** Update at milestones/completion

❌ **DON'T:** Put session summaries in reference docs
✅ **DO:** Session summaries go in docs/projects/{name}/sessions/

---

## 📝 Document Lifecycle

```
Idea
  ↓
.claude/docs/wip/{feature}/         (Planning & active development)
  ↓
.claude/docs/projects/{feature}/    (Completed, archived)
  ↓
.claude/docs/archive/{feature}/     (If superseded/obsolete)
```

**Codebase reference docs:** Updated in-place when structure changes
**Protocol docs:** Updated when protocols need refinement

---

## 🔍 Self-Check Questions

**Before creating a doc, ask yourself:**

1. **Does this doc describe current codebase structure?**
   - YES → `.claude/exabgp/`
   - NO → Continue

2. **Does this doc define how I should work?**
   - YES → `.claude/{PROTOCOL}.md`
   - NO → Continue

3. **Does this doc describe completed work?**
   - YES → `.claude/docs/projects/`
   - NO → Continue

4. **Does this doc track active work?**
   - YES → `.claude/docs/wip/`
   - NO → Continue

5. **Does this doc plan future work (implementation plan)?**
   - YES → `plan/` (project root)
   - NO → Continue

6. **Does this doc provide codebase API/reference info (CLI, socket API, syntax)?**
   - YES → `.claude/exabgp/` (API reference for current codebase)
   - NO → Ask user where it should go

---

## 🎓 Summary

**Three main categories:**

1. **CURRENT STATE** (`.claude/exabgp/`, `.claude/{protocols}.md`)
   - How things ARE now
   - How to USE/MODIFY now
   - How we WORK

2. **HISTORY** (`.claude/docs/projects/`)
   - What WAS done
   - How it WAS done
   - Decisions made

3. **FUTURE** (`plan/`, `.claude/docs/wip/`)
   - Implementation plans → `plan/`
   - Active work progress → `.claude/docs/wip/`

**Golden rule:** If you can't decide, ask the user.

---

**Updated:** 2025-11-26
