---
description: Review code changes for correctness and consistency
allowed-tools: Bash, Read, Grep, Glob
---

# Review

Semantically review code changes - understand what changed and whether it's correct.

## Arguments

$ARGUMENTS - Optional: file path(s) or "staged" or "all". Default: staged changes

## Instructions

### Step 1: Identify what to review

- If $ARGUMENTS is a file path: review that file
- If $ARGUMENTS is "staged" or empty: `git diff --cached`
- If $ARGUMENTS is "all": `git diff`

### Step 2: Understand the changes

Read the diff and understand:
1. **What is the intent?** - What problem is being solved?
2. **What files changed?** - Are they related or scattered?
3. **What's the scope?** - Small fix, refactor, new feature?

### Step 3: Check for consistency issues

For each significant change, verify:

**If adding a new class/type:**
- Is it registered where needed? (NLRI registry, Message registry, etc.)
- Does it follow existing patterns in similar files?
- Are there tests?

**If modifying pack/unpack methods:**
- Is the wire format documented?
- Does pack output match unpack input? (round-trip)
- Is `Buffer` used for data parameters (not `bytes`)?

**If changing configuration parsing:**
- Is the factory method used (not direct construction)?
- Are all fields validated?

**If adding/changing API:**
- Is it documented?
- Does it handle errors gracefully?

### Step 4: Check for missing pieces

- **Tests:** New code should have tests. Modified code should have passing tests.
- **Documentation:** Public APIs need docstrings.
- **Imports:** No `asyncio`, use `Buffer` not `bytes` for wire data.

### Step 5: Report findings

Format:
```
Review: {description of changes}

Scope: {small fix | refactor | feature | ...}

Findings:
- [category] issue description

Missing:
- Tests for X
- Documentation for Y

Suggestions:
- Consider doing Z
```

## What this is NOT

This is NOT a lint check. The auto-linter handles formatting.
This is about understanding the code and catching semantic issues.

## Reference

For coding standards details, see:
- `.claude/CODING_STANDARDS.md`
- `.claude/ESSENTIAL_PROTOCOLS.md`
