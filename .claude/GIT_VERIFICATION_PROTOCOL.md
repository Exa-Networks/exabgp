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
