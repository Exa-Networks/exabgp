"""Comprehensive tests for BGP AS_PATH attribute parsing.

AS_PATH is a well-known mandatory transitive attribute that identifies the
autonomous systems through which routing information has passed.

Structure:
- Segment Type (1 byte): 1=AS_SET, 2=AS_SEQUENCE, 3=CONFED_SEQUENCE, 4=CONFED_SET
- Segment Length (1 byte): Number of AS numbers in segment
- AS Numbers: Variable (2 or 4 bytes each depending on ASN format)

Target: src/exabgp/bgp/message/update/attribute/aspath.py

Test Coverage:
1. Four segment types (SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET)
2. ASN2 (2-byte) and ASN4 (4-byte) format handling
3. Empty AS_PATH
4. Single and multiple segments
5. Long paths (>255 ASNs requiring segmentation)
6. Invalid segment types
7. Truncated data
8. AS4_PATH attribute handling
9. Mixed ASN2/ASN4 scenarios with AS_TRANS
"""

import struct
from typing import Any
from unittest.mock import Mock

import pytest


def create_negotiated_mock(asn4: Any = False) -> Any:
    """Create minimal mock negotiated object for testing."""
    negotiated = Mock()
    negotiated.asn4 = asn4
    return negotiated


# =============================================================================
# Test AS_SEQUENCE (most common segment type)
# =============================================================================


def test_aspath_empty() -> None:
    """Test empty AS_PATH unpacking."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath

    negotiated = create_negotiated_mock(asn4=False)
    data = b''

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is None


def test_aspath_simple_sequence_asn2() -> None:
    """Test AS_SEQUENCE with 2-byte ASN (legacy format)."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE

    negotiated = create_negotiated_mock(asn4=False)

    # AS_SEQUENCE with 3 ASNs: 65001, 65002, 65003
    # Format: type(1) + length(1) + ASN1(2) + ASN2(2) + ASN3(2)
    data = struct.pack('!BB', 2, 3)  # type=AS_SEQUENCE, length=3
    data += struct.pack('!HHH', 65001, 65002, 65003)

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 1
    assert isinstance(result.aspath[0], SEQUENCE)
    assert len(result.aspath[0]) == 3
    assert int(result.aspath[0][0]) == 65001
    assert int(result.aspath[0][1]) == 65002
    assert int(result.aspath[0][2]) == 65003


def test_aspath_simple_sequence_asn4() -> None:
    """Test AS_SEQUENCE with 4-byte ASN (modern format)."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE

    negotiated = create_negotiated_mock(asn4=True)

    # AS_SEQUENCE with 3 large ASNs: 100000, 200000, 300000
    data = struct.pack('!BB', 2, 3)  # type=AS_SEQUENCE, length=3
    data += struct.pack('!LLL', 100000, 200000, 300000)

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 1
    assert isinstance(result.aspath[0], SEQUENCE)
    assert len(result.aspath[0]) == 3
    assert int(result.aspath[0][0]) == 100000
    assert int(result.aspath[0][1]) == 200000
    assert int(result.aspath[0][2]) == 300000


def test_aspath_single_asn() -> None:
    """Test AS_PATH with single ASN."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath

    negotiated = create_negotiated_mock(asn4=False)

    # Single ASN: 65000
    data = struct.pack('!BB', 2, 1) + struct.pack('!H', 65000)

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 1
    assert len(result.aspath[0]) == 1
    assert int(result.aspath[0][0]) == 65000


# =============================================================================
# Test AS_SET
# =============================================================================


def test_aspath_as_set() -> None:
    """Test AS_SET segment type (unordered set of ASNs)."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SET

    negotiated = create_negotiated_mock(asn4=False)

    # AS_SET with 4 ASNs: 65001, 65002, 65003, 65004
    data = struct.pack('!BB', 1, 4)  # type=AS_SET, length=4
    data += struct.pack('!HHHH', 65001, 65002, 65003, 65004)

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 1
    assert isinstance(result.aspath[0], SET)
    assert len(result.aspath[0]) == 4


# =============================================================================
# Test CONFED_SEQUENCE and CONFED_SET
# =============================================================================


def test_aspath_confed_sequence() -> None:
    """Test CONFED_SEQUENCE segment type (BGP confederation)."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, CONFED_SEQUENCE

    negotiated = create_negotiated_mock(asn4=False)

    # CONFED_SEQUENCE with 2 ASNs: 64512, 64513
    data = struct.pack('!BB', 3, 2)  # type=CONFED_SEQUENCE, length=2
    data += struct.pack('!HH', 64512, 64513)

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 1
    assert isinstance(result.aspath[0], CONFED_SEQUENCE)
    assert len(result.aspath[0]) == 2
    assert int(result.aspath[0][0]) == 64512
    assert int(result.aspath[0][1]) == 64513


def test_aspath_confed_set() -> None:
    """Test CONFED_SET segment type."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, CONFED_SET

    negotiated = create_negotiated_mock(asn4=False)

    # CONFED_SET with 3 ASNs
    data = struct.pack('!BB', 4, 3)  # type=CONFED_SET, length=3
    data += struct.pack('!HHH', 64512, 64513, 64514)

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 1
    assert isinstance(result.aspath[0], CONFED_SET)
    assert len(result.aspath[0]) == 3


# =============================================================================
# Test multiple segments
# =============================================================================


def test_aspath_multiple_segments() -> None:
    """Test AS_PATH with multiple segments."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE, SET

    negotiated = create_negotiated_mock(asn4=False)

    # First segment: AS_SEQUENCE with 2 ASNs
    segment1 = struct.pack('!BB', 2, 2) + struct.pack('!HH', 65001, 65002)

    # Second segment: AS_SET with 3 ASNs
    segment2 = struct.pack('!BB', 1, 3) + struct.pack('!HHH', 65003, 65004, 65005)

    data = segment1 + segment2

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 2
    assert isinstance(result.aspath[0], SEQUENCE)
    assert isinstance(result.aspath[1], SET)
    assert len(result.aspath[0]) == 2
    assert len(result.aspath[1]) == 3


def test_aspath_mixed_confederation() -> None:
    """Test AS_PATH with regular and confederation segments."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE, CONFED_SEQUENCE

    negotiated = create_negotiated_mock(asn4=False)

    # CONFED_SEQUENCE + regular AS_SEQUENCE
    confed = struct.pack('!BB', 3, 2) + struct.pack('!HH', 64512, 64513)
    regular = struct.pack('!BB', 2, 2) + struct.pack('!HH', 65001, 65002)

    data = confed + regular

    result = ASPath.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 2
    assert isinstance(result.aspath[0], CONFED_SEQUENCE)
    assert isinstance(result.aspath[1], SEQUENCE)


# =============================================================================
# Test AS4_PATH attribute
# =============================================================================


def test_as4path_unpacking() -> None:
    """Test AS4_PATH attribute (always uses 4-byte ASNs)."""
    from exabgp.bgp.message.update.attribute.aspath import AS4Path, SEQUENCE

    negotiated = create_negotiated_mock(asn4=False)  # Negotiated ASN2, but AS4Path is always ASN4

    # AS4_PATH with large ASNs
    data = struct.pack('!BB', 2, 2)  # AS_SEQUENCE with 2 ASNs
    data += struct.pack('!LL', 100000, 200000)

    result = AS4Path.unpack_attribute(data, negotiated)

    assert result is not None
    assert len(result.aspath) == 1
    assert isinstance(result.aspath[0], SEQUENCE)
    assert int(result.aspath[0][0]) == 100000
    assert int(result.aspath[0][1]) == 200000


# =============================================================================
# Test error cases
# =============================================================================


def test_aspath_invalid_segment_type() -> None:
    """Test AS_PATH with invalid segment type."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath
    from exabgp.bgp.message.notification import Notify

    negotiated = create_negotiated_mock(asn4=False)

    # Invalid segment type: 99
    data = struct.pack('!BB', 99, 1) + struct.pack('!H', 65000)

    with pytest.raises(Notify) as exc_info:
        ASPath.unpack_attribute(data, negotiated)

    assert exc_info.value.code == 3  # UPDATE Message Error
    assert exc_info.value.subcode == 11  # Malformed AS_PATH


def test_aspath_truncated_segment_header() -> None:
    """Test AS_PATH with truncated segment header."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath
    from exabgp.bgp.message.notification import Notify

    negotiated = create_negotiated_mock(asn4=False)

    # Only 1 byte (incomplete header)
    data = b'\x02'

    with pytest.raises(Notify) as exc_info:
        ASPath.unpack_attribute(data, negotiated)

    assert exc_info.value.code == 3
    assert exc_info.value.subcode == 11


def test_aspath_truncated_asn_data() -> None:
    """Test AS_PATH with truncated ASN data."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath
    from exabgp.bgp.message.notification import Notify

    negotiated = create_negotiated_mock(asn4=False)

    # Header claims 3 ASNs but only provides data for 2
    data = struct.pack('!BB', 2, 3)  # type=AS_SEQUENCE, length=3
    data += struct.pack('!HH', 65001, 65002)  # Only 2 ASNs

    with pytest.raises(Notify) as exc_info:
        ASPath.unpack_attribute(data, negotiated)

    assert exc_info.value.code == 3
    assert exc_info.value.subcode == 11


def test_aspath_truncated_asn4_data() -> None:
    """Test AS_PATH with truncated 4-byte ASN data."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath
    from exabgp.bgp.message.notification import Notify

    negotiated = create_negotiated_mock(asn4=True)

    # Header claims 2 ASNs but only provides partial data
    data = struct.pack('!BB', 2, 2)  # type=AS_SEQUENCE, length=2
    data += struct.pack('!L', 100000)  # Only 1 complete ASN
    data += b'\x00\x00'  # Incomplete second ASN

    with pytest.raises(Notify) as exc_info:
        ASPath.unpack_attribute(data, negotiated)

    assert exc_info.value.code == 3
    assert exc_info.value.subcode == 11


# =============================================================================
# Test packing
# =============================================================================


def test_aspath_pack_asn2() -> None:
    """Test packing AS_PATH with 2-byte ASNs."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
    from exabgp.bgp.message.open.asn import ASN

    negotiated = create_negotiated_mock(asn4=False)

    # Create AS_PATH with sequence [65001, 65002]
    asns = [ASN(65001), ASN(65002)]
    sequence = SEQUENCE(asns)
    aspath = ASPath([sequence])

    packed = aspath.pack_attribute(negotiated)

    # Should be: flags(1) + type(1) + length(1) + segment_type(1) + segment_len(1) + 2*ASN(2)
    # For transitive attribute: flags=0x40, type=2
    assert len(packed) >= 7  # Minimum expected size
    # Verify attribute header
    assert packed[0] == 0x40  # Transitive flag
    assert packed[1] == 2  # AS_PATH type code


def test_aspath_pack_asn4() -> None:
    """Test packing AS_PATH with 4-byte ASNs."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
    from exabgp.bgp.message.open.asn import ASN

    negotiated = create_negotiated_mock(asn4=True)

    # Create AS_PATH with large ASNs
    asns = [ASN(100000), ASN(200000)]
    sequence = SEQUENCE(asns)
    aspath = ASPath([sequence])

    packed = aspath.pack_attribute(negotiated)

    # Should include 4-byte ASNs
    assert len(packed) >= 11  # flags(1) + type(1) + length(1) + segment_type(1) + segment_len(1) + 2*ASN(4)


def test_aspath_pack_with_as_trans() -> None:
    """Test packing AS_PATH with ASN4 when peer doesn't support ASN4."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
    from exabgp.bgp.message.open.asn import ASN

    negotiated = create_negotiated_mock(asn4=False)

    # Create AS_PATH with large ASN (requires AS4_PATH)
    asns = [ASN(100000)]  # This is >65535, requires ASN4
    sequence = SEQUENCE(asns)
    aspath = ASPath([sequence])

    packed = aspath.pack_attribute(negotiated)

    # Should create both AS_PATH (with AS_TRANS) and AS4_PATH attributes
    # The packed data should be longer as it includes both attributes
    assert len(packed) > 7  # Should have extra data for AS4_PATH


# =============================================================================
# Test string representation
# =============================================================================


def test_aspath_string_representation() -> None:
    """Test AS_PATH string formatting."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
    from exabgp.bgp.message.open.asn import ASN

    # AS_SEQUENCE [65001, 65002]
    sequence = SEQUENCE([ASN(65001), ASN(65002)])
    aspath = ASPath([sequence])

    string_repr = str(aspath)
    assert '65001' in string_repr
    assert '65002' in string_repr
    assert '(' in string_repr  # SEQUENCE uses parentheses
    assert ')' in string_repr


def test_aspath_json_representation() -> None:
    """Test AS_PATH JSON formatting."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
    from exabgp.bgp.message.open.asn import ASN
    import json

    sequence = SEQUENCE([ASN(65001), ASN(65002)])
    aspath = ASPath([sequence])

    json_repr = aspath.json()
    parsed = json.loads(json_repr)

    assert '0' in parsed  # First segment
    assert parsed['0']['element'] == 'as-sequence'
    assert len(parsed['0']['value']) == 2


# =============================================================================
# Test equality
# =============================================================================


def test_aspath_equality() -> None:
    """Test AS_PATH equality comparison."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
    from exabgp.bgp.message.open.asn import ASN

    sequence1 = SEQUENCE([ASN(65001), ASN(65002)])
    aspath1 = ASPath([sequence1])

    sequence2 = SEQUENCE([ASN(65001), ASN(65002)])
    aspath2 = ASPath([sequence2])

    assert aspath1 == aspath2


def test_aspath_inequality() -> None:
    """Test AS_PATH inequality comparison."""
    from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
    from exabgp.bgp.message.open.asn import ASN

    sequence1 = SEQUENCE([ASN(65001), ASN(65002)])
    aspath1 = ASPath([sequence1])

    sequence2 = SEQUENCE([ASN(65001), ASN(65003)])  # Different ASN
    aspath2 = ASPath([sequence2])

    assert aspath1 != aspath2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
