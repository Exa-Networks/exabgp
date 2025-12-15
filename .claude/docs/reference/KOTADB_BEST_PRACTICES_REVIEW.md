# KotaDB Claude Code Best Practices Review

Review of https://github.com/jayminwest/kotadb/tree/develop/.claude for practices applicable to ExaBGP.

---

## Summary of KotaDB's Setup

KotaDB implements a sophisticated Claude Code configuration with:

1. **Multi-Agent System** - Specialized agents (scout, build, review, orchestrator)
2. **Hooks** - Auto-linter and context builder
3. **SDLC Workflows** - plan, implement, build, validate, review, document
4. **Domain Experts** - Architecture, testing, security, integration experts
5. **Custom Statusline** - Dynamic status display with git info
6. **Agent Registry** - JSON-based capability/tool matrix

---

## Recommendations for ExaBGP

### HIGH PRIORITY - Implement

#### 1. Auto-Linter Hook
**What they have:** PostToolUse hook that runs linter automatically after Write/Edit operations.

**Why useful for ExaBGP:**
- Enforces `ruff format` and `ruff check` automatically
- Prevents commits with lint errors
- Reduces manual "run ruff" reminders in CLAUDE.md

**Implementation:**
```python
# .claude/hooks/auto_linter.py
#!/usr/bin/env python3
"""PostToolUse hook: Auto-run ruff after Python file edits."""
import json
import subprocess
import sys

def main():
    input_data = json.loads(sys.stdin.read())
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name not in ("Write", "Edit"):
        return

    file_path = tool_input.get("file_path", "")
    if not file_path.endswith(".py"):
        return

    # Run ruff format + check
    try:
        subprocess.run(["uv", "run", "ruff", "format", file_path],
                      timeout=30, capture_output=True)
        result = subprocess.run(["uv", "run", "ruff", "check", "--fix", file_path],
                               timeout=30, capture_output=True, text=True)
        if result.returncode != 0:
            sys.stdout.write(f"[lint] Issues in {file_path}:\n{result.stdout}")
    except Exception as e:
        sys.stdout.write(f"[lint] Error: {e}")

if __name__ == "__main__":
    main()
```

**Effort:** Low (1 file, ~50 lines)

---

#### 2. Custom Statusline
**What they have:** Python script showing model, git branch, code changes with colors.

**Why useful for ExaBGP:**
- Shows current git branch (important given our strict git rules)
- Visual reminder of which model is active
- Better session awareness

**Implementation:**
```python
# .claude/statusline.py
#!/usr/bin/env python3
"""Custom status line for ExaBGP development."""
import json
import subprocess
import sys

COLORS = {
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "blue": "\033[34m", "magenta": "\033[35m", "cyan": "\033[36m",
    "reset": "\033[0m", "dim": "\033[2m"
}

def get_branch():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip() if result.returncode == 0 else "unknown"
    except:
        return "unknown"

def main():
    data = json.loads(sys.stdin.read())
    model = data.get("model", "unknown")
    added = data.get("lines_added", 0)
    removed = data.get("lines_removed", 0)
    branch = get_branch()

    # Color model name
    model_color = COLORS["magenta"] if "opus" in model else COLORS["cyan"]

    # Color branch (main=red warning, feature=cyan)
    branch_color = COLORS["red"] if branch == "main" else COLORS["cyan"]

    parts = [
        f"{model_color}{model}{COLORS['reset']}",
        f"{COLORS['green']}+{added}{COLORS['reset']}/{COLORS['red']}-{removed}{COLORS['reset']}",
        f"{branch_color}{branch}{COLORS['reset']}",
    ]

    sys.stdout.write(f" {COLORS['dim']}|{COLORS['reset']} ".join(parts))

if __name__ == "__main__":
    main()
```

**Effort:** Low (1 file, ~40 lines)

---

### MEDIUM PRIORITY - Consider

#### 3. Context Builder Hook
**What they have:** UserPromptSubmit hook that analyzes keywords and suggests relevant docs.

**Why potentially useful:**
- Could suggest relevant `.claude/exabgp/*.md` docs based on keywords
- Examples: "NLRI" → suggest NLRI_CLASS_HIERARCHY.md, "wire" → PEP688_BUFFER_PROTOCOL.md

**Why NOT implement now:**
- ExaBGP's CLAUDE.md already has a comprehensive "Quick reference" section
- Adding another layer may slow down responses
- Our docs are well-organized in `.claude/exabgp/`

**Verdict:** Defer until we find Claude consistently missing relevant docs.

---

#### 4. SDLC Workflow Commands
**What they have:** `/plan`, `/implement`, `/build`, `/validate`, `/review`, `/document`

**Why potentially useful:**
- Structured approach to feature development
- Consistent output formats

**Why NOT implement now:**
- ExaBGP already has `plan/` directory with good conventions
- Our CLAUDE.md enforces planning via `./qa/bin/test_everything` requirement
- Adding 13 new workflow files is significant maintenance burden

**Verdict:** Cherry-pick useful ones. Candidates:
- `/review` - Could standardize code review format
- `/validate` - Could wrap `./qa/bin/test_everything` with structured output

---

#### 5. Git Automation Commands
**What they have:** `/commit`, `/pull_request` commands

**Why NOT implement:**
- ExaBGP has strict "NEVER commit without explicit user request" rules
- Automating git risks violating our safety protocols
- Current CLAUDE.md git instructions are comprehensive

**Verdict:** Do not implement - conflicts with our safety model.

---

### LOW PRIORITY - Not Recommended

#### 6. Multi-Agent System (Scout/Build/Review/Orchestrator)
**What they have:** 4 specialized agents with different tool permissions.

**Why NOT implement:**
- Significant complexity (10+ agent definition files, registry JSON)
- ExaBGP is a single maintainer project - agent coordination overhead not justified
- Claude Code's built-in agent system (Task tool) already provides this

**Verdict:** Not worth the maintenance burden.

---

#### 7. Domain Expert Commands
**What they have:** `/experts/architecture-expert`, `/experts/testing-expert`, etc.

**Why NOT implement:**
- ExaBGP's domain is narrow (BGP protocol) - one expert would suffice
- Our `.claude/exabgp/` docs already provide domain expertise
- Adding 8 expert definitions is maintenance burden

**Verdict:** Not needed for ExaBGP's scope.

---

#### 8. Read-Only Default Permissions
**What they have:** `settings.json` denies Write/Edit by default.

**Why NOT implement:**
- ExaBGP development requires frequent file edits
- Would add friction to normal workflow
- Our git verification protocol provides safety instead

**Verdict:** Not appropriate for our workflow.

---

## Implementation Roadmap

### Phase 1 (Immediate)
1. **Auto-linter hook** - Low effort, high value
2. **Statusline** - Low effort, medium value

### Phase 2 (If Needed)
3. **Context builder** - Medium effort, evaluate after using Phase 1
4. **Select workflow commands** - Medium effort, `/review` and `/validate`

### Not Planned
- Multi-agent system
- Domain experts
- Git automation
- Read-only permissions

---

## Files to Create

```
.claude/
├── hooks/
│   └── auto_linter.py      # NEW: PostToolUse hook
├── statusline.py           # NEW: Custom status display
└── settings.json           # UPDATE: Add hook config
```

---

## Settings.json Updates Required

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "command": ["python3", ".claude/hooks/auto_linter.py"],
        "timeout": 45000
      }
    ]
  },
  "status_line": {
    "command": ["python3", ".claude/statusline.py"]
  }
}
```

---

## Summary

| Feature | Priority | Effort | Implement? |
|---------|----------|--------|------------|
| Auto-linter hook | HIGH | Low | Yes |
| Custom statusline | HIGH | Low | Yes |
| Context builder | MEDIUM | Medium | Defer |
| Workflow commands | MEDIUM | Medium | Partial |
| Git commands | LOW | Low | No |
| Multi-agent system | LOW | High | No |
| Domain experts | LOW | High | No |
| Read-only default | LOW | Low | No |

**Recommended action:** Implement auto-linter hook and statusline first. These provide immediate value with minimal complexity.
