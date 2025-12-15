# GitHub Project Setup Improvements

**Status:** 📋 Planning
**Created:** 2025-12-15
**Source:** [DevOps & AI Toolkit video](https://www.youtube.com/watch?v=gYl3moYa4iI)
**Reference:** `.claude/docs/reference/GITHUB_PROJECT_SETUP_BEST_PRACTICES.md`

---

## Summary

Modernize exabgp's GitHub configuration to:
- Reduce support burden (better issue templates)
- Improve contribution quality (PR template)
- Establish security posture (SECURITY.md)
- Automate routine tasks (labeling, stale issues)

**Estimated effort:** 2-4 hours for Phase 1, additional 2-3 hours for Phase 2

---

## Current State Assessment

### What We Have

| Item | Status | Notes |
|------|--------|-------|
| Issue templates | Partial | Old markdown format, no required fields |
| Issue config | Missing | No resource links menu |
| PR template | Missing | Only async-migration specific template |
| CODEOWNERS | Missing | No auto-reviewer assignment |
| SECURITY.md | Missing | Critical gap |
| CODE_OF_CONDUCT.md | Missing | Optional |
| Labeler | Missing | No auto-labeling |
| Release notes config | Missing | Unorganized releases |
| Stale workflow | Missing | Issue backlog grows |
| Dependabot | Partial | GitHub Actions only |
| LICENSE | Yes | `LICENCE.txt` (BSD) |
| CONTRIBUTING.md | Yes | Needs minor updates |
| CodeQL | Yes | Security scanning active |

---

## Detailed Review

### 1. Issue Templates (Needs Upgrade)

**Current:** `.github/ISSUE_TEMPLATE/bug_report.md`, `feature_request.md`

**Issues Found:**

| Problem | Impact |
|---------|--------|
| No required fields | Users submit empty/vague reports |
| No structured form | Free-text instead of guided fields |
| No dropdown for environment | Inconsistent version reporting |
| Outdated content | References 3.4→4.x migration (current is 6.x) |
| Typo | "provive" instead of "provide" (line 24) |
| No Python version field | Critical for debugging |

**Best Practice:** YAML form templates with required fields, dropdowns, checkboxes.

---

### 2. Issue Template Config (Missing)

**Impact:**
- No menu guiding users to correct resources
- Users can create blank issues
- No links to wiki, discussions, security reporting

---

### 3. PR Template (Missing)

**Current:** Only `PULL_REQUEST_TEMPLATE_ASYNC_MIGRATION.md` (not default)

**Impact:** Contributors don't know what information to provide.

---

### 4. SECURITY.md (CRITICAL - Missing)

**Impact for network infrastructure software:**
- No clear channel for responsible disclosure
- Security researchers may disclose publicly
- No defined response process

---

### 5. CONTRIBUTING.md (Needs Updates)

| Line | Issue | Fix |
|------|-------|-----|
| 25 | References `black` | Update to `ruff format` |
| 63-66 | Outdated test commands | Update to `./qa/bin/test_everything` |
| 78-81 | References `black -S -l 120` | Update to `ruff format` |

---

## Implementation Plan

### Phase 1: Critical (1-2 hours)

| # | Task | File |
|---|------|------|
| 1 | Create SECURITY.md | `SECURITY.md` |
| 2 | Create PR template | `.github/PULL_REQUEST_TEMPLATE.md` |
| 3 | Create issue config | `.github/ISSUE_TEMPLATE/config.yml` |
| 4 | Create CODEOWNERS | `.github/CODEOWNERS` |

### Phase 2: High Value (2-3 hours)

| # | Task | File |
|---|------|------|
| 5 | Upgrade bug report to YAML form | `.github/ISSUE_TEMPLATE/bug_report.yml` |
| 6 | Upgrade feature request to YAML form | `.github/ISSUE_TEMPLATE/feature_request.yml` |
| 7 | Update CONTRIBUTING.md | `CONTRIBUTING.md` |
| 8 | Create release notes config | `.github/release.yml` |

### Phase 3: Nice to Have (1-2 hours)

| # | Task | File |
|---|------|------|
| 9 | Add labeler config | `.github/labeler.yml` |
| 10 | Add labeler workflow | `.github/workflows/labeler.yml` |
| 11 | Add stale workflow | `.github/workflows/stale.yml` |
| 12 | Expand dependabot | `.github/dependabot.yml` |

---

## Proposed File Contents

### SECURITY.md

```markdown
# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 6.x     | :white_check_mark: |
| 5.x     | :white_check_mark: (security fixes only) |
| < 5.0   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via GitHub's private vulnerability reporting:
https://github.com/Exa-Networks/exabgp/security/advisories/new

Please include:
- Type of vulnerability
- Full paths of affected source files
- Steps to reproduce
- Proof-of-concept or exploit code (if available)
- Impact assessment

## Response Timeline

- Initial response: within 72 hours
- Status update: within 7 days
- Fix timeline: depends on severity
```

### .github/PULL_REQUEST_TEMPLATE.md

```markdown
## Description
<!-- What does this PR do? Why is it needed? -->

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update
- [ ] Refactoring (no functional changes)
- [ ] Test improvement

## Testing Performed
- [ ] `./qa/bin/test_everything` passes
- [ ] Manual testing performed (describe below)

## Checklist
- [ ] My code follows the project's style (`ruff format` / `ruff check`)
- [ ] I have updated documentation if needed
- [ ] I have added tests if applicable
- [ ] Breaking changes are documented

## Related Issues
<!-- Fixes #123, Relates to #456 -->
```

### .github/ISSUE_TEMPLATE/config.yml

```yaml
blank_issues_enabled: false
contact_links:
  - name: Documentation / Wiki
    url: https://github.com/Exa-Networks/exabgp/wiki
    about: Check existing documentation before filing an issue
  - name: Questions / Discussions
    url: https://github.com/Exa-Networks/exabgp/discussions
    about: Ask questions in GitHub Discussions
  - name: Security Vulnerabilities
    url: https://github.com/Exa-Networks/exabgp/security/advisories/new
    about: Report security issues privately (do NOT open public issues)
```

### .github/CODEOWNERS

```
# Default owner for everything
* @thomas-mangin
```

### .github/ISSUE_TEMPLATE/bug_report.yml (Phase 2)

```yaml
name: Bug Report
description: Report a bug to help us improve
title: "[Bug]: "
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to fill out this bug report!

        **Before submitting:**
        - Check the [wiki](https://github.com/Exa-Networks/exabgp/wiki) for known issues
        - Search [existing issues](https://github.com/Exa-Networks/exabgp/issues) to avoid duplicates
        - Test with the `main` branch if possible

  - type: input
    id: version
    attributes:
      label: ExaBGP Version
      description: Output of `exabgp --version`
      placeholder: "6.0.0"
    validations:
      required: true

  - type: input
    id: python
    attributes:
      label: Python Version
      description: Output of `python --version`
      placeholder: "3.12.0"
    validations:
      required: true

  - type: dropdown
    id: os
    attributes:
      label: Operating System
      options:
        - Linux (Ubuntu/Debian)
        - Linux (RHEL/CentOS/Rocky)
        - Linux (Other)
        - macOS
        - FreeBSD
        - Other
    validations:
      required: true

  - type: textarea
    id: description
    attributes:
      label: Bug Description
      description: Clear and concise description of the bug
    validations:
      required: true

  - type: textarea
    id: config
    attributes:
      label: Configuration
      description: Relevant configuration (sanitize sensitive data)
      render: text
    validations:
      required: true

  - type: textarea
    id: logs
    attributes:
      label: Debug Output
      description: |
        Output from running with `-d` flag: `exabgp -d your.conf`
        Do NOT edit or obfuscate the output.
      render: text
    validations:
      required: true

  - type: textarea
    id: steps
    attributes:
      label: Steps to Reproduce
      description: Steps to reproduce the behavior
      placeholder: |
        1. Start exabgp with config...
        2. Send BGP message...
        3. See error...
    validations:
      required: true

  - type: textarea
    id: expected
    attributes:
      label: Expected Behavior
      description: What you expected to happen
    validations:
      required: true
```

---

## Files Summary

| Action | File | Phase |
|--------|------|-------|
| CREATE | `SECURITY.md` | P1 |
| CREATE | `.github/PULL_REQUEST_TEMPLATE.md` | P1 |
| CREATE | `.github/ISSUE_TEMPLATE/config.yml` | P1 |
| CREATE | `.github/CODEOWNERS` | P1 |
| REPLACE | `.github/ISSUE_TEMPLATE/bug_report.md` → `.yml` | P2 |
| REPLACE | `.github/ISSUE_TEMPLATE/feature_request.md` → `.yml` | P2 |
| MODIFY | `CONTRIBUTING.md` | P2 |
| CREATE | `.github/release.yml` | P2 |
| CREATE | `.github/labeler.yml` | P3 |
| CREATE | `.github/workflows/labeler.yml` | P3 |
| CREATE | `.github/workflows/stale.yml` | P3 |
| MODIFY | `.github/dependabot.yml` | P3 |

---

## Progress

- [ ] Phase 1 approved
- [ ] Phase 1 implemented
- [ ] Phase 2 approved
- [ ] Phase 2 implemented
- [ ] Phase 3 approved
- [ ] Phase 3 implemented

---

## Resume Point

**Next action:** Get approval for Phase 1 implementation

---

**Updated:** 2025-12-15
