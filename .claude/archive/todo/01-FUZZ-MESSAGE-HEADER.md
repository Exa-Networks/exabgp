# Phase 1: Fuzz BGP Message Header Parser

**Estimated Time**: 3-4 hours
**Priority**: CRITICAL
**Depends On**: 00-SETUP-FOUNDATION.md

**Target**: `src/exabgp/reactor/network/connection.py::reader()`

---

## Background

The BGP message header is the first line of defense against malformed messages. It consists of:
- **Marker**: 16 bytes of 0xFF
- **Length**: 2-byte message length (19-4096)
- **Type**: 1-byte message type (1-5)

This parser MUST be bulletproof as it processes every incoming message.

---

## Task 1.1: Read and Understand Current Implementation

**File**: `/home/user/exabgp/src/exabgp/reactor/network/connection.py`

**What to do**:
1. Open the file and locate the `reader()` method
2. Understand the logic:
   - How it validates the marker
   - How it reads length and type
   - What exceptions it raises
   - How it handles errors

**Questions to answer**:
- [ ] What line validates the marker?
- [ ] What happens if marker is invalid?
- [ ] What are min/max valid lengths?
- [ ] What are valid message types?
- [ ] What exception types are raised?

**Notes**:
Record findings in comments or separate notes file.

---

## Task 1.2: Create Basic Fuzzing Test

**File**: `/home/user/exabgp/tests/fuzz/fuzz_message_header.py`

**What to do**:
Create the initial fuzzing test file:

```python
"""Fuzzing tests for BGP message header parsing."""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import struct

# Mark all tests in this module as fuzz tests
pytestmark = pytest.mark.fuzz


@given(data=st.binary(min_size=0, max_size=100))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_header_parsing_with_random_data(data):
    """Fuzz header parser with completely random binary data.

    The parser should handle any binary data gracefully without crashing.
    It should either parse successfully or raise expected exceptions.
    """
    from exabgp.reactor.network.connection import reader
    from exabgp.bgp.message import Notify

    # TODO: Determine how to properly invoke reader()
    # This is a placeholder - adjust based on actual API
    try:
        # reader is a generator, need to understand how to test it
        gen = reader(data)
        result = next(gen, None)
    except (Notify, ValueError, KeyError, IndexError, struct.error, StopIteration):
        # Expected exceptions for malformed data
        pass
    except Exception as e:
        pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # Run with: python -m pytest tests/fuzz/fuzz_message_header.py -v
    pytest.main([__file__, "-v", "-m", "fuzz"])
```

**Acceptance Criteria**:
- [ ] File created
- [ ] Basic fuzzing test skeleton present
- [ ] Marked with `pytest.mark.fuzz`
- [ ] File saved

---

## Task 1.3: Investigate Reader API

**What to do**:
1. Read `/home/user/exabgp/src/exabgp/reactor/network/connection.py` carefully
2. Understand how `reader()` is actually called
3. Determine:
   - Is it a generator or regular function?
   - What parameters does it take?
   - How does it consume data?
   - How is it used in production code?

4. Search for usage examples:
```bash
cd /home/user/exabgp
grep -r "def reader" src/
grep -r "\.reader(" src/
```

**Document findings**:
Create notes about the correct way to test `reader()`.

**Acceptance Criteria**:
- [ ] Understanding of reader() API documented
- [ ] Know how to properly invoke it in tests
- [ ] Identified what to mock/stub

---

## Task 1.4: Create Test Helper for Reader

**File**: `/home/user/exabgp/tests/fuzz/fuzz_message_header.py`

**What to do**:
Based on Task 1.3 findings, create a helper function:

```python
def parse_header_from_bytes(data):
    """Helper to parse BGP header from raw bytes.

    Args:
        data: Raw bytes to parse

    Returns:
        Parsed header or raises exception

    Raises:
        Notify: For BGP protocol errors
        ValueError: For invalid data
        struct.error: For unpacking errors
    """
    # TODO: Implement based on reader() API investigation
    # This might involve:
    # - Creating a mock connection object
    # - Setting up necessary state
    # - Calling reader() properly

    # Placeholder implementation:
    if len(data) < 19:
        raise ValueError("Message too short")

    marker = data[0:16]
    if marker != b'\xFF' * 16:
        raise Notify(1, 1, b'Invalid marker')

    length = struct.unpack('!H', data[16:18])[0]
    if length < 19 or length > 4096:
        raise Notify(1, 2, b'Invalid length')

    msg_type = data[18]
    if msg_type not in (1, 2, 3, 4, 5):
        raise Notify(1, 3, b'Invalid type')

    return marker, length, msg_type
```

**Acceptance Criteria**:
- [ ] Helper function created
- [ ] Properly invokes reader() or simulates it
- [ ] Returns structured data or raises exceptions
- [ ] Documented with docstring

---

## Task 1.5: Add Specific Fuzzing Tests

**File**: `/home/user/exabgp/tests/fuzz/fuzz_message_header.py`

**What to do**:
Add targeted fuzzing tests for specific scenarios:

```python
@pytest.mark.fuzz
@given(marker=st.binary(min_size=16, max_size=16))
def test_marker_validation(marker):
    """Fuzz marker validation with all possible 16-byte values.

    Only b'\\xFF' * 16 should be valid.
    """
    from exabgp.bgp.message import Notify

    length = struct.pack('!H', 19)  # Minimum valid length
    msg_type = b'\x01'  # OPEN message
    data = marker + length + msg_type

    if marker == b'\xFF' * 16:
        # Should parse successfully
        result = parse_header_from_bytes(data)
        assert result is not None
    else:
        # Should raise Notify
        with pytest.raises((Notify, ValueError)):
            parse_header_from_bytes(data)


@pytest.mark.fuzz
@given(length=st.integers(min_value=0, max_value=65535))
def test_length_validation(length):
    """Fuzz length field with all possible 16-bit values.

    Only 19-4096 should be valid BGP message lengths.
    """
    from exabgp.bgp.message import Notify

    marker = b'\xFF' * 16
    length_bytes = struct.pack('!H', length)
    msg_type = b'\x01'
    data = marker + length_bytes + msg_type

    if 19 <= length <= 4096:
        # Should parse successfully
        result = parse_header_from_bytes(data)
        assert result[1] == length
    else:
        # Should raise Notify or ValueError
        with pytest.raises((Notify, ValueError)):
            parse_header_from_bytes(data)


@pytest.mark.fuzz
@given(msg_type=st.integers(min_value=0, max_value=255))
def test_message_type_validation(msg_type):
    """Fuzz message type with all possible byte values.

    Only 1-5 are valid BGP message types.
    """
    from exabgp.bgp.message import Notify

    marker = b'\xFF' * 16
    length = struct.pack('!H', 19)
    data = marker + length + bytes([msg_type])

    if 1 <= msg_type <= 5:
        # Should parse successfully
        result = parse_header_from_bytes(data)
        assert result[2] == msg_type
    else:
        # Should raise Notify or ValueError
        with pytest.raises((Notify, ValueError)):
            parse_header_from_bytes(data)


@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=18))
def test_truncated_headers(data):
    """Test headers shorter than minimum (19 bytes)."""
    from exabgp.bgp.message import Notify

    # All truncated headers should be rejected
    with pytest.raises((Notify, ValueError, IndexError, struct.error)):
        parse_header_from_bytes(data)


@pytest.mark.fuzz
@given(
    marker_byte=st.integers(min_value=0, max_value=255),
    position=st.integers(min_value=0, max_value=15),
)
def test_marker_single_bit_flips(marker_byte, position):
    """Test marker with single byte corrupted at each position."""
    from exabgp.bgp.message import Notify

    marker = bytearray(b'\xFF' * 16)
    marker[position] = marker_byte

    length = struct.pack('!H', 19)
    msg_type = b'\x01'
    data = bytes(marker) + length + msg_type

    if marker_byte == 0xFF:
        # All 0xFF, should be valid
        result = parse_header_from_bytes(data)
        assert result is not None
    else:
        # Corrupted marker should be rejected
        with pytest.raises((Notify, ValueError)):
            parse_header_from_bytes(data)
```

**Acceptance Criteria**:
- [ ] At least 5 targeted fuzzing tests added
- [ ] Tests cover: marker, length, type, truncation, bit flips
- [ ] All tests properly decorated with `@pytest.mark.fuzz`
- [ ] Tests have descriptive docstrings
- [ ] File saved

---

## Task 1.6: Run and Debug Tests

**What to do**:
```bash
cd /home/user/exabgp
env PYTHONPATH=src pytest tests/fuzz/fuzz_message_header.py -v -m fuzz
```

**Expected issues**:
- Import errors
- API mismatches
- Incorrect exception types
- Missing dependencies

**Debug process**:
1. Fix import errors
2. Adjust parse_header_from_bytes() to match actual API
3. Update expected exception types
4. Iterate until all tests pass or fail as expected

**Acceptance Criteria**:
- [ ] Tests run without import errors
- [ ] Tests properly exercise the code
- [ ] All tests pass or have documented failures
- [ ] No unexpected crashes

---

## Task 1.7: Add Edge Case Tests

**File**: `/home/user/exabgp/tests/fuzz/fuzz_message_header.py`

**What to do**:
Add specific edge cases that are important:

```python
@pytest.mark.fuzz
def test_minimum_valid_header():
    """Test minimum valid BGP header (19 bytes, OPEN message)."""
    marker = b'\xFF' * 16
    length = struct.pack('!H', 19)
    msg_type = b'\x01'
    data = marker + length + msg_type

    result = parse_header_from_bytes(data)
    assert result is not None
    assert result[1] == 19
    assert result[2] == 1


@pytest.mark.fuzz
def test_maximum_valid_header():
    """Test maximum valid BGP header (4096 bytes)."""
    marker = b'\xFF' * 16
    length = struct.pack('!H', 4096)
    msg_type = b'\x02'  # UPDATE
    data = marker + length + msg_type

    result = parse_header_from_bytes(data)
    assert result is not None
    assert result[1] == 4096
    assert result[2] == 2


@pytest.mark.fuzz
def test_length_one_below_minimum():
    """Test length = 18 (one below minimum)."""
    from exabgp.bgp.message import Notify

    marker = b'\xFF' * 16
    length = struct.pack('!H', 18)
    msg_type = b'\x01'
    data = marker + length + msg_type

    with pytest.raises((Notify, ValueError)):
        parse_header_from_bytes(data)


@pytest.mark.fuzz
def test_length_one_above_maximum():
    """Test length = 4097 (one above maximum)."""
    from exabgp.bgp.message import Notify

    marker = b'\xFF' * 16
    length = struct.pack('!H', 4097)
    msg_type = b'\x01'
    data = marker + length + msg_type

    with pytest.raises((Notify, ValueError)):
        parse_header_from_bytes(data)


@pytest.mark.fuzz
def test_empty_input():
    """Test completely empty input."""
    from exabgp.bgp.message import Notify

    with pytest.raises((Notify, ValueError, IndexError)):
        parse_header_from_bytes(b'')


@pytest.mark.fuzz
def test_all_zeros():
    """Test header with all zeros."""
    from exabgp.bgp.message import Notify

    data = b'\x00' * 19
    with pytest.raises((Notify, ValueError)):
        parse_header_from_bytes(data)


@pytest.mark.fuzz
def test_all_ones():
    """Test header with all ones (except length)."""
    from exabgp.bgp.message import Notify

    # Marker all FF - valid
    # Length would be 0xFFFF = 65535 - invalid (> 4096)
    # Type 0xFF - invalid
    data = b'\xFF' * 19

    with pytest.raises((Notify, ValueError)):
        parse_header_from_bytes(data)
```

**Acceptance Criteria**:
- [ ] At least 7 edge case tests added
- [ ] Cover boundary conditions
- [ ] Cover min/max valid values
- [ ] Cover empty/all-zeros/all-ones
- [ ] File saved

---

## Task 1.8: Add Example-Based Tests

**File**: `/home/user/exabgp/tests/fuzz/fuzz_message_header.py`

**What to do**:
Add examples from actual BGP messages:

```python
@pytest.mark.fuzz
class TestRealWorldHeaders:
    """Test with real-world BGP message headers."""

    def test_typical_open_message_header(self):
        """Test header from typical OPEN message."""
        # Marker (16 bytes of FF) + Length (0x001D = 29) + Type (1 = OPEN)
        data = bytes.fromhex('ffffffffffffffffffffffffffffffff001d01')

        result = parse_header_from_bytes(data)
        assert result[1] == 29
        assert result[2] == 1

    def test_typical_update_message_header(self):
        """Test header from typical UPDATE message."""
        # Marker + Length (0x0023 = 35) + Type (2 = UPDATE)
        data = bytes.fromhex('ffffffffffffffffffffffffffffffff002302')

        result = parse_header_from_bytes(data)
        assert result[1] == 35
        assert result[2] == 2

    def test_keepalive_message_header(self):
        """Test header from KEEPALIVE message (minimum size)."""
        # Marker + Length (0x0013 = 19) + Type (4 = KEEPALIVE)
        data = bytes.fromhex('ffffffffffffffffffffffffffffffff001304')

        result = parse_header_from_bytes(data)
        assert result[1] == 19
        assert result[2] == 4

    def test_notification_message_header(self):
        """Test header from NOTIFICATION message."""
        # Marker + Length (varies) + Type (3 = NOTIFICATION)
        data = bytes.fromhex('ffffffffffffffffffffffffffffffff001503')

        result = parse_header_from_bytes(data)
        assert result[1] == 21
        assert result[2] == 3
```

**Acceptance Criteria**:
- [ ] Real-world examples added
- [ ] Examples from different message types
- [ ] Hex values documented with comments
- [ ] File saved

---

## Task 1.9: Measure Coverage

**What to do**:
```bash
cd /home/user/exabgp
env PYTHONPATH=src pytest tests/fuzz/fuzz_message_header.py \
    --cov=exabgp.reactor.network.connection \
    --cov-report=term \
    --cov-report=html \
    -v
```

**Analyze coverage**:
1. Check terminal output for coverage percentage
2. Open `htmlcov/index.html` in browser
3. Navigate to `connection.py`
4. Identify uncovered lines in `reader()` function

**Document findings**:
- Current coverage: ____%
- Uncovered lines: ___
- Missing test cases: ___

**Acceptance Criteria**:
- [ ] Coverage measured
- [ ] Coverage report generated
- [ ] Uncovered lines identified
- [ ] Target: >90% coverage of reader() function

---

## Task 1.10: Add Tests for Uncovered Cases

**What to do**:
Based on Task 1.9 findings, add tests for uncovered code paths.

**Example**:
```python
@pytest.mark.fuzz
def test_uncovered_case_1():
    """Test specific uncovered branch identified in coverage."""
    # Add test based on coverage analysis
    pass
```

**Acceptance Criteria**:
- [ ] All significant uncovered branches have tests
- [ ] Re-run coverage to verify improvement
- [ ] Target: 95%+ coverage achieved

---

## Task 1.11: Run Extensive Fuzzing

**What to do**:
```bash
cd /home/user/exabgp
env PYTHONPATH=src HYPOTHESIS_PROFILE=extensive \
    pytest tests/fuzz/fuzz_message_header.py -v --tb=short
```

This will run 10,000 examples per test (may take 10-20 minutes).

**Monitor for**:
- Unexpected crashes
- New failing examples
- Performance issues
- Memory leaks

**Acceptance Criteria**:
- [ ] Extensive fuzzing completed
- [ ] No unexpected crashes
- [ ] All failures are documented
- [ ] Hypothesis statistics reviewed

---

## Task 1.12: Document Findings

**File**: `/home/user/exabgp/tests/fuzz/fuzz_message_header.py`

**What to do**:
Add module-level documentation:

```python
"""Fuzzing tests for BGP message header parsing.

This module tests the BGP message header parser (reactor/network/connection.py::reader())
with various malformed and edge-case inputs to ensure robustness.

BGP Message Header Structure:
    - Marker: 16 bytes (must be all 0xFF)
    - Length: 2 bytes (valid range: 19-4096)
    - Type: 1 byte (valid values: 1-5)

Test Coverage:
    - Random binary data fuzzing
    - Marker validation (all 16-byte combinations)
    - Length validation (all 16-bit values)
    - Type validation (all 8-bit values)
    - Truncated headers (< 19 bytes)
    - Bit-flip mutations
    - Edge cases (min/max valid values)
    - Real-world examples

Test Statistics:
    - Total tests: [count]
    - Coverage: [percentage]% of connection.py::reader()
    - Hypothesis examples per test: 50 (dev), 100 (ci), 10000 (extensive)

Findings:
    - [Document any bugs found]
    - [Document unexpected behaviors]
    - [Document performance observations]
"""
```

**Acceptance Criteria**:
- [ ] Module docstring complete
- [ ] Test coverage documented
- [ ] Findings documented
- [ ] File saved

---

## Task 1.13: Commit Changes

**What to do**:
```bash
cd /home/user/exabgp
git add tests/fuzz/fuzz_message_header.py
git commit -m "Add comprehensive fuzzing tests for BGP message header parser

- Test marker validation with all 16-byte combinations
- Test length field with all possible values (0-65535)
- Test message type with all byte values (0-255)
- Test truncated headers and edge cases
- Test real-world BGP message headers
- Achieve 95%+ coverage of connection.py::reader()

Fuzzing includes:
- Random binary data (Hypothesis)
- Targeted value fuzzing for each field
- Bit-flip mutations
- Boundary value testing
- Real-world examples from actual BGP sessions

Test statistics:
- [X] tests total
- [Y]% coverage of reader() function
- 10,000 examples per test in extensive mode"
```

**Acceptance Criteria**:
- [ ] File added and committed
- [ ] Commit message descriptive
- [ ] Statistics included in message

---

## Completion Checklist

- [ ] Task 1.1: Reader implementation understood
- [ ] Task 1.2: Basic fuzzing test created
- [ ] Task 1.3: Reader API investigated
- [ ] Task 1.4: Test helper created
- [ ] Task 1.5: Specific fuzzing tests added
- [ ] Task 1.6: Tests running successfully
- [ ] Task 1.7: Edge case tests added
- [ ] Task 1.8: Real-world examples added
- [ ] Task 1.9: Coverage measured
- [ ] Task 1.10: Uncovered cases tested
- [ ] Task 1.11: Extensive fuzzing completed
- [ ] Task 1.12: Findings documented
- [ ] Task 1.13: Changes committed

**Estimated Total Time**: 3-4 hours
**Next File**: `02-FUZZ-UPDATE-MESSAGE.md`
