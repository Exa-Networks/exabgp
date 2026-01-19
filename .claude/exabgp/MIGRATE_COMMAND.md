# Migrate Command Reference

The `exabgp migrate` command transforms configuration files and API commands between ExaBGP versions.

## Subcommands

### `exabgp migrate conf`

Migrate configuration files.

```bash
exabgp migrate conf -f <from> -t <to> [options] <config-file>

Options:
  -f, --from      Source version (3.4, 4, 5)
  -t, --to        Target version (4, 5, main)
  -o, --output    Output file (default: stdout)
  -i, --inplace   Modify in place (creates .YYYYMMDD-HHMMSS.bak)
  -n, --dry-run   Show changes without applying
  -v, --verbose   Show each transformation
  -w, --wrap-api  Wrap run commands with API migration bridge
```

### `exabgp migrate api`

Migrate API commands/JSON (stdin/stdout bridge).

```bash
exabgp migrate api -f <from> -t <to> [options] [input]

Options:
  -f, --from      Source API version (4, 5)
  -t, --to        Target API version (5, main)
  -v, --verbose   Show each transformation
  -e, --exec      Execute command with bidirectional transformation
```

## Migration Rules

### Config: 3.4 → 4

| Change | Before | After |
|--------|--------|-------|
| Process reference | `process foo;` | `api { processes [ foo ]; }` |
| Encoder required | (none) | `encoder text;` in process blocks |
| Route-refresh | `route-refresh;` | `route-refresh enable;` |

### Config: 4 → 5

| Change | Before | After |
|--------|--------|-------|
| Route refresh | `route refresh` | `route-refresh` |
| TCP once | `tcp.once true` | `tcp.attempts 1` |
| TCP once | `tcp.once false` | `tcp.attempts 0` |
| Fragment | `not-a-fragment` | `!is-fragment` |
| Facility | `facility syslog` | `facility daemon` |

### Config: 5 → main

| Change | Before | After |
|--------|--------|-------|
| NLRI-MPLS | `nlri-mpls` | `labeled-unicast` |

### API: 4 → main (v6)

| Change | Before | After |
|--------|--------|-------|
| Shutdown | `shutdown` | `daemon shutdown` |
| Reload | `reload` | `daemon reload` |
| Announce | `announce route ...` | `peer * announce route ...` |
| Withdraw | `withdraw route ...` | `peer * withdraw route ...` |
| Neighbor | `neighbor 1.2.3.4 ...` | `peer 1.2.3.4 ...` |
| Show RIB | `show adj-rib out` | `rib show out` |
| Show peers | `show neighbor` | `peer show` |

### JSON Key Renames

| Version | Old Key | New Key | Context |
|---------|---------|---------|---------|
| 4→5 | `sr_capability_flags` | `sr-capability-flags` | bgp-ls |
| 4→5 | `interface-address` | `interface-addresses` | bgp-ls |
| 4→5 | `neighbor-address` | `neighbor-addresses` | bgp-ls |
| 5→main | `ip` | `prefix` | ip-reachability-tlv |

## Exec Mode (Bidirectional Bridge)

When using `--exec`, the migrate command acts as a bidirectional bridge:

```
ExaBGP (main/v6)
    │
    │ sends v6 JSON events
    ▼
[stdin: reverse transform v6 → v4]
    │
    ▼
old-script.py (expects v4)
    │
    │ outputs v4 commands
    ▼
[stdout: forward transform v4 → v6]
    │
    ▼
ExaBGP (main/v6)
```

This allows unmodified legacy scripts to work with new ExaBGP.

## Usage Patterns

### Migrate and load directly

```bash
exabgp migrate conf -f 3.4 -t main old.conf | exabgp server -
```

### Migrate with API bridge for scripts

```bash
exabgp migrate conf -f 3.4 -t main -w old.conf | exabgp server -
```

The `-w` flag transforms:
```
run /path/to/script.py;
```
Into:
```
run exabgp migrate api -f 4 -t main --exec /path/to/script.py;
```

### Preview changes

```bash
exabgp migrate conf -f 3.4 -t main --dry-run old.conf
```

### Migrate in place

```bash
exabgp migrate conf -f 4 -t main -i config.conf
# Creates config.conf.20250119-143022.bak
```

## Source Files

| File | Purpose |
|------|---------|
| `src/exabgp/application/migrate.py` | Main implementation |
| `src/exabgp/application/server.py` | Stdin config support |
| `qa/bin/test_migrate` | Test runner |
| `qa/migrate/*.mi` | Test cases |
| `tests/unit/test_migrate.py` | Unit tests |

## Test File Format (.mi)

### Basic Format (conf/api tests)

```
from:3.4
to:main
wrap-api:true        # optional
type:api             # optional, default: conf

input:<<<
# config or commands here
>>>

expect:pattern       # must contain
reject:pattern       # must NOT contain
```

### Bridge Test Format (--exec mode)

```
type:bridge
from:4
to:main

script:<<<
#!/usr/bin/env python3
# Script that outputs v4 commands
print('announce route 10.0.0.0/24 next-hop 1.2.3.4')
print('shutdown')
>>>

input:<<<
# Simulated v6 JSON input (what ExaBGP would send)
{"exabgp":"6.0.0","type":"update",...}
>>>

expect:peer * announce route 10.0.0.0/24
expect:daemon shutdown
reject:^announce route
reject:^shutdown$
```

Bridge tests verify bidirectional transformation:
- Script outputs → transformed v4→v6 (checked via expect/reject)
- Input JSON → transformed v6→v4 (passed to script stdin)

## Known Limitations

1. **Brace matching ignores strings/comments**: `{ "}" }` may confuse parser
2. **Hardcoded 4-space indent**: Encoder insertion uses 4 spaces
3. **Semicolons in quoted args**: `run /bin/test "arg;";` may split wrong
4. **No backwards migration**: Only forward (old → new) supported
