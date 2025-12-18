# Runtime Crash Prevention Audit

**Status:** ✅ Complete
**Created:** 2025-12-04
**Completed:** 2025-12-16
**Priority:** Security/Stability

---

## Summary

Systematic audit of all parsing code to identify and fix missing length/bounds validation that could cause runtime crashes (IndexError, struct.error, ValueError) when processing malformed data.

**Result:** Codebase is well-protected against malformed message crashes.

| Module | Issues Fixed |
|--------|--------------|
| BGP-LS | 12 |
| BGP Messages | 0 (already validated) |
| Capabilities | 0 (already validated) |
| Attributes | 0 (already validated) |
| NLRI Types | 0 (already validated) |
| Protocol Layer | 0 (already validated) |

---

## BGP-LS Fixes (12 issues)

### SRv6 Parsing (6 issues)
| File | Fix |
|------|-----|
| srv6endx.py | 22 byte minimum |
| srv6lanendx.py | 28/26 bytes (ISIS/OSPF) |
| srv6sidstructure.py | 4 byte minimum |
| srv6locator.py | 8 byte minimum |
| srv6endpointbehavior.py | 4 byte minimum |
| srcap.py | Initial + per-iteration |

### SR Adjacency (2 issues)
| File | Fix |
|------|-----|
| sradjlan.py | 10 byte minimum |
| sradj.py | 4 byte minimum |

### Core Parsing (2 issues)
| File | Fix |
|------|-----|
| linkstate.py | TLV header + payload validation |
| linkstate.py | Empty flags check |

### Node Attributes (2 issues)
| File | Fix |
|------|-----|
| isisarea.py | Empty data check |
| srprefix.py | 4 byte minimum |

---

## Fix Pattern

```python
# VULNERABLE
def unpack(cls, data: bytes) -> SomeClass:
    value = data[3]  # IndexError if len(data) < 4

# SAFE
MIN_LENGTH = 4

def unpack(cls, data: bytes) -> SomeClass:
    if len(data) < MIN_LENGTH:
        raise Notify(3, 5, f'{cls.REPR}: data too short')
    value = data[3]
```

---

## References

- BGP: RFC 4271
- BGP-LS: RFC 7752
- SR Extensions: RFC 8667, RFC 9085
- SRv6: RFC 9252, RFC 9514
