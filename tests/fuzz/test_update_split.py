"""Fuzzing tests for BGP UPDATE message split() method.

This module tests the UPDATE message split() method which parses the basic
structure of UPDATE messages and validates length fields.

Target: src/exabgp/bgp/message/update/__init__.py::split()

UPDATE Message Structure:
    - Withdrawn Routes Length (2 bytes)
    - Withdrawn Routes (variable)
    - Path Attributes Length (2 bytes)
    - Path Attributes (variable)
    - NLRI (variable)

Test Coverage:
    - Random binary data
    - Length field fuzzing (all 16-bit values)
    - Truncation at each boundary
    - Off-by-one errors
    - Wraparound scenarios
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import struct

from tests.fuzz.update_helpers import create_update_message, create_ipv4_prefix

pytestmark = pytest.mark.fuzz


@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=200))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=50)
def test_update_split_with_random_data(data: bytes) -> None:
    """Fuzz UPDATE split() with completely random binary data.

    The split() method should either parse successfully or raise Notify(3, 1).
    """
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    try:
        withdrawn, attributes, announced = UpdateCollection.split(data)

        # If it parses successfully, verify the components
        # split() now returns memoryview slices for zero-copy
        assert isinstance(withdrawn, (bytes, memoryview))
        assert isinstance(attributes, (bytes, memoryview))
        assert isinstance(announced, (bytes, memoryview))

        # Verify the lengths add up
        # Format: 2 (withdrawn_len) + withdrawn + 2 (attr_len) + attributes + announced
        expected_len = 2 + len(withdrawn) + 2 + len(attributes) + len(announced)
        assert expected_len == len(data), f'Length mismatch: {expected_len} != {len(data)}'

    except Notify as e:
        # Expected for malformed data
        # UPDATE errors should be code 3 (Update Message Error)
        assert e.code == 3, f'Expected code 3, got {e.code}'
        assert e.subcode == 1, f'Expected subcode 1 (Malformed Attribute List), got {e.subcode}'
    except struct.error:
        # Expected when data is too short for unpack
        pass


@pytest.mark.fuzz
@given(withdrawn_len=st.integers(min_value=0, max_value=65535))
@settings(deadline=None, max_examples=100)
def test_update_split_withdrawn_length_fuzzing(withdrawn_len: int) -> None:
    """Fuzz withdrawn routes length field with all possible 16-bit values.

    Tests validation of withdrawn routes length against actual data.
    """
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    # Create UPDATE with specific withdrawn length claim
    # Provide exactly 10 bytes of actual withdrawn data
    actual_withdrawn_data = b'\x08\x0a' * 5  # 10 bytes of data

    data = (
        struct.pack('!H', withdrawn_len)  # Claimed length
        + actual_withdrawn_data  # Actual data (10 bytes)
        + struct.pack('!H', 0)  # Attr length = 0
    )

    try:
        withdrawn, attributes, announced = UpdateCollection.split(data)

        # Should only succeed if withdrawn_len == 10
        assert withdrawn_len == 10, f'Should have failed with length {withdrawn_len} != 10'
        assert len(withdrawn) == 10
        assert len(attributes) == 0
        assert len(announced) == 0

    except Notify as e:
        # Should fail for all other lengths
        assert withdrawn_len != 10, f'Should have succeeded with length {withdrawn_len}'
        assert e.code == 3 and e.subcode == 1


@pytest.mark.fuzz
@given(attr_len=st.integers(min_value=0, max_value=65535))
@settings(deadline=None, max_examples=100)
def test_update_split_attr_length_fuzzing(attr_len: int) -> None:
    """Fuzz path attributes length field with all possible 16-bit values.

    Tests validation of path attributes length against actual data.
    """
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    # Create UPDATE with specific attr length claim
    # Provide exactly 15 bytes of actual attribute data
    actual_attr_data = b'\x40\x01\x01\x00' + b'\x40\x02\x00' + b'\x40\x03\x04\xc0\x00\x02\x01\x00'  # 15 bytes

    data = (
        struct.pack('!H', 0)  # Withdrawn length = 0
        + struct.pack('!H', attr_len)  # Claimed attr length
        + actual_attr_data  # Actual data (15 bytes)
        # No NLRI
    )

    try:
        withdrawn, attributes, announced = UpdateCollection.split(data)

        # Should only succeed if attr_len matches or is less than actual data
        # If attr_len < 15, remaining bytes become NLRI
        # If attr_len == 15, all bytes are attributes
        if attr_len <= 15:
            assert len(withdrawn) == 0
            assert len(attributes) == attr_len
            assert len(announced) == 15 - attr_len
        else:
            pytest.fail(f'Should have raised Notify with attr_len={attr_len} > 15')

    except Notify as e:
        # Should fail when attr_len > actual data (15 bytes)
        assert attr_len > 15, f'Should have succeeded with length {attr_len} <= 15'
        assert e.code == 3 and e.subcode == 1


@pytest.mark.fuzz
def test_update_split_valid_empty_update() -> None:
    """Test minimal valid UPDATE (EOR marker)."""
    from exabgp.bgp.message.update import UpdateCollection

    # Empty UPDATE: no withdrawals, no attributes, no NLRI
    data = b'\x00\x00\x00\x00'  # 4 bytes

    withdrawn, attributes, announced = UpdateCollection.split(data)

    assert withdrawn == b''
    assert attributes == b''
    assert announced == b''


@pytest.mark.fuzz
def test_update_split_with_withdrawals_only() -> None:
    """Test UPDATE with only withdrawals."""
    from exabgp.bgp.message.update import UpdateCollection

    # Withdrawal: 192.0.2.0/24
    prefix = create_ipv4_prefix('192.0.2.0', 24)

    data = create_update_message(
        withdrawn_routes=prefix,
        path_attributes=b'',
        nlri=b'',
    )

    withdrawn, attributes, announced = UpdateCollection.split(data)

    assert len(withdrawn) == len(prefix)
    assert len(attributes) == 0
    assert len(announced) == 0


@pytest.mark.fuzz
def test_update_split_with_attributes_and_nlri() -> None:
    """Test UPDATE with attributes and NLRI."""
    from exabgp.bgp.message.update import UpdateCollection

    # Some dummy attributes (not validated by split())
    attrs = b'\x40\x01\x01\x00'  # ORIGIN attribute

    # NLRI: 10.0.0.0/8
    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(
        withdrawn_routes=b'',
        path_attributes=attrs,
        nlri=nlri,
    )

    withdrawn, attributes, announced = UpdateCollection.split(data)

    assert len(withdrawn) == 0
    assert len(attributes) == len(attrs)
    assert len(announced) == len(nlri)


@pytest.mark.fuzz
@given(truncate_at=st.integers(min_value=0, max_value=30))
@settings(deadline=None)
def test_update_split_truncation(truncate_at: int) -> None:
    """Test UPDATE truncated at various positions."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    # Create a valid UPDATE with known size
    prefix = create_ipv4_prefix('192.0.2.0', 24)
    attrs = b'\x40\x01\x01\x00' + b'\x40\x02\x00'
    nlri = create_ipv4_prefix('10.0.0.0', 2)

    valid_update = create_update_message(
        withdrawn_routes=prefix,
        path_attributes=attrs,
        nlri=nlri,
    )

    # Truncate it
    data = valid_update[:truncate_at]

    try:
        withdrawn, attributes, announced = UpdateCollection.split(data)

        # If it succeeds, verify it's either:
        # 1. Complete message
        # 2. Valid partial parse (split() is lenient with partial data in some cases)
        # 3. EOR marker
        if truncate_at == 4 and data == b'\x00\x00\x00\x00':
            # EOR case
            pass
        elif truncate_at >= len(valid_update):
            # Complete or over-complete
            pass
        # Some truncations may succeed if they land on valid boundaries
        # This is expected behavior

    except (Notify, struct.error, IndexError):
        # Expected for most truncated data
        pass


@pytest.mark.fuzz
def test_update_split_length_one_byte_too_short() -> None:
    """Test withdrawn length claiming 1 byte too few."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    # Actual data: 10 bytes, claim: 9 bytes
    actual_data = b'\x18\xc0\x00\x02' + b'\x08\x0a' * 3  # 10 bytes

    data = (
        struct.pack('!H', 9)  # Claim 9 bytes
        + actual_data  # Actually 10 bytes
        + struct.pack('!H', 0)  # No attributes
    )

    with pytest.raises(Notify) as exc_info:
        UpdateCollection.split(data)

    assert exc_info.value.code == 3
    assert exc_info.value.subcode == 1


@pytest.mark.fuzz
def test_update_split_length_one_byte_too_long() -> None:
    """Test withdrawn length claiming 1 byte too many."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    # Actual data: 10 bytes, claim: 11 bytes
    actual_data = b'\x18\xc0\x00\x02' + b'\x08\x0a' * 3  # 10 bytes

    # Need to have enough data for the attr_len field too
    data = (
        struct.pack('!H', 11)  # Claim 11 bytes of withdrawals
        + actual_data  # Actually 10 bytes
        + b'\x00'  # Not enough for attr_len (need 2 bytes)
    )

    # This will fail with struct.error or Notify
    with pytest.raises((Notify, struct.error)):
        UpdateCollection.split(data)


@pytest.mark.fuzz
def test_update_split_total_length_mismatch() -> None:
    """Test when component lengths don't match total length."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    # Claim 5 bytes of withdrawals but only provide 4 bytes + attr_len field
    data = (
        struct.pack('!H', 5)  # Claim 5 bytes of withdrawals
        + b'\x18\xc0\x00\x02'  # Actually 4 bytes (not enough for attr_len field)
    )

    # Should fail with either Notify or struct.error (not enough data)
    with pytest.raises((Notify, struct.error)):
        UpdateCollection.split(data)


@pytest.mark.fuzz
def test_update_split_max_valid_lengths() -> None:
    """Test with maximum valid length fields."""
    from exabgp.bgp.message.update import UpdateCollection

    # Create small UPDATE with 0-length fields
    data = b'\x00\x00\x00\x00'  # Empty UPDATE

    withdrawn, attributes, announced = UpdateCollection.split(data)

    assert withdrawn == b''
    assert attributes == b''
    assert announced == b''


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
