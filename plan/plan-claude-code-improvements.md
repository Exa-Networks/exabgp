# Plan: Claude Code Configuration Improvements

**Status:** PLANNING
**Created:** 2025-12-15
**Source:** KotaDB best practices review

---

## Overview

Add productivity improvements to ExaBGP's Claude Code configuration based on analysis of kotadb's `.claude` directory.

---

## SDLC Workflow Analysis

### KotaDB's Approach

KotaDB has 13 workflow commands covering the full SDLC. After detailed review:

| Command | KotaDB Purpose | ExaBGP Equivalent | Recommendation |
|---------|---------------|-------------------|----------------|
| `/plan` | Create spec files with issue tracking | `plan/` directory conventions | **Skip** - We have this |
| `/implement` | Follow plan step-by-step | CLAUDE.md guidance | **Skip** - Adds complexity |
| `/build` | Compile/artifact creation | N/A (Python, no build) | **Skip** - Not applicable |
| `/validate` | 3-tier test validation | `./qa/bin/test_everything` | **Consider** - See below |
| `/review` | JSON code review output | None | **Consider** - See below |
| `/document` | Generate docs | `/review-docs` exists | **Skip** - We have this |
| `/patch` | Bug fixes | Standard workflow | **Skip** - Not needed |

### Commands Worth Adding

#### 1. `/validate` - Structured Test Validation

**Why useful:**
- Provides tiered validation (quick lint vs full test suite)
- Structured output for consistency
- Matches KotaDB's Level 1/2/3 concept

**ExaBGP adaptation:**
```
Level 1 (Lint Gate, <30s):
  - uv run ruff format --check src
  - uv run ruff check src

Level 2 (Unit Gate, ~2min):
  - Level 1 +
  - uv run pytest ./tests/unit/

Level 3 (Full Gate, ~5min):
  - ./qa/bin/test_everything
```

#### 2. `/review` - Code Review Checklist

**Why useful:**
- Standardizes code review for PRs
- ExaBGP-specific checks (Buffer protocol, no asyncio, Python 3.12+)
- Could output structured findings

**ExaBGP adaptation:**
- Check for `bytes` instead of `Buffer` in unpack methods
- Check for `Union`/`Optional` instead of `|` syntax
- Check for asyncio imports (forbidden)
- Check for unused `negotiated` parameter documentation
- Verify test coverage for changed code

#### 3. `/pre-commit` - Pre-Commit Checks

**Why useful:**
- Quick validation before `git add`
- Catches common issues early
- Complements auto-linter hook

---

## Implementation Plan

### Phase 1: Core Infrastructure (High Priority)

#### Task 1.1: Create Auto-Linter Hook
**Files:**
- `NEW: .claude/hooks/auto_linter.py`

**Behavior:**
- Triggers on Write/Edit of `.py` files
- Runs `uv run ruff format <file>`
- Runs `uv run ruff check --fix <file>`
- Reports any remaining issues

**Implementation:**
```python
#!/usr/bin/env python3
"""PostToolUse hook: Auto-lint Python files after edits."""
import json
import subprocess
import sys
from pathlib import Path

def main():
    try:
        input_data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        return

    tool_name = input_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return

    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path.endswith(".py"):
        return

    path = Path(file_path)
    if not path.exists():
        return

    # Find project root (has pyproject.toml)
    project_root = path.parent
    while project_root != project_root.parent:
        if (project_root / "pyproject.toml").exists():
            break
        project_root = project_root.parent

    try:
        # Format
        subprocess.run(
            ["uv", "run", "ruff", "format", str(path)],
            cwd=project_root,
            timeout=30,
            capture_output=True
        )

        # Check and fix
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--fix", str(path)],
            cwd=project_root,
            timeout=30,
            capture_output=True,
            text=True
        )

        if result.returncode != 0 and result.stdout.strip():
            sys.stdout.write(f"[lint] {path.name}: {result.stdout.strip()}\n")

    except subprocess.TimeoutExpired:
        sys.stdout.write(f"[lint] Timeout linting {path.name}\n")
    except FileNotFoundError:
        sys.stdout.write("[lint] uv not found\n")
    except Exception as e:
        sys.stdout.write(f"[lint] Error: {e}\n")

if __name__ == "__main__":
    main()
```

---

#### Task 1.2: Create Custom Statusline
**Files:**
- `NEW: .claude/statusline.py`

**Behavior:**
- Shows model name (colored by tier)
- Shows git branch (red warning for `main`)
- Shows lines added/removed
- Shows project name

**Implementation:**
```python
#!/usr/bin/env python3
"""Custom status line for ExaBGP development."""
import json
import subprocess
import sys

# ANSI color codes
C = {
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
    "reset": "\033[0m", "dim": "\033[2m", "bold": "\033[1m"
}

def get_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() if result.returncode == 0 else "?"
    except Exception:
        return "?"

def main():
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError:
        data = {}

    model = data.get("model", "unknown")
    added = data.get("lines_added", 0)
    removed = data.get("lines_removed", 0)
    branch = get_branch()

    # Model color: opus=magenta, sonnet=cyan, haiku=yellow
    if "opus" in model.lower():
        model_color = C["magenta"]
        model_short = "opus"
    elif "haiku" in model.lower():
        model_color = C["yellow"]
        model_short = "haiku"
    else:
        model_color = C["cyan"]
        model_short = "sonnet"

    # Branch color: main=red (danger), feature=cyan
    if branch in ("main", "master"):
        branch_color = C["red"] + C["bold"]
    elif branch.startswith(("feat", "feature", "fix", "bug")):
        branch_color = C["green"]
    else:
        branch_color = C["cyan"]

    # Build status line
    sep = f" {C['dim']}|{C['reset']} "
    parts = [
        f"{model_color}{model_short}{C['reset']}",
        f"{C['green']}+{added}{C['reset']}/{C['red']}-{removed}{C['reset']}",
        f"{branch_color}{branch}{C['reset']}",
    ]

    sys.stdout.write(sep.join(parts))

if __name__ == "__main__":
    main()
```

---

#### Task 1.3: Update settings.local.json
**Files:**
- `UPDATE: .claude/settings.local.json`

**Changes:**
- Add PostToolUse hook for auto-linter
- Add statusline configuration

---

### Phase 2: Workflow Commands (Medium Priority)

#### Task 2.1: Create `/validate` Command
**Files:**
- `NEW: .claude/commands/validate.md`

**Behavior:**
- Accept optional level (1, 2, 3) - default 2
- Run appropriate test suite
- Output structured results

**Template:**
```markdown
---
description: Run validation tests at specified level (1=lint, 2=unit, 3=full)
---

# Validation Command

Run tiered validation for ExaBGP code changes.

## Validation Levels

| Level | Tests | Duration | Use When |
|-------|-------|----------|----------|
| 1 | Lint only | <30s | Quick syntax check |
| 2 | Lint + Unit | ~2min | Standard development |
| 3 | Full suite | ~5min | Before commit/PR |

## Instructions

1. Parse the requested level from arguments (default: 2)
2. Run the appropriate commands
3. Report results in structured format

### Level 1: Lint Gate
```bash
uv run ruff format --check src
uv run ruff check src
```

### Level 2: Unit Gate (includes Level 1)
```bash
uv run ruff format --check src && uv run ruff check src
env exabgp_log_enable=false uv run pytest ./tests/unit/ -q
```

### Level 3: Full Gate
```bash
./qa/bin/test_everything
```

## Output Format

```
✅ Validation Level {N} PASSED

📊 Results:
- Lint: ✅ passed
- Unit tests: ✅ 1376/1376 passed
- Functional: ✅ 72/72 passed (if level 3)

⏱️ Duration: Xs
```

Or on failure:
```
❌ Validation Level {N} FAILED

📊 Results:
- Lint: ❌ 3 errors (see above)
- Unit tests: ⏭️ skipped (lint failed)

🔧 Fix lint errors before proceeding.
```
```

---

#### Task 2.2: Create `/review` Command
**Files:**
- `NEW: .claude/commands/review.md`

**Behavior:**
- Review code changes for ExaBGP-specific issues
- Check for common mistakes
- Output structured findings

**Template:**
```markdown
---
description: Review code changes for ExaBGP-specific issues
---

# Code Review Command

Review staged or specified files for ExaBGP coding standards.

## Review Checklist

### 1. Python 3.12+ Syntax
- [ ] Uses `X | Y` instead of `Union[X, Y]`
- [ ] Uses `X | None` instead of `Optional[X]`
- [ ] No `from __future__` imports

### 2. Buffer Protocol Compliance
- [ ] Unpack methods use `data: Buffer` not `data: bytes`
- [ ] Import from `exabgp.util.types import Buffer`
- [ ] No unnecessary `.tobytes()` conversions

### 3. ExaBGP Conventions
- [ ] Unused `negotiated` params documented as "(unused, required by interface)"
- [ ] No asyncio imports (forbidden)
- [ ] No FIB manipulation code

### 4. Test Coverage
- [ ] New code has corresponding tests
- [ ] Modified code tests still pass

### 5. Documentation
- [ ] Public methods have docstrings
- [ ] Complex logic has comments explaining WHY

## Instructions

1. Get list of changed files: `git diff --name-only` or specified files
2. For each Python file, check against the checklist
3. Report findings by category

## Output Format

```
📋 Code Review: {file_count} files

✅ Python 3.12+ Syntax: No issues
⚠️ Buffer Protocol: 2 issues
   - src/foo.py:42 - Uses `bytes` instead of `Buffer`
   - src/bar.py:17 - Missing Buffer import
✅ ExaBGP Conventions: No issues
⚠️ Test Coverage: 1 issue
   - New function `parse_thing()` has no tests
✅ Documentation: No issues

Summary: 3 issues (0 blockers, 3 suggestions)
```
```

---

#### Task 2.3: Create `/pre-commit` Command
**Files:**
- `NEW: .claude/commands/pre-commit.md`

**Behavior:**
- Quick pre-commit validation
- Check staged files only
- Fast feedback loop

---

### Phase 3: Documentation Updates

#### Task 3.1: Update CLAUDE.md
- Document new hooks
- Document new commands
- Add to quick reference

#### Task 3.2: Create hooks/README.md
- Document hook architecture
- Explain how to add new hooks
- List available hooks

---

## File Summary

### New Files
| File | Purpose | Priority |
|------|---------|----------|
| `.claude/hooks/auto_linter.py` | Auto-lint on edit | Phase 1 |
| `.claude/statusline.py` | Custom status display | Phase 1 |
| `.claude/commands/validate.md` | Tiered test validation | Phase 2 |
| `.claude/commands/review.md` | Code review checklist | Phase 2 |
| `.claude/commands/pre-commit.md` | Pre-commit checks | Phase 2 |
| `.claude/hooks/README.md` | Hook documentation | Phase 3 |

### Modified Files
| File | Changes | Priority |
|------|---------|----------|
| `.claude/settings.local.json` | Add hooks config | Phase 1 |
| `CLAUDE.md` | Document new features | Phase 3 |

---

## Decision Points for User

### 1. SDLC Workflow Depth

**Option A: Minimal (Recommended)**
- Just `/validate` command
- Wraps existing `test_everything` with structure
- Low maintenance burden

**Option B: Standard**
- `/validate` + `/review` + `/pre-commit`
- More structure for development workflow
- Medium maintenance burden

**Option C: Full**
- All commands including `/plan`, `/implement`
- KotaDB-style full SDLC
- High maintenance burden (not recommended)

### 2. Hook Strictness

**Option A: Advisory (Recommended)**
- Auto-linter fixes issues silently
- Shows warnings but doesn't block

**Option B: Strict**
- Auto-linter can block operations
- Requires lint pass before proceeding

### 3. Statusline Content

**Option A: Minimal**
- Model + branch only

**Option B: Standard (Recommended)**
- Model + branch + lines changed

**Option C: Full**
- Model + branch + lines + test status + time

---

## Progress Tracking

- [ ] Phase 1.1: Auto-linter hook
- [ ] Phase 1.2: Custom statusline
- [ ] Phase 1.3: Settings update
- [ ] Phase 2.1: /validate command
- [ ] Phase 2.2: /review command
- [ ] Phase 2.3: /pre-commit command
- [ ] Phase 3.1: CLAUDE.md update
- [ ] Phase 3.2: hooks/README.md

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hook slows down editing | Medium | Add timeout, make advisory |
| Commands not used | Low | Start with most useful ones |
| Maintenance burden | Medium | Keep implementations simple |
| Conflicts with existing workflow | Low | Commands are opt-in |

---

## Success Criteria

1. Auto-linter catches formatting issues before commit
2. Statusline shows branch (red warning on main)
3. `/validate` provides quick feedback loop
4. No increase in false positives or workflow friction

---

## References

- KotaDB analysis: `.claude/docs/reference/KOTADB_BEST_PRACTICES_REVIEW.md`
- Claude Code hooks docs: https://docs.anthropic.com/claude-code/hooks
- ExaBGP test suite: `./qa/bin/test_everything`
