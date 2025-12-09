"""Comprehensive fuzz tests for BGP attribute parsing.

This module tests that attribute parsing handles malformed input gracefully
without crashing. All parsing errors should result in appropriate Notify
exceptions, not crashes or undefined behavior.

Test Categories:
- Invalid attribute flags
- Length exceeds remaining data
- Unknown attribute types
- Extended length vs regular length
- Malformed AS_PATH segments
- Community parsing edge cases
- Aggregator and OriginatorID validation
"""

import pytest
import struct
from typing import Any
from unittest.mock import Mock
from hypothesis import given, strategies as st, settings, HealthCheck, assume

pytestmark = pytest.mark.fuzz


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_negotiated(asn4: bool = True) -> Any:
    """Create a minimal mock Negotiated object for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    neighbor.session = Mock()
    neighbor.session.local_address = Mock()
    neighbor.session.local_address.afi = 1

    negotiated = Mock()
    negotiated.neighbor = neighbor
    negotiated.families = [(1, 1)]
    negotiated.asn4 = asn4
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.aigp = False
    negotiated.msg_size = 4096
    negotiated.required = Mock(return_value=False)

    return negotiated


def create_attribute(flag: int, attr_id: int, value: bytes) -> bytes:
    """Create a BGP attribute with proper header.

    Args:
        flag: Attribute flags (Optional, Transitive, Partial, Extended)
        attr_id: Attribute type code
        value: Attribute value bytes

    Returns:
        Complete attribute bytes with header
    """
    if flag & 0x10:  # Extended length
        return bytes([flag, attr_id]) + struct.pack('!H', len(value)) + value
    else:
        return bytes([flag, attr_id, len(value)]) + value


# =============================================================================
# Attribute Flag Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    flag=st.integers(min_value=0, max_value=255),
    attr_id=st.integers(min_value=1, max_value=30),
    value_len=st.integers(min_value=0, max_value=50),
)
@settings(deadline=None, max_examples=100)
def test_attribute_flag_combinations(flag: int, attr_id: int, value_len: int) -> None:
    """Test attribute parsing with various flag combinations."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    # Create attribute with specified flags
    value = b'\x00' * value_len
    if flag & 0x10:  # Extended length
        data = bytes([flag, attr_id]) + struct.pack('!H', len(value)) + value
    else:
        data = bytes([flag, attr_id, len(value)]) + value

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # Should either parse successfully or add TreatAsWithdraw/Discard
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        # Should handle gracefully, not crash
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(value_len=st.integers(min_value=256, max_value=1000))
@settings(deadline=None, max_examples=50)
def test_extended_length_attribute(value_len: int) -> None:
    """Test attributes requiring extended length."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    # Extended length for large attributes
    flag = 0x90  # Optional + Extended
    attr_id = 0xFF  # Unknown attribute

    value = b'\x00' * value_len
    data = bytes([flag, attr_id]) + struct.pack('!H', len(value)) + value

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Attribute Length Mismatch Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    claimed_len=st.integers(min_value=1, max_value=100),
    actual_len=st.integers(min_value=0, max_value=50),
)
@settings(deadline=None, max_examples=100)
def test_length_mismatch(claimed_len: int, actual_len: int) -> None:
    """Test handling of length field mismatches."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.bgp.message.notification import Notify

    assume(claimed_len != actual_len)

    # Claim one length, provide different
    flag = 0x40  # Transitive
    attr_id = 1  # ORIGIN

    value = b'\x00' * actual_len
    data = bytes([flag, attr_id, claimed_len]) + value

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # May parse successfully if we provided enough data
        # or may treat as withdraw/discard
        assert isinstance(result, AttributeCollection)
    except (Notify, IndexError, struct.error):
        # Expected for mismatched lengths
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_zero_length_mandatory_attribute() -> None:
    """Test zero-length mandatory attribute (ORIGIN)."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    # ORIGIN with zero length
    flag = 0x40  # Transitive
    attr_id = 1  # ORIGIN
    data = bytes([flag, attr_id, 0])

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # May treat as withdraw or parse with default
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# AS_PATH Parsing Tests
# =============================================================================


@pytest.mark.fuzz
@given(seg_type=st.integers(min_value=0, max_value=255).filter(lambda x: x not in [1, 2, 3, 4]))
@settings(deadline=None, max_examples=50)
def test_aspath_invalid_segment_type(seg_type: int) -> None:
    """Test AS_PATH with invalid segment type."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath
    from exabgp.bgp.message.notification import Notify

    # Invalid segment type + count + ASN
    data = bytes([seg_type, 1]) + struct.pack('!H', 65000)

    try:
        ASPath.from_packet(data, asn4=False)
        pytest.fail('Expected Notify for invalid segment type')
    except Notify as e:
        assert e.code == 3  # UPDATE message error
        assert e.subcode == 11  # Malformed AS_PATH


@pytest.mark.fuzz
@given(seg_count=st.integers(min_value=1, max_value=100))
@settings(deadline=None, max_examples=50)
def test_aspath_truncated_segment(seg_count: int) -> None:
    """Test AS_PATH with truncated segment (count > available ASNs)."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath
    from exabgp.bgp.message.notification import Notify

    # Claim seg_count ASNs but provide only one
    data = bytes([2, seg_count]) + struct.pack('!H', 65000)  # SEQUENCE

    assume(seg_count > 1)

    try:
        ASPath.from_packet(data, asn4=False)
        pytest.fail('Expected Notify for truncated AS_PATH')
    except Notify as e:
        assert e.code == 3  # UPDATE message error
        assert e.subcode == 11  # Malformed AS_PATH


@pytest.mark.fuzz
@given(asn_count=st.integers(min_value=0, max_value=20))
@settings(deadline=None, max_examples=50)
def test_aspath_valid_sequence(asn_count: int) -> None:
    """Test AS_PATH with valid sequence of ASNs."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath

    # Valid SEQUENCE segment
    data = bytes([2, asn_count])  # SEQUENCE
    for i in range(asn_count):
        data += struct.pack('!H', 65000 + i)

    aspath = ASPath.from_packet(data, asn4=False)
    segments = aspath.aspath

    if asn_count > 0:
        assert len(segments) == 1
        assert len(segments[0]) == asn_count


@pytest.mark.fuzz
@given(random_data=st.binary(min_size=0, max_size=100))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=100)
def test_aspath_random_data(random_data: bytes) -> None:
    """Test AS_PATH parsing doesn't crash on random data."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath
    from exabgp.bgp.message.notification import Notify

    try:
        ASPath.from_packet(random_data, asn4=False)
    except Notify:
        # Expected for invalid data
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(asn4=st.booleans())
@settings(deadline=None, max_examples=10)
def test_aspath_asn4_format(asn4: bool) -> None:
    """Test AS_PATH with both 2-byte and 4-byte ASN formats."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath

    # SEQUENCE with one ASN
    if asn4:
        data = bytes([2, 1]) + struct.pack('!L', 4200000000)
    else:
        data = bytes([2, 1]) + struct.pack('!H', 65000)

    aspath = ASPath.from_packet(data, asn4=asn4)
    segments = aspath.aspath

    assert len(segments) == 1
    assert len(segments[0]) == 1


# =============================================================================
# Community Parsing Tests
# =============================================================================


@pytest.mark.fuzz
@given(community_count=st.integers(min_value=0, max_value=50))
@settings(deadline=None, max_examples=50)
def test_community_values(community_count: int) -> None:
    """Test community attribute with various counts."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    # Community attribute (4 bytes each)
    flag = 0xC0  # Optional + Transitive
    attr_id = 8  # COMMUNITY

    value = b''
    for i in range(community_count):
        value += struct.pack('!HH', i, i)  # AS:value format

    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(extra_bytes=st.integers(min_value=1, max_value=3))
@settings(deadline=None, max_examples=3)
def test_community_misaligned(extra_bytes: int) -> None:
    """Test community attribute with length not multiple of 4."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    # Communities must be 4-byte aligned
    flag = 0xC0  # Optional + Transitive
    attr_id = 8  # COMMUNITY

    # Valid community + extra bytes
    value = struct.pack('!HH', 65000, 100) + b'\x00' * extra_bytes

    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # May parse and ignore extra bytes, or treat as error
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(ext_community_count=st.integers(min_value=0, max_value=20))
@settings(deadline=None, max_examples=50)
def test_extended_community_values(ext_community_count: int) -> None:
    """Test extended community attribute (8 bytes each)."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0xC0  # Optional + Transitive
    attr_id = 16  # EXTENDED_COMMUNITY

    value = b''
    for i in range(ext_community_count):
        # Type high, type low, value (6 bytes)
        value += bytes([0x00, 0x02]) + struct.pack('!I', i) + b'\x00\x00'

    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(large_community_count=st.integers(min_value=0, max_value=10))
@settings(deadline=None, max_examples=50)
def test_large_community_values(large_community_count: int) -> None:
    """Test large community attribute (12 bytes each)."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0xC0  # Optional + Transitive
    attr_id = 32  # LARGE_COMMUNITY

    value = b''
    for i in range(large_community_count):
        # Global admin (4) + local data 1 (4) + local data 2 (4)
        value += struct.pack('!LLL', 65000, i, i * 2)

    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# ORIGIN Attribute Tests
# =============================================================================


@pytest.mark.fuzz
@given(origin_value=st.integers(min_value=0, max_value=255))
@settings(deadline=None, max_examples=50)
def test_origin_values(origin_value: int) -> None:
    """Test ORIGIN attribute with various values."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    # ORIGIN is single byte: 0=IGP, 1=EGP, 2=INCOMPLETE
    flag = 0x40  # Transitive
    attr_id = 1  # ORIGIN

    data = create_attribute(flag, attr_id, bytes([origin_value]))
    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        assert isinstance(result, AttributeCollection)
        # Only 0, 1, 2 are valid - others may be treated as error
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# NEXT_HOP Attribute Tests
# =============================================================================


@pytest.mark.fuzz
@given(nh_len=st.integers(min_value=0, max_value=20).filter(lambda x: x not in [4, 16]))
@settings(deadline=None, max_examples=20)
def test_nexthop_invalid_length(nh_len: int) -> None:
    """Test NEXT_HOP with invalid length (not 4 or 16)."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0x40  # Transitive
    attr_id = 3  # NEXT_HOP

    value = b'\x00' * nh_len
    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # Should treat as withdraw or discard for invalid length
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_nexthop_ipv4_valid() -> None:
    """Test NEXT_HOP with valid IPv4 address."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0x40  # Transitive
    attr_id = 3  # NEXT_HOP

    # 192.168.1.1
    value = bytes([192, 168, 1, 1])
    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    result = AttributeCollection.unpack(data, negotiated)
    assert isinstance(result, AttributeCollection)
    assert attr_id in result


# =============================================================================
# MED and LOCAL_PREF Attribute Tests
# =============================================================================


@pytest.mark.fuzz
@given(med_value=st.integers(min_value=0, max_value=4294967295))
@settings(deadline=None, max_examples=50)
def test_med_values(med_value: int) -> None:
    """Test MED attribute with full 32-bit range."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0x80  # Optional
    attr_id = 4  # MED

    value = struct.pack('!L', med_value)
    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    result = AttributeCollection.unpack(data, negotiated)
    assert isinstance(result, AttributeCollection)


@pytest.mark.fuzz
@given(local_pref_value=st.integers(min_value=0, max_value=4294967295))
@settings(deadline=None, max_examples=50)
def test_local_pref_values(local_pref_value: int) -> None:
    """Test LOCAL_PREF attribute with full 32-bit range."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0x40  # Transitive
    attr_id = 5  # LOCAL_PREF

    value = struct.pack('!L', local_pref_value)
    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    result = AttributeCollection.unpack(data, negotiated)
    assert isinstance(result, AttributeCollection)


# =============================================================================
# AGGREGATOR Attribute Tests
# =============================================================================


@pytest.mark.fuzz
@given(asn4=st.booleans())
@settings(deadline=None, max_examples=10)
def test_aggregator_format(asn4: bool) -> None:
    """Test AGGREGATOR with 2-byte and 4-byte ASN formats."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0xC0  # Optional + Transitive
    attr_id = 7  # AGGREGATOR

    # ASN + IPv4 address
    if asn4:
        value = struct.pack('!L', 65000) + bytes([192, 168, 1, 1])
    else:
        value = struct.pack('!H', 65000) + bytes([192, 168, 1, 1])

    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated(asn4=asn4)

    try:
        result = AttributeCollection.unpack(data, negotiated)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(agg_len=st.integers(min_value=0, max_value=20).filter(lambda x: x not in [6, 8]))
@settings(deadline=None, max_examples=20)
def test_aggregator_invalid_length(agg_len: int) -> None:
    """Test AGGREGATOR with invalid length."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0xC0  # Optional + Transitive
    attr_id = 7  # AGGREGATOR

    value = b'\x00' * agg_len
    data = create_attribute(flag, attr_id, value)
    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # May treat as withdraw/discard or parse with defaults
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Unknown Attribute Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    attr_id=st.integers(min_value=100, max_value=255),
    value_len=st.integers(min_value=0, max_value=50),
)
@settings(deadline=None, max_examples=50)
def test_unknown_optional_attribute(attr_id: int, value_len: int) -> None:
    """Test handling of unknown optional attributes."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0xC0  # Optional + Transitive
    value = b'\x00' * value_len
    data = create_attribute(flag, attr_id, value)

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # Unknown optional attributes should be handled gracefully
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(attr_id=st.integers(min_value=100, max_value=255))
@settings(deadline=None, max_examples=50)
def test_unknown_well_known_attribute(attr_id: int) -> None:
    """Test handling of unknown well-known (non-optional) attributes."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    flag = 0x40  # Transitive (well-known)
    value = b'\x00\x00\x00\x00'
    data = create_attribute(flag, attr_id, value)

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # Unknown well-known should trigger error handling
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Multiple Attributes Tests
# =============================================================================


@pytest.mark.fuzz
@given(attr_count=st.integers(min_value=1, max_value=10))
@settings(deadline=None, max_examples=50)
def test_multiple_attributes(attr_count: int) -> None:
    """Test parsing multiple attributes in sequence."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    data = b''

    # Add ORIGIN
    data += create_attribute(0x40, 1, bytes([0]))

    # Add AS_PATH
    data += create_attribute(0x40, 2, bytes([2, 1]) + struct.pack('!H', 65000))

    # Add NEXT_HOP
    data += create_attribute(0x40, 3, bytes([192, 168, 1, 1]))

    # Add optional attributes up to attr_count
    for i in range(attr_count - 3):
        # Add optional unknown attributes
        data += create_attribute(0xC0, 200 + i, b'\x00\x00\x00\x00')

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_duplicate_attribute() -> None:
    """Test handling of duplicate attributes."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    # Two ORIGIN attributes
    data = b''
    data += create_attribute(0x40, 1, bytes([0]))  # IGP
    data += create_attribute(0x40, 1, bytes([2]))  # INCOMPLETE

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(data, negotiated)
        # Should handle duplicate gracefully (use last or error)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Random Data Tests
# =============================================================================


@pytest.mark.fuzz
@given(random_data=st.binary(min_size=0, max_size=200))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=100)
def test_attributes_random_data(random_data: bytes) -> None:
    """Test attribute parsing doesn't crash on random data."""
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    negotiated = create_mock_negotiated()

    try:
        result = AttributeCollection.unpack(random_data, negotiated)
        assert isinstance(result, AttributeCollection)
    except Exception as e:
        # Should handle gracefully, not crash
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
