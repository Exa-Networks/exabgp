# Session-End Checklist

**When to use:** MANDATORY before ending ANY work session
**Prerequisites:** ESSENTIAL_PROTOCOLS.md
**Size:** ~2 KB

---

## Quick Summary

Before ending a session:
1. Update any plan files you worked on
2. Document any test failures
3. Check git status for plan file changes
4. Report session summary to user

**This checklist BLOCKS ending work. Complete it first.**

---

## 1. Plan File Updates

**If you worked on ANY plan file this session:**

For EACH plan file in `plan/`:
- [ ] Updated "Last Updated" timestamp to today
- [ ] Documented progress made this session
- [ ] Documented any test failures (with root cause if known)
- [ ] Documented any blockers discovered
- [ ] Documented any design decisions made
- [ ] Updated "Resume Point" section for next session

**Template for Resume Point:**
```markdown
## Resume Point

**Last worked:** YYYY-MM-DD
**Last commit:** [hash or "uncommitted"]
**Session ended:** Mid-task / Clean break / Blocked

**To resume:**
1. [Exact next step to take]
2. [Context needed]
3. [Watch out for: potential issues]
```

---

## 2. Failure Documentation

**If ANY tests failed this session:**

- [ ] Each failure has entry in plan file's "Recent Failures" section
- [ ] Root cause documented (or "Unknown - needs investigation")
- [ ] Resolution documented (or "Pending")

**Template for failure entry:**
```markdown
### [Date] Test Failure: test_name

**Error:** [paste error message]
**Suspected cause:** [your analysis]
**Status:** 🔄 Investigating | ✅ Fixed | ❌ Blocked

**Resolution:** [what fixed it, or why blocked]
```

---

## 3. Git Status Check

```bash
git status
```

- [ ] Check if plan files are modified
- [ ] If YES: Include plan files in next commit (default behavior)
- [ ] If user doesn't want to commit yet: Leave uncommitted (will show in next session)

**Default:** Plan files are committed WITH code changes.

**If plan files modified but no code to commit:**
- Ask user: "Plan files updated. Commit them now or leave for later?"

---

## 4. Session Summary

**Report to user before ending:**

```
Session summary:
- Plans updated: [list or "none"]
- Failures documented: [count or "none"]
- Blockers: [list or "none"]
- Next steps: [what to do next session]
```

---

## Enforcement

**NEVER end a session without:**
1. Running this checklist
2. Updating plan files (if applicable)
3. Reporting summary to user

**Violation indicators:**
- Ending without mentioning plan status
- Leaving failures undocumented
- Not updating "Resume Point" when mid-task

**Auto-fix:** Stop. Run checklist. Update plans. Report summary.

---

## See Also

- ESSENTIAL_PROTOCOLS.md - Plan Update Triggers
- PRE_FLIGHT_CHECKLIST.md - Session start checklist
- GIT_VERIFICATION_PROTOCOL.md - Git workflow

---

**Updated:** 2025-12-04
