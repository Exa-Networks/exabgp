# Phase 2: Fuzz BGP UPDATE Message Parser

**Estimated Time**: 6-8 hours
**Priority**: CRITICAL
**Depends On**: 01-FUZZ-MESSAGE-HEADER.md

**Target**: `src/exabgp/bgp/message/update/__init__.py::unpack_message()`

---

## Background

UPDATE is the most complex BGP message type. Structure:
- **Withdrawn Routes Length**: 2 bytes
- **Withdrawn Routes**: Variable (list of prefixes)
- **Path Attributes Length**: 2 bytes
- **Path Attributes**: Variable (complex TLV structures)
- **NLRI**: Variable (announced prefixes)

This is HIGH RISK as it processes untrusted route data.

---

## Task 2.1: Analyze UPDATE Message Structure

**Files to read**:
- `/home/user/exabgp/src/exabgp/bgp/message/update/__init__.py`
- `/home/user/exabgp/src/exabgp/bgp/message/update/attribute/attributes.py`

**What to do**:
1. Locate `unpack_message()` function
2. Understand the parsing logic:
   - How withdrawn routes are parsed
   - How path attributes are parsed
   - How NLRI is parsed
   - What validations are performed
3. Identify all exception types raised
4. Document the flow

**Questions to answer**:
- [ ] What does unpack_message() return?
- [ ] What parameters does it take?
- [ ] How are lengths validated?
- [ ] What happens if lengths don't match data?
- [ ] What are the minimum/maximum sizes?

**Create**: `tests/fuzz/UPDATE_STRUCTURE.md` with findings

---

## Task 2.2: Create UPDATE Test Helpers

**File**: `/home/user/exabgp/tests/helpers.py`

**What to do**:
Add UPDATE-specific helpers (if not already present from Task 0.5):

```python
def create_ipv4_prefix(prefix_str):
    """Create wire-format IPv4 prefix.

    Args:
        prefix_str: Prefix like "192.0.2.0/24"

    Returns:
        bytes: Wire format (length byte + address bytes)
    """
    ip, prefix_len = prefix_str.split('/')
    prefix_len = int(prefix_len)

    # Calculate how many bytes needed
    bytes_needed = (prefix_len + 7) // 8

    # Convert IP to bytes
    ip_parts = [int(p) for p in ip.split('.')]
    ip_bytes = bytes(ip_parts[:bytes_needed])

    return bytes([prefix_len]) + ip_bytes


def create_path_attribute(type_code, value, optional=False, transitive=True, partial=False, extended=False):
    """Create a BGP path attribute.

    Args:
        type_code: Attribute type code (1-255)
        value: Attribute value (bytes)
        optional: Optional flag
        transitive: Transitive flag
        partial: Partial flag
        extended: Extended length flag

    Returns:
        bytes: Wire format attribute
    """
    # Flags byte
    flags = 0
    if optional:
        flags |= 0x80
    if transitive:
        flags |= 0x40
    if partial:
        flags |= 0x20
    if extended:
        flags |= 0x10

    # Determine length encoding
    length = len(value)
    if extended or length > 255:
        # Extended length (2 bytes)
        flags |= 0x10
        attr = bytes([flags, type_code])
        attr += length.to_bytes(2, 'big')
        attr += value
    else:
        # Standard length (1 byte)
        attr = bytes([flags, type_code, length])
        attr += value

    return attr


def create_origin_attribute(origin=0):
    """Create ORIGIN attribute.

    Args:
        origin: 0=IGP, 1=EGP, 2=INCOMPLETE

    Returns:
        bytes: ORIGIN attribute
    """
    return create_path_attribute(
        type_code=1,
        value=bytes([origin]),
        optional=False,
        transitive=True
    )


def create_as_path_attribute(as_sequence):
    """Create AS_PATH attribute.

    Args:
        as_sequence: List of AS numbers, e.g., [65001, 65002]

    Returns:
        bytes: AS_PATH attribute
    """
    # AS_SEQUENCE segment
    segment_type = 2
    segment_length = len(as_sequence)

    value = bytes([segment_type, segment_length])
    for asn in as_sequence:
        value += asn.to_bytes(2, 'big')

    return create_path_attribute(
        type_code=2,
        value=value,
        optional=False,
        transitive=True
    )


def create_next_hop_attribute(next_hop='192.0.2.1'):
    """Create NEXT_HOP attribute.

    Args:
        next_hop: IPv4 address as string

    Returns:
        bytes: NEXT_HOP attribute
    """
    octets = [int(o) for o in next_hop.split('.')]
    value = bytes(octets)

    return create_path_attribute(
        type_code=3,
        value=value,
        optional=False,
        transitive=True
    )
```

**Acceptance Criteria**:
- [ ] Helper functions added to tests/helpers.py
- [ ] Functions documented
- [ ] Functions tested manually
- [ ] File saved

---

## Task 2.3: Create Basic UPDATE Fuzzing Test

**File**: `/home/user/exabgp/tests/fuzz/fuzz_update_message.py`

**What to do**:

```python
"""Fuzzing tests for BGP UPDATE message parsing.

UPDATE Message Structure:
    - Withdrawn Routes Length: 2 bytes
    - Withdrawn Routes: Variable
    - Path Attributes Length: 2 bytes
    - Path Attributes: Variable
    - NLRI: Variable
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import struct
import sys
sys.path.insert(0, 'tests')
from helpers import create_update_message

pytestmark = pytest.mark.fuzz


def parse_update_message(data):
    """Helper to parse UPDATE message.

    Args:
        data: Raw UPDATE message body (without header)

    Returns:
        Parsed UPDATE or raises exception
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.direction import Direction
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

    # TODO: Adjust based on actual API
    direction = Direction.IN
    negotiated = Negotiated(None)

    return Update.unpack_message(data, direction, negotiated)


@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=4096))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=1000)
def test_update_random_data(data):
    """Fuzz UPDATE parser with completely random data."""
    from exabgp.bgp.message import Notify

    try:
        result = parse_update_message(data)
    except (Notify, ValueError, KeyError, IndexError, struct.error, TypeError):
        # Expected exceptions
        pass
    except Exception as e:
        pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "fuzz"])
```

**Acceptance Criteria**:
- [ ] File created
- [ ] Basic fuzzing test present
- [ ] Helper function for parsing
- [ ] File saved

---

## Task 2.4: Add Length Field Fuzzing

**File**: `/home/user/exabgp/tests/fuzz/fuzz_update_message.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(
    withdrawn_len=st.integers(min_value=0, max_value=4096),
    attr_len=st.integers(min_value=0, max_value=4096),
)
@settings(max_examples=500)
def test_update_length_fields(withdrawn_len, attr_len):
    """Fuzz UPDATE with various length field values.

    Tests all combinations of withdrawn and attribute lengths.
    """
    from exabgp.bgp.message import Notify

    # Build UPDATE with specified lengths
    data = withdrawn_len.to_bytes(2, 'big')
    data += b'\x00' * min(withdrawn_len, 100)  # Limit actual data to avoid huge messages
    data += attr_len.to_bytes(2, 'big')
    data += b'\x00' * min(attr_len, 100)

    try:
        result = parse_update_message(data)
    except (Notify, ValueError, KeyError, IndexError, struct.error):
        # Expected for mismatched lengths
        pass


@pytest.mark.fuzz
@given(withdrawn_len=st.integers(min_value=0, max_value=65535))
def test_withdrawn_length_field(withdrawn_len):
    """Fuzz withdrawn routes length field with all possible values."""
    from exabgp.bgp.message import Notify

    data = withdrawn_len.to_bytes(2, 'big')
    # Add actual withdrawn data if length is reasonable
    if withdrawn_len <= 100:
        data += b'\x00' * withdrawn_len
    data += b'\x00\x00'  # Zero attributes length

    try:
        result = parse_update_message(data)
    except (Notify, ValueError, IndexError, struct.error):
        pass


@pytest.mark.fuzz
@given(attr_len=st.integers(min_value=0, max_value=65535))
def test_attribute_length_field(attr_len):
    """Fuzz path attributes length field with all possible values."""
    from exabgp.bgp.message import Notify

    data = b'\x00\x00'  # Zero withdrawn length
    data += attr_len.to_bytes(2, 'big')
    # Add actual attribute data if length is reasonable
    if attr_len <= 100:
        data += b'\x00' * attr_len

    try:
        result = parse_update_message(data)
    except (Notify, ValueError, IndexError, struct.error):
        pass
```

**Acceptance Criteria**:
- [ ] Length field tests added
- [ ] Tests cover withdrawn and attribute lengths
- [ ] Tests handle large values gracefully
- [ ] File saved

---

## Task 2.5: Add Truncation Tests

**File**: `/home/user/exabgp/tests/fuzz/fuzz_update_message.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(
    withdrawn_len=st.integers(min_value=1, max_value=100),
    actual_data=st.integers(min_value=0, max_value=99),
)
def test_withdrawn_truncation(withdrawn_len, actual_data):
    """Test UPDATE with truncated withdrawn routes section.

    Length field says N bytes, but only M < N bytes provided.
    """
    from exabgp.bgp.message import Notify

    data = withdrawn_len.to_bytes(2, 'big')
    data += b'\x00' * actual_data  # Less than withdrawn_len
    data += b'\x00\x00'  # Attr length

    if actual_data < withdrawn_len:
        # Should detect truncation
        with pytest.raises((Notify, ValueError, IndexError)):
            parse_update_message(data)
    else:
        # Might parse or fail for other reasons
        try:
            parse_update_message(data)
        except (Notify, ValueError, IndexError, struct.error):
            pass


@pytest.mark.fuzz
@given(
    attr_len=st.integers(min_value=1, max_value=100),
    actual_data=st.integers(min_value=0, max_value=99),
)
def test_attribute_truncation(attr_len, actual_data):
    """Test UPDATE with truncated attributes section."""
    from exabgp.bgp.message import Notify

    data = b'\x00\x00'  # Zero withdrawn
    data += attr_len.to_bytes(2, 'big')
    data += b'\x00' * actual_data  # Less than attr_len

    if actual_data < attr_len:
        # Should detect truncation
        with pytest.raises((Notify, ValueError, IndexError)):
            parse_update_message(data)
    else:
        try:
            parse_update_message(data)
        except (Notify, ValueError, IndexError, struct.error):
            pass
```

**Acceptance Criteria**:
- [ ] Truncation tests added
- [ ] Tests cover both sections
- [ ] Tests verify error detection
- [ ] File saved

---

## Task 2.6: Add Valid UPDATE Tests

**File**: `/home/user/exabgp/tests/fuzz/fuzz_update_message.py`

**What to do**:

```python
@pytest.mark.fuzz
def test_minimal_valid_update():
    """Test minimal valid UPDATE (no routes, no attributes)."""
    data = b'\x00\x00'  # Withdrawn length = 0
    data += b'\x00\x00'  # Attribute length = 0
    # No NLRI

    result = parse_update_message(data)
    # Should parse successfully (withdraw-all message)
    assert result is not None


@pytest.mark.fuzz
def test_update_with_single_route():
    """Test UPDATE announcing a single route."""
    from helpers import (
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
        create_ipv4_prefix,
    )

    # No withdrawn routes
    data = b'\x00\x00'

    # Path attributes
    attrs = b''
    attrs += create_origin_attribute(origin=0)  # IGP
    attrs += create_as_path_attribute([65001, 65002])
    attrs += create_next_hop_attribute('192.0.2.1')

    data += len(attrs).to_bytes(2, 'big')
    data += attrs

    # NLRI: Single prefix 192.0.2.0/24
    data += create_ipv4_prefix('192.0.2.0/24')

    result = parse_update_message(data)
    assert result is not None


@pytest.mark.fuzz
def test_update_withdraw_single_route():
    """Test UPDATE withdrawing a single route."""
    from helpers import create_ipv4_prefix

    # Withdrawn routes
    withdrawn = create_ipv4_prefix('192.0.2.0/24')
    data = len(withdrawn).to_bytes(2, 'big')
    data += withdrawn

    # No attributes or NLRI
    data += b'\x00\x00'

    result = parse_update_message(data)
    assert result is not None


@pytest.mark.fuzz
@given(
    prefix_count=st.integers(min_value=1, max_value=10),
    as_path_length=st.integers(min_value=1, max_value=5),
)
def test_update_multiple_routes(prefix_count, as_path_length):
    """Test UPDATE with multiple announced routes."""
    from helpers import (
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
        create_ipv4_prefix,
    )

    # No withdrawn
    data = b'\x00\x00'

    # Attributes
    attrs = b''
    attrs += create_origin_attribute(0)

    # Random AS path
    as_path = [65000 + i for i in range(as_path_length)]
    attrs += create_as_path_attribute(as_path)
    attrs += create_next_hop_attribute('192.0.2.1')

    data += len(attrs).to_bytes(2, 'big')
    data += attrs

    # Multiple prefixes
    for i in range(prefix_count):
        prefix = f'192.0.{i}.0/24'
        data += create_ipv4_prefix(prefix)

    try:
        result = parse_update_message(data)
        assert result is not None
    except (Notify, ValueError) as e:
        # Might fail for other validation reasons
        pass
```

**Acceptance Criteria**:
- [ ] Valid UPDATE tests added
- [ ] Tests cover common scenarios
- [ ] Tests use helper functions
- [ ] File saved

---

## Task 2.7: Add Attribute Fuzzing

**File**: `/home/user/exabgp/tests/fuzz/fuzz_update_message.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(
    attr_flags=st.integers(min_value=0, max_value=255),
    attr_type=st.integers(min_value=0, max_value=255),
    attr_length=st.integers(min_value=0, max_value=255),
)
def test_malformed_attribute_header(attr_flags, attr_type, attr_length):
    """Fuzz attribute header fields."""
    from exabgp.bgp.message import Notify

    # No withdrawn
    data = b'\x00\x00'

    # Malformed attribute
    attr = bytes([attr_flags, attr_type, attr_length])
    attr += b'\x00' * min(attr_length, 50)  # Attribute data

    data += len(attr).to_bytes(2, 'big')
    data += attr

    try:
        result = parse_update_message(data)
    except (Notify, ValueError, KeyError, IndexError):
        pass


@pytest.mark.fuzz
@given(attr_data=st.binary(min_size=0, max_size=255))
def test_attribute_with_random_value(attr_data):
    """Test well-formed attribute with random value."""
    from exabgp.bgp.message import Notify

    data = b'\x00\x00'  # No withdrawn

    # ORIGIN attribute with random value
    attr = bytes([0x40, 0x01, len(attr_data)])  # Well-known, type=ORIGIN
    attr += attr_data

    data += len(attr).to_bytes(2, 'big')
    data += attr

    try:
        result = parse_update_message(data)
    except (Notify, ValueError, KeyError):
        # Expected for invalid ORIGIN values
        pass
```

**Acceptance Criteria**:
- [ ] Attribute fuzzing tests added
- [ ] Tests cover headers and values
- [ ] Tests handle exceptions properly
- [ ] File saved

---

## Task 2.8: Add NLRI Fuzzing

**File**: `/home/user/exabgp/tests/fuzz/fuzz_update_message.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(
    prefix_len=st.integers(min_value=0, max_value=255),
    data_len=st.integers(min_value=0, max_value=32),
)
def test_nlri_prefix_fuzzing(prefix_len, data_len):
    """Fuzz NLRI prefix length and data."""
    from exabgp.bgp.message import Notify
    from helpers import (
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    # Minimal valid attributes
    data = b'\x00\x00'  # No withdrawn
    attrs = b''
    attrs += create_origin_attribute(0)
    attrs += create_as_path_attribute([65001])
    attrs += create_next_hop_attribute('192.0.2.1')

    data += len(attrs).to_bytes(2, 'big')
    data += attrs

    # Malformed NLRI
    data += bytes([prefix_len])  # Prefix length
    data += b'\x00' * data_len    # Prefix bytes

    # Calculate expected bytes
    expected_bytes = (prefix_len + 7) // 8 if prefix_len <= 32 else 999

    try:
        result = parse_update_message(data)
        if expected_bytes != data_len:
            # Should have caught mismatch
            pytest.fail("Should have detected length mismatch")
    except (Notify, ValueError, IndexError):
        # Expected for mismatches
        pass


@pytest.mark.fuzz
@given(nlri_data=st.binary(min_size=0, max_size=100))
def test_nlri_random_data(nlri_data):
    """Test NLRI section with random data."""
    from exabgp.bgp.message import Notify
    from helpers import (
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    data = b'\x00\x00'  # No withdrawn

    attrs = b''
    attrs += create_origin_attribute(0)
    attrs += create_as_path_attribute([65001])
    attrs += create_next_hop_attribute('192.0.2.1')

    data += len(attrs).to_bytes(2, 'big')
    data += attrs
    data += nlri_data  # Random NLRI

    try:
        result = parse_update_message(data)
    except (Notify, ValueError, IndexError, struct.error):
        pass
```

**Acceptance Criteria**:
- [ ] NLRI fuzzing tests added
- [ ] Tests cover prefix length mismatches
- [ ] Tests use random data
- [ ] File saved

---

## Task 2.9: Run and Measure Coverage

**What to do**:
```bash
cd /home/user/exabgp
env PYTHONPATH=src pytest tests/fuzz/fuzz_update_message.py \
    --cov=exabgp.bgp.message.update \
    --cov-report=term \
    --cov-report=html \
    -v -m fuzz
```

**Analyze**:
1. Check coverage of `update/__init__.py`
2. Identify uncovered lines
3. Document findings

**Acceptance Criteria**:
- [ ] Coverage measured
- [ ] Report generated
- [ ] Uncovered lines documented
- [ ] Target: >85% coverage of unpack_message()

---

## Task 2.10: Add Edge Cases

**What to do**:
Based on coverage analysis, add tests for edge cases:

```python
@pytest.mark.fuzz
def test_update_maximum_withdrawn_routes():
    """Test UPDATE with maximum withdrawn routes."""
    # Implementation based on findings
    pass


@pytest.mark.fuzz
def test_update_maximum_attributes():
    """Test UPDATE with maximum attributes."""
    # Implementation based on findings
    pass


@pytest.mark.fuzz
def test_update_all_attribute_types():
    """Test UPDATE with all known attribute types."""
    # Implementation based on findings
    pass
```

**Acceptance Criteria**:
- [ ] Edge case tests added
- [ ] Coverage improved
- [ ] File saved

---

## Task 2.11: Run Extensive Fuzzing

**What to do**:
```bash
env PYTHONPATH=src HYPOTHESIS_PROFILE=extensive \
    pytest tests/fuzz/fuzz_update_message.py -v --tb=short
```

**Monitor and document**:
- Failures
- Performance
- Memory usage

**Acceptance Criteria**:
- [ ] Extensive fuzzing completed
- [ ] Results documented
- [ ] No unexpected crashes

---

## Task 2.12: Document and Commit

**What to do**:
Add module documentation and commit:

```bash
git add tests/fuzz/fuzz_update_message.py tests/helpers.py
git commit -m "Add comprehensive fuzzing tests for UPDATE message parser

- Test length field validation (withdrawn, attributes)
- Test truncation detection
- Test valid UPDATE messages (announce, withdraw)
- Test malformed attributes
- Test NLRI fuzzing
- Achieve 85%+ coverage of update/__init__.py::unpack_message()

Test coverage:
- Random data fuzzing
- Length field combinations
- Truncation scenarios
- Valid message construction
- Attribute fuzzing
- NLRI prefix fuzzing"
```

**Acceptance Criteria**:
- [ ] Documentation complete
- [ ] Changes committed
- [ ] Statistics included

---

## Completion Checklist

- [ ] Task 2.1: UPDATE structure analyzed
- [ ] Task 2.2: Test helpers created
- [ ] Task 2.3: Basic fuzzing test created
- [ ] Task 2.4: Length field fuzzing added
- [ ] Task 2.5: Truncation tests added
- [ ] Task 2.6: Valid UPDATE tests added
- [ ] Task 2.7: Attribute fuzzing added
- [ ] Task 2.8: NLRI fuzzing added
- [ ] Task 2.9: Coverage measured
- [ ] Task 2.10: Edge cases added
- [ ] Task 2.11: Extensive fuzzing completed
- [ ] Task 2.12: Documented and committed

**Estimated Total Time**: 6-8 hours
**Next File**: `03-FUZZ-ATTRIBUTES.md`
