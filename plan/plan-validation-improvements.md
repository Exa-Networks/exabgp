# Plan: Data Validation Improvements

## Overview

Several validation functions in `data/check.py` have TODO markers indicating incomplete validation.

## Items

### 1. Watchdog Name Validation (line 226)

Current:
```python
def watchdog(data: Any) -> bool:
    return ' ' not in data  # TODO: improve
```

Improvement:
- Validate watchdog name format (alphanumeric + allowed chars)
- Check length limits
- Reject reserved names if any

### 2. Extended Community Validation (line 282)

Current:
```python
def extendedcommunity(data: Any) -> bool:  # TODO: improve, incomplete see RFC 4360
```

Improvement:
- Support all extended community types per RFC 4360
- Validate type-specific formats
- Handle 4-byte ASN variants

### 3. Redirect Community Validation (line 357)

Current:
```python
def redirect(data: Any) -> bool:  # TODO: check restrictiveness
```

Improvement:
- Review ASN validation (asn16 vs asn32)
- Support IPv6 redirect targets
- Validate against FlowSpec redirect community format

### 4. ACK Format Configuration (processes.py:274)

Current:
```python
# TODO: Future enhancement - add 'ack-format' config option
self._ackjson[process] = False
```

Improvement:
- Add `ack-format json;` config option
- Send `{"status": "ok"}` instead of "done" when enabled
- Per-process configuration

## Steps

1. [ ] Improve watchdog validation
2. [ ] Improve extended community validation
3. [ ] Review redirect ASN validation
4. [ ] Implement ack-format config option
5. [ ] Add unit tests for each improvement

## Priority

Low - Current validation is sufficient for most use cases.

## Files Affected

- `data/check.py` - validation functions
- `reactor/api/processes.py` - ack-format option
- `configuration/process/__init__.py` - config parsing for ack-format
