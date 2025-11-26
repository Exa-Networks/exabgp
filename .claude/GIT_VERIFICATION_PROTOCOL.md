# GIT VERIFICATION PROTOCOL

**Failures:**
- Made false claims ("I pushed") without verifying repository state
- Committed pre-existing changes without asking user (included README.md and qa/requirements.txt changes that were already staged)

## MANDATORY RULES

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
