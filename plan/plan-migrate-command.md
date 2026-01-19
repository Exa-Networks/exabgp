# Plan: Configuration Migration Command

**Status:** ✅ Complete
**Created:** 2025-01-19
**Last Updated:** 2025-01-19

## Overview

Add `exabgp migrate` CLI command to transform configuration files and API commands between versions:
- 3.4 → 4 → 5 → main (6.0)

**Approach:** Text transformation (regex/string replacements) preserving comments and formatting.

## Migration Rules

### Config: 3.4 → 4

| Change | Before | After |
|--------|--------|-------|
| Process reference | `process <name>;` inside neighbor | `api { processes [ <name> ]; }` |
| Encoder required | (none) | Add `encoder text;` to process blocks |
| Route-refresh | `route-refresh;` | `route-refresh enable;` |

### Config: 4 → 5

| Change | Before | After |
|--------|--------|-------|
| Route refresh keyword | `route refresh` | `route-refresh` |
| TCP once | `tcp.once true` | `tcp.attempts 1` |
| Fragment match | `fragment not-a-fragment` | `fragment !is-fragment` |
| Syslog facility | `facility syslog` | `facility daemon` |

### Config: 5 → main

| Change | Before | After |
|--------|--------|-------|
| NLRI-MPLS alias | `nlri-mpls` | `labeled-unicast` |

### API: 4 → main (v6)

| Change | Before | After |
|--------|--------|-------|
| Shutdown | `shutdown` | `daemon shutdown` |
| Announce | `announce route ...` | `peer * announce route ...` |
| Neighbor | `neighbor 1.2.3.4 ...` | `peer 1.2.3.4 ...` |
| Show RIB | `show adj-rib out` | `rib show out` |

## Implementation

### CLI Interface

```bash
# Config migration
exabgp migrate conf -f <version> -t <version> [options] <config-file>
  -o, --output     Output file (default: stdout)
  -i, --inplace    Modify file in place (creates timestamped backup)
  -n, --dry-run    Show changes without applying
  -v, --verbose    Show each transformation
  -w, --wrap-api   Wrap run commands with API migration bridge

# API migration (stdin/stdout bridge)
exabgp migrate api -f <version> -t <version> [options] [input]
  -v, --verbose    Show each transformation
  -e, --exec       Execute command with bidirectional transformation
```

### Examples

```bash
# Migrate config and load directly
exabgp migrate conf -f 3.4 -t main old.conf | exabgp server -

# Migrate with API bridge for scripts
exabgp migrate conf -f 3.4 -t main -w old.conf | exabgp server -

# Preview changes
exabgp migrate conf -f 3.4 -t main --dry-run old.conf

# Migrate API commands
echo "shutdown" | exabgp migrate api -f 4 -t main
# Output: daemon shutdown
```

## Tasks

| # | Task | Status |
|---|------|--------|
| 1 | Create `src/exabgp/application/migrate.py` | ✅ |
| 2 | Register in `main.py` | ✅ |
| 3 | Implement 3.4 → 4 config transforms | ✅ |
| 4 | Implement 4 → 5 config transforms | ✅ |
| 5 | Implement 5 → main config transforms | ✅ |
| 6 | Implement API command transforms | ✅ |
| 7 | Implement JSON key transforms | ✅ |
| 8 | Add bidirectional --exec mode | ✅ |
| 9 | Add stdin config support to server | ✅ |
| 10 | Add --wrap-api to conf migration | ✅ |
| 11 | Add unit tests (64 tests) | ✅ |
| 12 | Add functional tests (7 .mi files) | ✅ |
| 13 | Integrate into test_everything | ✅ |
| 14 | Add .claude reference doc | ✅ |
| 15 | Add bridge test for --exec mode | ✅ |

## Files

| File | Purpose |
|------|---------|
| `src/exabgp/application/migrate.py` | Main implementation |
| `src/exabgp/application/server.py` | Stdin config support |
| `tests/unit/test_migrate.py` | Unit tests |
| `qa/bin/test_migrate` | Functional test runner |
| `qa/migrate/*.mi` | Functional test cases (7 tests) |
| `.claude/exabgp/MIGRATE_COMMAND.md` | Reference documentation |

## Known Limitations

1. Brace matching ignores strings/comments
2. Hardcoded 4-space indentation for encoder insertion
3. Semicolons in quoted arguments may split incorrectly
4. No backwards migration (only old → new)

## References

- Wiki: [From 3.4 to 4.x](https://github.com/Exa-Networks/exabgp/wiki/From-3.4-to-4.x)
- Wiki: [From 4.x to 5.x](https://github.com/Exa-Networks/exabgp/wiki/From-4.x-to-5.x)
- 5.0 → main changes: Analyzed from git history
