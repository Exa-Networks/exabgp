---
description: Run validation tests (quick lint or full suite)
allowed-tools: Bash
---

# Validate

Run validation tests for ExaBGP.

## Arguments

$ARGUMENTS - Optional: `quick` or `full`. Default: `full`

## Modes

| Mode | Command | Duration |
|------|---------|----------|
| `quick` | Lint only | ~30s |
| `full` | Full test suite | ~5min |

## Instructions

### If $ARGUMENTS is "quick" or "1":

Run lint check only:
```bash
uv run ruff format --check src && uv run ruff check src
```

### Otherwise (default "full"):

Run complete test suite:
```bash
./qa/bin/test_everything
```

## Notes

- Use `quick` during development for fast feedback
- Use `full` (default) before committing or when claiming "done"
- The auto-linter hook already formats on save, so `quick` mainly catches issues in files you didn't edit
