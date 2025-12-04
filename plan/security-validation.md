# Security: Input Validation and Error Sanitization

**Status:** 📋 Planning (not started)
**Priority:** Medium
**See also:** `runtime-validation/` (parsing layer validation)

## Goal

Harden ExaBGP against malicious or malformed input at the configuration and API layers:

1. **Configuration Parser Validation** - Reject invalid configs early with clear errors
2. **Error Message Sanitization** - Prevent information leakage in external-facing APIs

## Scope

### In Scope

- Configuration file parsing (`src/exabgp/configuration/`)
- API command parsing (`src/exabgp/reactor/api/command/`)
- Error messages returned via JSON/text API responses
- CLI error output

### Out of Scope

- Wire protocol validation (covered in `runtime-validation/`)
- Authentication/authorization (ExaBGP trusts configured processes)

---

## Part 1: Configuration Parser Validation

### Current State

The configuration parser (`src/exabgp/configuration/`) does validation but may have gaps:
- Some values accepted without range checking
- Some type coercions may fail silently
- Error messages may be unclear

### Audit Areas

| Area | Files | Priority |
|------|-------|----------|
| Neighbor config | `configuration/neighbor/` | High |
| Route attributes | `configuration/static/parser.py` | High |
| Flow rules | `configuration/flow/parser.py` | Medium |
| Capabilities | `configuration/capability.py` | Medium |
| Templates | `configuration/template/` | Low |

### Validation Categories

1. **Type validation** - Ensure values are correct type
2. **Range validation** - Ensure numeric values within valid ranges
3. **Format validation** - Ensure strings match expected patterns (IP, ASN, etc.)
4. **Semantic validation** - Ensure combinations are valid (e.g., AFI/SAFI pairs)

### Example Fixes Needed

```python
# WEAK: accepts any integer
def parse_asn(value: str) -> int:
    return int(value)

# STRONG: validates range
def parse_asn(value: str) -> int:
    asn = int(value)
    if not (0 <= asn <= 4294967295):  # 32-bit ASN
        raise ValueError(f'ASN must be 0-4294967295, got {asn}')
    return asn
```

### Files to Audit

```bash
# Find all parser functions
grep -rn "def parse" src/exabgp/configuration/ | wc -l

# Find potential issues
grep -rn "int(" src/exabgp/configuration/ | grep -v "range\|<\|>"
```

---

## Part 2: Error Message Sanitization

### Current State

Error messages may expose:
- Internal file paths
- Stack traces
- Configuration details
- System information

### Audit Areas

| Area | Files | Risk |
|------|-------|------|
| JSON API responses | `reactor/api/response/json.py` | High |
| Text API responses | `reactor/api/response/text.py` | High |
| CLI error output | `cli/cli.py` | Medium |
| Log messages | `logger/` | Low (usually internal) |

### Sanitization Rules

1. **No file paths** in API responses
2. **No stack traces** in API responses (log internally)
3. **Generic errors** for invalid input ("invalid command" not "parsing error at...")
4. **No version leakage** unless explicitly requested

### Example Fixes

```python
# LEAKY
except Exception as e:
    return f'{{"error": "{str(e)}"}}'  # May include paths, internals

# SAFE
except ConfigurationError as e:
    log.error(f'Config error: {e}')  # Log full details internally
    return '{"error": "configuration invalid"}'  # Generic to client
except Exception as e:
    log.exception('Unexpected error')  # Full trace to logs
    return '{"error": "internal error"}'  # Generic to client
```

### Files to Audit

```bash
# Find error response patterns
grep -rn "error" src/exabgp/reactor/api/response/
grep -rn "except.*:" src/exabgp/reactor/api/
```

---

## Implementation Plan

### Phase 1: Audit (Research)

1. List all parser functions in configuration/
2. Identify missing validations
3. List all API error response points
4. Categorize by risk level

### Phase 2: Configuration Validation

1. Add range checks for numeric values (ASN, port, timer values)
2. Add format validation for strings (IP addresses, route targets)
3. Improve error messages with specific guidance
4. Add unit tests for validation

### Phase 3: Error Sanitization

1. Create error response helper functions
2. Update API responses to use helpers
3. Ensure full details logged, generic sent to client
4. Add tests for error scenarios

---

## Testing

```bash
# After each change
./qa/bin/test_everything

# Specific validation tests
uv run pytest tests/unit/configuration/ -v

# Manual API testing
./sbin/exabgp --api test.conf &
echo "invalid command" | nc -U /var/run/exabgp.sock
```

---

## Risks

| Risk | Mitigation |
|------|------------|
| Too strict breaks valid configs | Test with real-world configs |
| Generic errors unhelpful | Keep detailed logs, reference error codes |
| Performance impact | Validation is fast, minimal overhead |

---

**Last Updated:** 2025-12-04
