# GitHub Project Setup Best Practices

**Source:** [Top 10 GitHub Project Setup Tricks You MUST Use in 2025!](https://www.youtube.com/watch?v=gYl3moYa4iI) by DevOps & AI Toolkit

**Purpose:** Reference document for modernizing exabgp's GitHub repository configuration.

---

## Summary of Best Practices

### 1. Issue Templates with Structured Forms

**Problem:** Vague bug reports ("it's broken") waste maintainer time playing detective.

**Solution:** GitHub issue templates with YAML forms that:
- Guide users through structured fields (description, steps to reproduce, expected vs actual behavior, environment)
- Mark required fields
- Include "before submitting" checklists (search existing issues, check docs)
- Disable blank issues to force template usage

**Configuration:**
- `.github/ISSUE_TEMPLATE/config.yml` - disable blank issues, add contact links
- `.github/ISSUE_TEMPLATE/bug_report.yml` - structured bug report form
- `.github/ISSUE_TEMPLATE/feature_request.yml` - problem-focused feature requests

**Key insight:** Templates reveal intent. If someone circumvents guidance, you know you're dealing with someone who ignored the process deliberately.

---

### 2. Issue Template Config with Resource Links

**Problem:** People open issues for questions, support requests, or security reports that belong elsewhere.

**Solution:** Config file that shows a menu before creating issues:
- Link to GitHub Discussions for questions
- Link to documentation
- Link to support resources
- Private channel for security vulnerabilities

**Configuration:** `.github/ISSUE_TEMPLATE/config.yml`
```yaml
blank_issues_enabled: false
contact_links:
  - name: Questions
    url: https://github.com/org/repo/discussions
    about: Ask questions in Discussions
  - name: Documentation
    url: https://example.com/docs
    about: Check existing documentation
  - name: Security
    url: https://example.com/security
    about: Report security vulnerabilities privately
```

---

### 3. Pull Request Templates

**Problem:** PRs with no context make code review impossible.

**Solution:** PR template markdown file requiring:
- What changed and why
- Type of change (feature/bug fix/refactor/docs)
- Testing performed
- Breaking changes analysis
- Security considerations
- Documentation updates needed

**Configuration:** `.github/PULL_REQUEST_TEMPLATE.md`

**Bonus:** Works for both humans AND AI coding agents - agents can parse templates to understand what information to provide.

---

### 4. CODEOWNERS for Automatic Review Assignment

**Problem:** PRs sit unreviewed because no one was assigned.

**Solution:** CODEOWNERS file maps file paths to responsible reviewers:
```
* @default-owner
/docs/ @docs-team
/src/core/ @architecture-team
/.github/ @devops-team
```

**Configuration:** `.github/CODEOWNERS`

When files are changed, corresponding owners are automatically requested as reviewers.

---

### 5. Automatic PR Labeling

**Problem:** No one remembers to label PRs correctly, making release notes disorganized.

**Solution:** GitHub Actions workflow + labeler configuration:
- Maps file path patterns to labels
- Applies labels automatically on PR creation
- Enables organized release notes

**Configuration:**
- `.github/labeler.yml` - path-to-label mappings
- `.github/workflows/labeler.yml` - workflow to run labeler

Example mappings:
```yaml
documentation:
  - docs/**
  - '*.md'
tests:
  - tests/**
ci-cd:
  - .github/workflows/**
```

---

### 6. Organized Release Notes

**Problem:** Release notes are unorganized lists of changes.

**Solution:** Configure release notes to use PR labels for categorization:

**Configuration:** `.github/release.yml`
```yaml
changelog:
  categories:
    - title: New Features
      labels: [feature, enhancement]
    - title: Bug Fixes
      labels: [bug, fix]
    - title: Documentation
      labels: [documentation]
    - title: Dependencies
      labels: [dependencies]
  exclude:
    labels: [skip-changelog]
```

---

### 7. Security Scanning (OpenSSF Scorecard)

**Problem:** Projects lack visibility into security best practices.

**Solution:** OpenSSF Scorecard GitHub Action:
- Evaluates against security best practices
- Checks: pinned dependencies, code review, security policies
- Generates badge for README
- Uploads results to GitHub's code scanning dashboard

**Configuration:** `.github/workflows/scorecard.yml`

Runs on push to main + weekly schedule.

---

### 8. Automated Dependency Updates (Renovate/Dependabot)

**Problem:** Dependencies fall months/years behind, creating security risks.

**Solution:** Renovate or Dependabot automatically:
- Creates PRs when new versions available
- Groups related updates
- Auto-merges safe updates (dev deps, patch/minor versions)
- Requires review for major updates

**Configuration:** `renovate.json` or `.github/dependabot.yml`

Key settings:
- Auto-merge rules for low-risk updates
- Grouping related packages
- Schedule (weekly/monthly)
- Required reviewers for major updates

---

### 9. Stale Issue/PR Management

**Problem:** Hundreds of issues accumulate, many irrelevant.

**Solution:** Stale bot workflow:
- Marks issues/PRs without activity as stale
- Gives grace period for response
- Auto-closes if no activity
- Exempts issues with certain labels (security) or assigned to milestones

**Configuration:** `.github/workflows/stale.yml`

Typical settings:
- Issues: 60 days to stale, 7 days to close
- PRs: 30 days to stale, 7 days to close
- Exempt labels: security, pinned, help-wanted

---

### 10. Governance Documentation

**Essential files:**

| File | Purpose |
|------|---------|
| `README.md` | What, why, who, how to get started |
| `LICENSE` | Legal permissions (MIT, Apache, GPL) |
| `CONTRIBUTING.md` | How to contribute, style guides |
| `CODE_OF_CONDUCT.md` | Community behavior expectations |
| `SECURITY.md` | How to report vulnerabilities |
| `SUPPORT.md` | Where to get help |

**Key insight:** These aren't just for open source - internal projects benefit equally from clear processes.

---

## Current State Assessment for exabgp

### Already Have:
- [x] Issue templates (`.github/ISSUE_TEMPLATE/bug_report.md`, `feature_request.md`) - OLD FORMAT (markdown, not YAML forms)
- [ ] Issue template config (no `config.yml` - no resource links menu)
- [ ] PR template (only `PULL_REQUEST_TEMPLATE_ASYNC_MIGRATION.md` - not default template)
- [ ] CODEOWNERS
- [ ] Labeler workflow
- [ ] Release notes config
- [x] Security scanning - CodeQL analysis workflow exists
- [x] Dependabot - GitHub Actions only (`.github/dependabot.yml`)
- [ ] Stale workflow
- [x] LICENSE - `LICENCE.txt` (BSD License)
- [x] CONTRIBUTING.md - exists, good content
- [ ] CODE_OF_CONDUCT.md
- [ ] SECURITY.md

### Existing CI/CD Workflows:
- `codeql-analysis.yml` - Security scanning
- `release.yml` - Release workflow
- `container.yml` - Container builds
- `functional-testing.yml` - Functional tests
- `linting.yml` - Code linting
- `sync-requirements.yml` - Requirements sync
- `type-checking.yml` - Type checking
- `unit-testing.yml` - Unit tests

### Gaps to Address:

| Item | Current State | Recommended Action |
|------|---------------|-------------------|
| Issue templates | Old markdown format | Upgrade to YAML forms with required fields |
| Issue config | Missing | Add config.yml with resource links |
| PR template | Missing default | Create `.github/PULL_REQUEST_TEMPLATE.md` |
| CODEOWNERS | Missing | Add for automatic reviewer assignment |
| SECURITY.md | Missing | Critical - add security reporting policy |
| CODE_OF_CONDUCT.md | Missing | Optional - consider for community |
| Labeler | Missing | Add for auto-labeling based on files |
| Release notes | Not configured | Add `.github/release.yml` |
| Stale bot | Missing | Add for issue hygiene |
| Dependabot | Actions only | Consider adding for Python dependencies |

### Recommended Implementation Priority:

**Phase 1 - High Impact, Low Effort (do first):**
1. SECURITY.md - Establishes vulnerability reporting (critical for network software)
2. Default PR template - Improves contribution quality
3. Issue template config - Adds resource links menu

**Phase 2 - Medium Impact, Medium Effort:**
4. Upgrade issue templates to YAML forms with required fields
5. CODEOWNERS file
6. Release notes configuration

**Phase 3 - Nice to Have:**
7. Automatic PR labeling
8. Stale issue workflow
9. OpenSSF Scorecard badge
10. CODE_OF_CONDUCT.md

---

## Implementation Plan Considerations

### Issue Templates for exabgp

Bug reports should require:
- ExaBGP version (`exabgp --version`)
- Python version
- OS/platform
- Configuration file (sanitized)
- Logs with appropriate log level
- Steps to reproduce
- Expected vs actual behavior

Feature requests should require:
- Use case / problem being solved
- BGP RFC reference if applicable
- Proposed implementation approach (optional)

### PR Template for exabgp

Should include:
- Description of changes
- Type: feature / bugfix / refactor / docs / test
- Testing performed (unit tests, functional tests)
- Breaking changes?
- RFC compliance (if applicable)
- Documentation updates needed

### CODEOWNERS Mapping

Potential structure:
```
* @thomas-mangin
/src/exabgp/bgp/ @thomas-mangin
/src/exabgp/reactor/ @thomas-mangin
/.github/ @thomas-mangin
/doc/ @thomas-mangin
```

---

## References

- [GitHub Issue Forms](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/configuring-issue-templates-for-your-repository)
- [PR Templates](https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/creating-a-pull-request-template-for-your-repository)
- [CODEOWNERS](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)
- [OpenSSF Scorecard](https://securityscorecards.dev/)
- [Renovate](https://docs.renovatebot.com/)
- [GitHub Labeler Action](https://github.com/actions/labeler)

---

**Created:** 2025-12-15
**Status:** Reference document for planning
