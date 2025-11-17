# GIT VERIFICATION PROTOCOL

**Failure:** Made false claims ("I pushed") without verifying repository state.

## MANDATORY RULES

**1. NEVER claim git state without fresh verification**

Before ANY claim, run:
```bash
git status && git log --oneline -3 && git log origin/main..HEAD
```

**2. Quote output, don't summarize**
- ✗ "The push succeeded"
- ✓ "Output shows: 'To github.com:... main -> main'"

**3. Verify after EVERY git operation**
```bash
git status && git log --oneline -3
```

**4. Investigate anomalies**
- Commits disappearing? "Everything up-to-date" when expecting push?
- STOP, run diagnostics, report to user
- NEVER blindly re-run commands

**5. Be precise**
- ✓ "Commit created locally" / "Commit pushed to origin/main"
- ✗ "Changes committed" / "Changes pushed" (ambiguous)
