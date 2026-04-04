# Phase 3: Fuzz BGP Path Attributes Parser

**Estimated Time**: 6-8 hours
**Priority**: CRITICAL
**Depends On**: 02-FUZZ-UPDATE-MESSAGE.md

**Target**: `src/exabgp/bgp/message/update/attribute/attributes.py::unpack()`

---

## Background

Path attributes are the heart of BGP routing policy. Each UPDATE can have multiple attributes, each with:
- **Flags** (1 byte): Optional, Transitive, Partial, Extended Length
- **Type Code** (1 byte): Identifies attribute type (1-255)
- **Length** (1 or 2 bytes): Attribute value length
- **Value** (variable): Attribute-specific data

Known attribute types include:
1. ORIGIN
2. AS_PATH
3. NEXT_HOP
4. MULTI_EXIT_DISC
5. LOCAL_PREF
6. ATOMIC_AGGREGATE
7. AGGREGATOR
8. COMMUNITY
16. EXTENDED_COMMUNITIES
... and many more

---

## Task 3.1: Analyze Attributes Parser

**File**: `/home/user/exabgp/src/exabgp/bgp/message/update/attribute/attributes.py`

**What to do**:
1. Locate the `unpack()` method
2. Understand the parsing loop:
   - How flags are parsed
   - How type code is read
   - How length is determined (standard vs extended)
   - How each attribute type is dispatched
3. Identify validation logic
4. List all supported attribute types

**Questions to answer**:
- [ ] How does it loop through attributes?
- [ ] What happens with unknown attributes?
- [ ] How is extended length handled?
- [ ] What validations are performed on flags?
- [ ] Which attributes are mandatory?

**Create**: `tests/fuzz/ATTRIBUTES_STRUCTURE.md` with findings

---

## Task 3.2: List All Attribute Types

**File**: `/home/user/exabgp/tests/fuzz/ATTRIBUTES_STRUCTURE.md`

**What to do**:
```bash
cd /home/user/exabgp/src/exabgp/bgp/message/update/attribute
grep -r "class.*Attribute" . | grep -v ".pyc"
```

Create a comprehensive list:
```markdown
# BGP Path Attribute Types

## Well-Known Mandatory
1. ORIGIN (type=1)
2. AS_PATH (type=2)
3. NEXT_HOP (type=3)

## Well-Known Discretionary
4. MULTI_EXIT_DISC (type=4)
5. LOCAL_PREF (type=5)
6. ATOMIC_AGGREGATE (type=6)
7. AGGREGATOR (type=7)

## Optional Transitive
8. COMMUNITY (type=8)
14. MP_REACH_NLRI (type=14)
15. MP_UNREACH_NLRI (type=15)
16. EXTENDED_COMMUNITIES (type=16)
...

## Total Supported: [count]
```

**Acceptance Criteria**:
- [ ] All attribute types listed
- [ ] Type codes documented
- [ ] Categories identified
- [ ] File saved

---

## Task 3.3: Create Attribute Helpers

**File**: `/home/user/exabgp/tests/unit/helpers.py`

**What to do**:
Add comprehensive attribute helpers:

```python
def create_multi_exit_disc_attribute(med=100):
    """Create MULTI_EXIT_DISC attribute."""
    value = med.to_bytes(4, 'big')
    return create_path_attribute(
        type_code=4,
        value=value,
        optional=True,
        transitive=False
    )


def create_local_pref_attribute(local_pref=100):
    """Create LOCAL_PREF attribute."""
    value = local_pref.to_bytes(4, 'big')
    return create_path_attribute(
        type_code=5,
        value=value,
        optional=False,
        transitive=False
    )


def create_atomic_aggregate_attribute():
    """Create ATOMIC_AGGREGATE attribute (no value)."""
    return create_path_attribute(
        type_code=6,
        value=b'',
        optional=False,
        transitive=True
    )


def create_aggregator_attribute(asn=65001, aggregator='192.0.2.1'):
    """Create AGGREGATOR attribute."""
    value = asn.to_bytes(2, 'big')
    octets = [int(o) for o in aggregator.split('.')]
    value += bytes(octets)

    return create_path_attribute(
        type_code=7,
        value=value,
        optional=True,
        transitive=True
    )


def create_community_attribute(communities):
    """Create COMMUNITY attribute.

    Args:
        communities: List of (asn, value) tuples

    Returns:
        bytes: COMMUNITY attribute
    """
    value = b''
    for asn, val in communities:
        value += asn.to_bytes(2, 'big')
        value += val.to_bytes(2, 'big')

    return create_path_attribute(
        type_code=8,
        value=value,
        optional=True,
        transitive=True
    )


def create_extended_community_attribute(communities):
    """Create EXTENDED_COMMUNITIES attribute.

    Args:
        communities: List of 8-byte extended communities

    Returns:
        bytes: EXTENDED_COMMUNITIES attribute
    """
    value = b''.join(communities)

    return create_path_attribute(
        type_code=16,
        value=value,
        optional=True,
        transitive=True
    )


def create_unknown_attribute(type_code, value=b'\x00', optional=True):
    """Create unknown/unrecognized attribute."""
    return create_path_attribute(
        type_code=type_code,
        value=value,
        optional=optional,
        transitive=True
    )
```

**Acceptance Criteria**:
- [ ] Helpers for common attributes added
- [ ] Helpers documented
- [ ] File saved

---

## Task 3.4: Create Basic Attribute Fuzzing Test

**File**: `/home/user/exabgp/tests/fuzz/fuzz_attributes.py`

**What to do**:

```python
"""Fuzzing tests for BGP path attributes parsing.

Path Attribute Structure:
    - Flags (1 byte): Optional, Transitive, Partial, Extended
    - Type Code (1 byte): Attribute type
    - Length (1 or 2 bytes): Standard or extended
    - Value (variable): Attribute-specific data
"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import struct
import sys
sys.path.insert(0, 'tests')

pytestmark = pytest.mark.fuzz


def parse_attributes(data):
    """Helper to parse path attributes.

    Args:
        data: Raw attributes data

    Returns:
        Parsed attributes or raises exception
    """
    from exabgp.bgp.message.update.attribute.attributes import Attributes
    from exabgp.bgp.message.direction import Direction
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

    direction = Direction.IN
    negotiated = Negotiated(None)

    return Attributes.unpack(data, direction, negotiated)


@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=4096))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=1000)
def test_attributes_random_data(data):
    """Fuzz attributes parser with completely random data."""
    from exabgp.bgp.message import Notify

    try:
        result = parse_attributes(data)
    except (Notify, ValueError, KeyError, IndexError, struct.error, TypeError):
        pass
    except Exception as e:
        pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "fuzz"])
```

**Acceptance Criteria**:
- [ ] File created
- [ ] Basic fuzzing test present
- [ ] Parse helper implemented
- [ ] File saved

---

## Task 3.5: Fuzz Attribute Flags

**File**: `/home/user/exabgp/tests/fuzz/fuzz_attributes.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(flags=st.integers(min_value=0, max_value=255))
def test_attribute_flags_fuzzing(flags):
    """Fuzz attribute flags byte with all possible values."""
    from exabgp.bgp.message import Notify

    # Create simple attribute with fuzzed flags
    type_code = 1  # ORIGIN
    value = b'\x00'  # IGP
    attr = bytes([flags, type_code, len(value)]) + value

    try:
        result = parse_attributes(attr)
    except (Notify, ValueError, KeyError):
        # May fail for invalid flag combinations
        pass


@pytest.mark.fuzz
@given(
    optional=st.booleans(),
    transitive=st.booleans(),
    partial=st.booleans(),
    extended=st.booleans(),
)
def test_flag_combinations(optional, transitive, partial, extended):
    """Test all combinations of attribute flags."""
    from exabgp.bgp.message import Notify

    flags = 0
    if optional:
        flags |= 0x80
    if transitive:
        flags |= 0x40
    if partial:
        flags |= 0x20
    if extended:
        flags |= 0x10

    type_code = 1  # ORIGIN
    value = b'\x00'

    if extended:
        attr = bytes([flags, type_code])
        attr += len(value).to_bytes(2, 'big')
        attr += value
    else:
        attr = bytes([flags, type_code, len(value)])
        attr += value

    try:
        result = parse_attributes(attr)
        # Some flag combinations may be invalid per RFC
    except (Notify, ValueError):
        pass


@pytest.mark.fuzz
def test_well_known_with_optional_flag():
    """Test well-known attribute marked as optional (should fail)."""
    from exabgp.bgp.message import Notify

    # ORIGIN is well-known mandatory, but set optional flag
    flags = 0x80 | 0x40  # Optional + Transitive
    attr = bytes([flags, 0x01, 0x01, 0x00])  # ORIGIN=IGP

    # Should be rejected
    with pytest.raises((Notify, ValueError)):
        parse_attributes(attr)
```

**Acceptance Criteria**:
- [ ] Flag fuzzing tests added
- [ ] All flag combinations tested
- [ ] Invalid combinations detected
- [ ] File saved

---

## Task 3.6: Fuzz Attribute Type Codes

**File**: `/home/user/exabgp/tests/fuzz/fuzz_attributes.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(type_code=st.integers(min_value=0, max_value=255))
def test_all_attribute_types(type_code):
    """Fuzz with all possible attribute type codes."""
    from exabgp.bgp.message import Notify

    # Well-formed attribute with any type code
    flags = 0xC0  # Optional + Transitive
    value = b'\x00\x01\x02\x03'  # Some data

    attr = bytes([flags, type_code, len(value)])
    attr += value

    try:
        result = parse_attributes(attr)
        # Unknown types should be handled gracefully
    except (Notify, ValueError, KeyError):
        pass


@pytest.mark.fuzz
def test_unknown_attribute_optional():
    """Test unknown attribute with optional flag (should pass)."""
    from exabgp.bgp.message import Notify

    # Type 255 (unassigned)
    flags = 0xC0  # Optional + Transitive
    attr = bytes([flags, 255, 4, 0x00, 0x01, 0x02, 0x03])

    try:
        result = parse_attributes(attr)
        # Should handle unknown optional attributes
    except (Notify, ValueError):
        # Or may choose to reject
        pass


@pytest.mark.fuzz
def test_unknown_attribute_well_known():
    """Test unknown attribute marked well-known (should fail)."""
    from exabgp.bgp.message import Notify

    # Type 255 but marked as well-known (no optional flag)
    flags = 0x40  # Transitive only
    attr = bytes([flags, 255, 4, 0x00, 0x01, 0x02, 0x03])

    # Should reject unknown well-known attribute
    with pytest.raises((Notify, ValueError)):
        parse_attributes(attr)
```

**Acceptance Criteria**:
- [ ] Type code fuzzing added
- [ ] Unknown types tested
- [ ] Optional vs well-known handling tested
- [ ] File saved

---

## Task 3.7: Fuzz Attribute Lengths

**File**: `/home/user/exabgp/tests/fuzz/fuzz_attributes.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(length=st.integers(min_value=0, max_value=255))
def test_standard_length_field(length):
    """Fuzz standard length field (1 byte)."""
    from exabgp.bgp.message import Notify

    flags = 0xC0  # Optional + Transitive (no extended flag)
    type_code = 100  # Optional attribute

    attr = bytes([flags, type_code, length])
    attr += b'\x00' * min(length, 50)  # Provide some data

    try:
        result = parse_attributes(attr)
    except (Notify, ValueError, IndexError):
        pass


@pytest.mark.fuzz
@given(length=st.integers(min_value=0, max_value=65535))
def test_extended_length_field(length):
    """Fuzz extended length field (2 bytes)."""
    from exabgp.bgp.message import Notify

    flags = 0xD0  # Optional + Transitive + Extended
    type_code = 100

    attr = bytes([flags, type_code])
    attr += length.to_bytes(2, 'big')
    attr += b'\x00' * min(length, 100)  # Limit actual data

    try:
        result = parse_attributes(attr)
    except (Notify, ValueError, IndexError, MemoryError):
        pass


@pytest.mark.fuzz
@given(
    declared_length=st.integers(min_value=0, max_value=100),
    actual_length=st.integers(min_value=0, max_value=100),
)
def test_length_mismatch(declared_length, actual_length):
    """Test when declared length doesn't match actual data."""
    from exabgp.bgp.message import Notify

    flags = 0xC0
    type_code = 100

    attr = bytes([flags, type_code, declared_length])
    attr += b'\x00' * actual_length

    if declared_length != actual_length:
        # Should detect mismatch
        try:
            result = parse_attributes(attr)
            # If it parsed, might be parsing multiple attributes
        except (Notify, ValueError, IndexError):
            # Expected
            pass
    else:
        try:
            result = parse_attributes(attr)
        except (Notify, ValueError):
            pass
```

**Acceptance Criteria**:
- [ ] Length fuzzing added
- [ ] Standard and extended lengths tested
- [ ] Length mismatches tested
- [ ] File saved

---

## Task 3.8: Test Multiple Attributes

**File**: `/home/user/exabgp/tests/fuzz/fuzz_attributes.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(attr_count=st.integers(min_value=1, max_value=20))
def test_multiple_attributes(attr_count):
    """Test parsing multiple attributes in sequence."""
    from exabgp.bgp.message import Notify
    from helpers import (
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
        create_multi_exit_disc_attribute,
    )

    attrs = b''
    for i in range(min(attr_count, 4)):
        if i == 0:
            attrs += create_origin_attribute(0)
        elif i == 1:
            attrs += create_as_path_attribute([65001])
        elif i == 2:
            attrs += create_next_hop_attribute('192.0.2.1')
        elif i == 3:
            attrs += create_multi_exit_disc_attribute(100)

    try:
        result = parse_attributes(attrs)
    except (Notify, ValueError):
        pass


@pytest.mark.fuzz
def test_duplicate_attributes():
    """Test duplicate attributes (should be rejected)."""
    from exabgp.bgp.message import Notify
    from helpers import create_origin_attribute

    # Two ORIGIN attributes
    attrs = create_origin_attribute(0)
    attrs += create_origin_attribute(1)

    # Should reject duplicates
    with pytest.raises((Notify, ValueError)):
        parse_attributes(attrs)


@pytest.mark.fuzz
def test_missing_mandatory_attributes():
    """Test missing mandatory attributes."""
    from exabgp.bgp.message import Notify
    from helpers import create_origin_attribute

    # Only ORIGIN, missing AS_PATH and NEXT_HOP
    attrs = create_origin_attribute(0)

    # Might be detected here or later in UPDATE processing
    try:
        result = parse_attributes(attrs)
        # May parse but fail validation later
    except (Notify, ValueError, KeyError):
        pass
```

**Acceptance Criteria**:
- [ ] Multiple attribute tests added
- [ ] Duplicate detection tested
- [ ] Mandatory attribute tests added
- [ ] File saved

---

## Task 3.9: Test Specific Attribute Values

**File**: `/home/user/exabgp/tests/fuzz/fuzz_attributes.py`

**What to do**:

```python
@pytest.mark.fuzz
@given(origin=st.integers(min_value=0, max_value=255))
def test_origin_values(origin):
    """Test ORIGIN attribute with all possible values.

    Valid values: 0=IGP, 1=EGP, 2=INCOMPLETE
    """
    from exabgp.bgp.message import Notify

    flags = 0x40  # Well-known, Transitive
    attr = bytes([flags, 0x01, 0x01, origin])

    if origin in (0, 1, 2):
        # Valid ORIGIN value
        try:
            result = parse_attributes(attr)
        except (Notify, ValueError):
            # May fail for other reasons
            pass
    else:
        # Invalid ORIGIN value - should be rejected
        with pytest.raises((Notify, ValueError)):
            parse_attributes(attr)


@pytest.mark.fuzz
@given(as_path_data=st.binary(min_size=0, max_size=255))
def test_as_path_malformed(as_path_data):
    """Test AS_PATH with random data."""
    from exabgp.bgp.message import Notify

    flags = 0x40  # Well-known, Transitive
    attr = bytes([flags, 0x02, len(as_path_data)])
    attr += as_path_data

    try:
        result = parse_attributes(attr)
    except (Notify, ValueError, IndexError, struct.error):
        # Expected for malformed AS_PATH
        pass


@pytest.mark.fuzz
@given(next_hop=st.binary(min_size=0, max_size=16))
def test_next_hop_lengths(next_hop):
    """Test NEXT_HOP with various lengths.

    Valid: 4 bytes for IPv4
    """
    from exabgp.bgp.message import Notify

    flags = 0x40  # Well-known, Transitive
    attr = bytes([flags, 0x03, len(next_hop)])
    attr += next_hop

    if len(next_hop) == 4:
        # Valid IPv4 next hop
        try:
            result = parse_attributes(attr)
        except (Notify, ValueError):
            pass
    else:
        # Invalid length - should reject
        with pytest.raises((Notify, ValueError)):
            parse_attributes(attr)
```

**Acceptance Criteria**:
- [ ] Attribute value fuzzing added
- [ ] ORIGIN, AS_PATH, NEXT_HOP tested
- [ ] Invalid values detected
- [ ] File saved

---

## Task 3.10: Run and Measure Coverage

**What to do**:
```bash
cd /home/user/exabgp
env PYTHONPATH=src pytest tests/fuzz/fuzz_attributes.py \
    --cov=exabgp.bgp.message.update.attribute \
    --cov-report=term \
    --cov-report=html \
    -v -m fuzz
```

**Acceptance Criteria**:
- [ ] Coverage measured
- [ ] Report generated
- [ ] Target: >85% of attributes.py::unpack()

---

## Task 3.11: Add Edge Cases and Coverage Improvements

**What to do**:
Based on coverage analysis, add tests for uncovered paths.

**Acceptance Criteria**:
- [ ] Uncovered lines identified
- [ ] Tests added
- [ ] Coverage target met

---

## Task 3.12: Run Extensive Fuzzing

**What to do**:
```bash
env PYTHONPATH=src HYPOTHESIS_PROFILE=extensive \
    pytest tests/fuzz/fuzz_attributes.py -v --tb=short
```

**Acceptance Criteria**:
- [ ] Extensive fuzzing completed
- [ ] Results documented
- [ ] No unexpected crashes

---

## Task 3.13: Document and Commit

**What to do**:
```bash
git add tests/fuzz/fuzz_attributes.py tests/fuzz/ATTRIBUTES_STRUCTURE.md tests/unit/helpers.py
git commit -m "Add comprehensive fuzzing tests for BGP path attributes parser

- Test all attribute flag combinations
- Test all attribute type codes (0-255)
- Test standard and extended length fields
- Test length mismatches and truncation
- Test specific attribute values (ORIGIN, AS_PATH, NEXT_HOP)
- Test multiple attributes and duplicates
- Achieve 85%+ coverage of attributes.py::unpack()

Coverage:
- Attribute flags: All 256 combinations
- Type codes: All 256 values
- Length fields: Standard (1-byte) and extended (2-byte)
- Multiple attributes in sequence
- Duplicate detection
- Mandatory attribute validation"
```

**Acceptance Criteria**:
- [ ] Changes committed
- [ ] Documentation complete

---

## Completion Checklist

- [ ] Task 3.1: Attributes parser analyzed
- [ ] Task 3.2: All attribute types listed
- [ ] Task 3.3: Attribute helpers created
- [ ] Task 3.4: Basic fuzzing test created
- [ ] Task 3.5: Flag fuzzing added
- [ ] Task 3.6: Type code fuzzing added
- [ ] Task 3.7: Length fuzzing added
- [ ] Task 3.8: Multiple attributes tested
- [ ] Task 3.9: Specific values tested
- [ ] Task 3.10: Coverage measured
- [ ] Task 3.11: Edge cases added
- [ ] Task 3.12: Extensive fuzzing completed
- [ ] Task 3.13: Documented and committed

**Estimated Total Time**: 6-8 hours
**Next File**: `04-FUZZ-OPEN-MESSAGE.md`
