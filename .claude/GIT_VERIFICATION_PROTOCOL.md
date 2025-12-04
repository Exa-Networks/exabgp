# Git Verification Protocol

**When to read:** Before ANY git operation (commit, push, pull, branch, merge)
**Prerequisites:** ESSENTIAL_PROTOCOLS.md (verification basics, git workflow essentials)
**Size:** 3.7 KB

---

## Quick Summary

- Never run git commands without fresh `git status` pasted first
- Categorize changes: yours vs. pre-existing (ask user about pre-existing)
- User must explicitly say "commit" or "push" - never assume
- One logical change per commit
- Never `git add -A` without asking which files to include

**See enforcement checklist below for complete workflow.**

---

## MANDATORY RULES

**Historical failures corrected by this protocol:**
- Made false claims ("I pushed") without verifying repository state
- Committed pre-existing changes without asking user (included README.md and qa/requirements.txt changes that were already staged)

**1. At START of session - Check for pre-existing changes**

BEFORE starting ANY work, run:
```bash
git status
git diff
git diff --staged
```

If ANY files are modified or staged:
- STOP and ask user: "I see [file1, file2] have changes. Should I include these in my work or handle them separately?"
- NEVER assume you should include pre-existing changes
- NEVER run `git add -A` without knowing what's already modified

**2. NEVER claim git state without fresh verification**

Before ANY claim, run:
```bash
git status && git log --oneline -3 && git log origin/main..HEAD
```

**3. Quote output, don't summarize**
- ✗ "The push succeeded"
- ✓ "Output shows: 'To github.com:... main -> main'"

**4. Verify after EVERY git operation**
```bash
git status && git log --oneline -3
```

**5. Investigate anomalies**
- Commits disappearing? "Everything up-to-date" when expecting push?
- STOP, run diagnostics, report to user
- NEVER blindly re-run commands

**6. Be precise**
- ✓ "Commit created locally" / "Commit pushed to origin/main"
- ✗ "Changes committed" / "Changes pushed" (ambiguous)

**7. CRITICAL: When user says "commit" with pre-existing changes**

NEVER proceed automatically. ALWAYS follow this process:

1. **STOP** - Do NOT run `git add` or `git commit` immediately
2. **Run** `git status` to see all modified files
3. **Categorize** files:
   - Files YOU modified during this session
   - Files with pre-existing changes from before session started
4. **Ask user explicitly:**
   ```
   "I see X modified files:
   - My changes: [file1.py]
   - Pre-existing: [file2.py, file3.py, ...]

   Commit which files?
   1. Only my changes (file1.py)
   2. All files together
   3. Let me review each file first"
   ```
5. **WAIT** for explicit answer
6. **Stage** only the files user specified
7. **Verify** with `git status` before committing

**NEVER:**
- Run `git add -A` without asking which files
- Assume "commit" means "commit everything"
- Include pre-existing changes without explicit permission
- Skip the categorization step

**Example violation:**
```
User: "commit"
❌ Wrong: git add -A && git commit
✅ Right: Stop, categorize files, ask which to include
```

**8. Backport review check**

At session start:
1. Check `.claude/BACKPORT.md` for last reviewed commit hash
2. Run `git log <last_hash>..HEAD --oneline` to see new commits
3. If new commits exist and appear to be bug fixes, ask: "Do any of these commits need backport review?"
4. Skip if commits are clearly refactoring/typing/style only
5. After review, update last reviewed hash in BACKPORT.md

When session starts with modified (uncommitted) files:
- If changes appear to be bug fixes, ask: "Do any of these changes need backport review?"
- Skip if changes are clearly refactoring/typing/style only

---

## ENFORCEMENT

Before ANY git operation:
```bash
git status && git log --oneline -3
```
- [ ] Command run: `<paste above>`
- [ ] Output: `<paste full output>`
- [ ] No unexpected changes OR user asked about them
- [ ] Categorized: my changes vs pre-existing

**If ANY unchecked: STOP. Don't run git command.**

---

## VIOLATION DETECTION

**If I do these, I'm violating:**
- `git add -A` without asking which files
- `git commit` with pre-existing changes without explicit user approval
- Any git operation without fresh `git status` pasted
- Claiming "pushed" without `git log origin/main..HEAD` showing empty
- Assuming repo state without verification

**Auto-fix:** Stop. Run `git status`. Paste. Ask user.

---

## Plan Files and Git

### Before Committing Code

1. Run `git status` - check if plan files in `plan/` are modified
2. If YES (plan files modified):
   - **Default:** Include plan files with code in same commit
   - Use commit message format: `Type: What changed` (plan updates implicit)
   - Only ask user if they want separate commits for unusual cases

3. If NO (only code modified):
   - Proceed normally

### When Plan Files Are Modified but No Code to Commit

If `git status` shows plan file changes but no code:
- Ask user: "Plan files updated. Commit now, or leave for later?"
- If commit: Use message like "Docs: Update plan/[file] - [brief description]"
- If leave: Will show in next session's git status

### At Session End

If plan files have uncommitted changes:
- Warn user: "Plan files have uncommitted changes: [list]"
- Recommend committing with any pending code
- Never force - leave uncommitted if user prefers

### Commit Message Examples

```bash
# Code + plan together (default)
git commit -m "Fix: Resolve race condition in peer handler"

# Plan-only commit
git commit -m "Docs: Update plan/packed-bytes/progress.md - Wave 7 complete"

# WIP with plan
git commit -m "WIP: BGP-LS refactoring (see plan/packed-bytes/)"
```

---

## See Also

- MANDATORY_REFACTORING_PROTOCOL.md - Git commits during refactoring
- VERIFICATION_PROTOCOL.md - Verify git state before claiming
- BACKPORT.md - Bug fix tracking for backports
- SESSION_END_CHECKLIST.md - Plan file handling at session end

---

**Updated:** 2025-12-04
