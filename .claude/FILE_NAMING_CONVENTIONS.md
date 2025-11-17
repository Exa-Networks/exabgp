# File Naming Conventions

**Last Updated:** 2025-11-17

## Standard: lowercase-with-hyphens

All documentation and code files should follow lowercase naming with hyphens as separators, **except** for special top-level files.

---

## Rules

### 1. Special Top-Level Files (UPPERCASE)

These files use UPPERCASE because they are standard project files recognized across all repositories:

- `README.md` - Project readme (standard across all repos)
- `INDEX.md` - Top-level index/table of contents
- `CHANGELOG.md` - Change history
- `LICENSE` - License file
- `CONTRIBUTING.md` - Contribution guidelines
- `CLAUDE.md` - Claude Code project instructions

**Rationale:** These are universal project files with established conventions.

### 2. All Other Files (lowercase-with-hyphens)

Everything else uses lowercase with hyphens:

```
✅ Good:
async-architecture.md
api-integration.md
conversion-patterns.md
generator-inventory.md
phase-1.md
phase-2-poc.md
session-summary-io-optimization.md

❌ Bad:
ASYNC_ARCHITECTURE.md
API_INTEGRATION.md
AsyncArchitecture.md
async_architecture.md
```

**Rationale:**
- Easier to type (no shift key)
- Works on case-insensitive filesystems
- Standard across modern projects
- Better URL compatibility
- Avoids confusion between underscores and hyphens

### 3. Separator: Use Hyphens, Not Underscores

```
✅ Good:
api-integration.md
phase-b-part2-session-summary.md

❌ Bad:
api_integration.md
phase_b_part2_session_summary.md
```

**Rationale:** Hyphens are more common in documentation and web URLs.

---

## Examples

### Documentation Structure

```
docs/
├── README.md                          # ✅ Special file
├── INDEX.md                           # ✅ Special file
├── asyncio-migration/                 # ✅ lowercase
│   ├── README.md                      # ✅ Special file
│   ├── INDEX.md                       # ✅ Special file
│   ├── async-architecture.md          # ✅ lowercase
│   ├── overview/
│   │   ├── completion.md              # ✅ lowercase
│   │   └── progress.md                # ✅ lowercase
│   ├── technical/
│   │   ├── api-integration.md         # ✅ lowercase
│   │   ├── conversion-patterns.md     # ✅ lowercase
│   │   └── lessons-learned.md         # ✅ lowercase
│   └── phases/
│       ├── phase-1.md                 # ✅ lowercase
│       ├── phase-2-poc.md             # ✅ lowercase
│       └── phase-a.md                 # ✅ lowercase
```

### Code Files

```
src/
├── __init__.py                        # ✅ Python convention
├── async-reactor.py                   # ✅ lowercase (if creating new files)
└── network/
    ├── connection.py                  # ✅ lowercase
    └── outgoing.py                    # ✅ lowercase
```

**Note:** Existing Python code uses `snake_case` module names (standard Python convention). This is fine - don't rename existing code files.

---

## Migration Guide

If you find UPPERCASE documentation files (other than special files), rename them:

```bash
# Example renaming
git mv ASYNC_ARCHITECTURE.md async-architecture.md
git mv API_INTEGRATION.md api-integration.md

# Update references in other files
sed -i '' 's/ASYNC_ARCHITECTURE\.md/async-architecture.md/g' *.md
```

---

## When Creating New Files

### Documentation

```bash
# New technical doc
touch docs/new-feature-guide.md          # ✅ Correct

# NOT:
touch docs/NEW_FEATURE_GUIDE.md          # ❌ Wrong
touch docs/NewFeatureGuide.md            # ❌ Wrong
touch docs/new_feature_guide.md          # ❌ Wrong (underscores)
```

### Code

Follow the language/framework conventions:
- **Python:** `snake_case.py` (existing convention)
- **JavaScript:** `camelCase.js` or `kebab-case.js` (project convention)
- **Markdown:** `kebab-case.md` (this standard)

---

## Exceptions

### Archive Files

Files in `archive/` directories can keep their original names for historical accuracy, but should be renamed if actively referenced.

### Auto-Generated Files

Files created by tools (e.g., `coverage.xml`, `pytest.ini`) follow their tool's conventions.

### External Dependencies

Files from external sources (vendored code, submodules) keep their original names.

---

## Claude Code Instructions

**When creating new documentation files:**

1. Check if it's a special top-level file (README.md, INDEX.md, etc.)
   - If yes: Use UPPERCASE
   - If no: Use lowercase-with-hyphens

2. Use hyphens, not underscores, for word separation

3. Example decision tree:
   ```
   Creating "Migration Guide" doc?

   Q: Is it README or INDEX?
   A: No

   → Use: migration-guide.md
   NOT: MIGRATION_GUIDE.md
   NOT: MigrationGuide.md
   NOT: migration_guide.md
   ```

**When renaming files:**

1. Use `git mv` to preserve history
2. Update all references in other files
3. Check for broken links
4. Commit with clear message about standardization

---

## Rationale Summary

| Aspect | Choice | Why |
|--------|--------|-----|
| Case | lowercase | Easier to type, cross-platform compatible |
| Separator | hyphens | Web-standard, common in docs |
| Special files | UPPERCASE | Universal convention (README, LICENSE) |
| Consistency | Strict | Prevents confusion, easier maintenance |

---

## References

- [GitHub docs style guide](https://docs.github.com/en/contributing/style-guide-and-content-model/style-guide)
- [Microsoft docs naming](https://learn.microsoft.com/en-us/contribute/file-names-and-locations)
- [Google developer docs](https://developers.google.com/style/filenames)

---

**This convention was established:** 2025-11-17
**Applied to:** docs/asyncio-migration/ (29 files standardized)
