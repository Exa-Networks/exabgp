# PRE-FLIGHT CHECKLIST

**MANDATORY - Run BEFORE starting ANY work.**

---

## 1. Protocols Read

- [ ] VERIFICATION_DISCIPLINE.md
- [ ] COMMUNICATION_STYLE.md
- [ ] EMOJI_GUIDE.md
- [ ] GIT_VERIFICATION_PROTOCOL.md
- [ ] MANDATORY_REFACTORING_PROTOCOL.md
- [ ] ERROR_RECOVERY_PROTOCOL.md
- [ ] CODING_STANDARDS.md
- [ ] TESTING_DISCIPLINE.md
- [ ] PLANNING_GUIDE.md
- [ ] CI_TESTING.md
- [ ] FUNCTIONAL_TEST_DEBUGGING_GUIDE.md

**If ANY unchecked: STOP. Read them.**

---

## 2. Git State Verified

```bash
git status && git diff && git diff --staged
```

**Paste output above. If modified/staged files: ASK user before proceeding.**

---

## 3. Codebase References (For New Features/Refactoring)

**If task involves new features, major changes, or unfamiliar areas:**

- [ ] Read relevant codebase reference docs (see CLAUDE.md § Essential Codebase References)
  - Adding NLRI type → exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md, exabgp/CODEBASE_ARCHITECTURE.md
  - Understanding data flow → exabgp/DATA_FLOW_GUIDE.md
  - Finding BGP concept → exabgp/BGP_CONCEPTS_TO_CODE_MAP.md
  - Quick file navigation → exabgp/CRITICAL_FILES_REFERENCE.md

**Skip this if:** Simple bug fix, known area, documentation-only work

---

## 4. Ready to Work

- [ ] All protocols read
- [ ] Git state checked
- [ ] User informed of any pre-existing changes
- [ ] No assumptions made
- [ ] Relevant codebase references reviewed (if applicable)

**If ANY unchecked: STOP.**

---

**This checklist BLOCKS starting work. Complete it first.**
