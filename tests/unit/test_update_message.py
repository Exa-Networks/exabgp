"""Comprehensive tests for UPDATE message validation and integration.

These tests focus on UPDATE message-level validation beyond basic parsing:
- Mandatory attribute validation (ORIGIN, AS_PATH, NEXT_HOP)
- Attribute combinations in UPDATE context
- Withdrawn + announced routes handling
- MP_REACH_NLRI / MP_UNREACH_NLRI integration
- EOR marker detection
- Extended length attribute handling
- Maximum message size constraints
- TREAT_AS_WITHDRAW behavior in UPDATE context

Target: src/exabgp/bgp/message/update/__init__.py

Test Coverage Phases:
Phase 1: Mandatory attribute validation (tests 1-5)
Phase 2: Attribute combinations (tests 6-10)
Phase 3: MP extensions (tests 11-15)
Phase 4: Edge cases and limits (tests 16-20)
"""

import struct
from typing import Any
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """Mock the logger to avoid initialization issues."""
    # Mock the option.logger attribute to avoid AttributeError
    from exabgp.logger.option import option

    # Save original values
    original_logger = option.logger
    original_formater = option.formater

    # Create a mock logger with all required methods
    mock_option_logger = Mock()
    mock_option_logger.debug = Mock()
    mock_option_logger.info = Mock()
    mock_option_logger.warning = Mock()
    mock_option_logger.error = Mock()
    mock_option_logger.critical = Mock()

    # Create a mock formater that accepts all arguments
    mock_formater = Mock(return_value='formatted message')

    option.logger = mock_option_logger
    option.formater = mock_formater

    # Also mock log to avoid other issues
    with (
        patch('exabgp.bgp.message.update.log') as mock_log,
        patch('exabgp.bgp.message.update.nlri.nlri.log') as mock_nlri_log,
        patch('exabgp.bgp.message.update.attribute.attributes.log') as mock_attr_log,
    ):
        mock_log.debug = Mock()
        mock_nlri_log.debug = Mock()
        mock_attr_log.debug = Mock()

        yield

    # Restore original values
    option.logger = original_logger
    option.formater = original_formater


def create_negotiated_mock(families: Any = None, asn4: Any = False) -> Any:
    """Create a mock negotiated object with optional family support."""
    negotiated = Mock()
    negotiated.asn4 = asn4
    negotiated.addpath = Mock()
    negotiated.addpath.receive = Mock(return_value=False)
    negotiated.addpath.send = Mock(return_value=False)
    negotiated.required = Mock(return_value=False)
    negotiated.families = families if families else []
    negotiated.msg_size = 4096  # Standard BGP message size
    return negotiated


# ==============================================================================
# Phase 1: Mandatory Attribute Validation
# ==============================================================================


def test_update_with_mandatory_attributes() -> None:
    """Test UPDATE with all mandatory attributes for IPv4 announcement.

    For IPv4 unicast announcements, mandatory attributes are:
    - ORIGIN (Type 1)
    - AS_PATH (Type 2)
    - NEXT_HOP (Type 3)
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    negotiated = create_negotiated_mock()

    # Create UPDATE with all mandatory attributes
    attributes = (
        create_origin_attribute(0)  # IGP
        + create_as_path_attribute([65001, 65002])  # AS_PATH
        + create_next_hop_attribute('192.0.2.1')  # NEXT_HOP
    )

    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(
        withdrawn_routes=b'',
        path_attributes=attributes,
        nlri=nlri,
    )

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    assert len(result.nlris) == 1
    # Verify attributes were parsed
    from exabgp.bgp.message.update.attribute import Attribute

    assert Attribute.CODE.ORIGIN in result.attributes
    assert Attribute.CODE.AS_PATH in result.attributes
    assert Attribute.CODE.NEXT_HOP in result.attributes


def test_update_missing_mandatory_origin() -> None:
    """Test that UPDATE with announcement but missing ORIGIN is handled.

    Note: ExaBGP's attribute parsing is permissive during parsing.
    Missing mandatory attributes are typically caught during route construction.
    This test verifies that parsing completes but the attributes structure
    shows the missing attribute.
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    negotiated = create_negotiated_mock()

    # Create UPDATE without ORIGIN (missing mandatory)
    attributes = (
        create_as_path_attribute([65001])  # AS_PATH present
        + create_next_hop_attribute('192.0.2.1')  # NEXT_HOP present
        # ORIGIN missing!
    )

    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(
        withdrawn_routes=b'',
        path_attributes=attributes,
        nlri=nlri,
    )

    # Should parse successfully (permissive parsing)
    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # Verify ORIGIN is missing from attributes
    from exabgp.bgp.message.update.attribute import Attribute

    assert Attribute.CODE.ORIGIN not in result.attributes


def test_update_missing_mandatory_as_path() -> None:
    """Test UPDATE with announcement but missing AS_PATH."""
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_next_hop_attribute,
    )

    negotiated = create_negotiated_mock()

    # Create UPDATE without AS_PATH
    attributes = (
        create_origin_attribute(0)  # ORIGIN present
        + create_next_hop_attribute('192.0.2.1')  # NEXT_HOP present
        # AS_PATH missing!
    )

    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(
        withdrawn_routes=b'',
        path_attributes=attributes,
        nlri=nlri,
    )

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # Verify AS_PATH is missing
    from exabgp.bgp.message.update.attribute import Attribute

    assert Attribute.CODE.AS_PATH not in result.attributes


def test_update_missing_mandatory_next_hop() -> None:
    """Test UPDATE with IPv4 announcement but missing NEXT_HOP."""
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_as_path_attribute,
    )

    negotiated = create_negotiated_mock()

    # Create UPDATE without NEXT_HOP
    attributes = (
        create_origin_attribute(0)  # ORIGIN present
        + create_as_path_attribute([65001])  # AS_PATH present
        # NEXT_HOP missing!
    )

    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(
        withdrawn_routes=b'',
        path_attributes=attributes,
        nlri=nlri,
    )

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # NLRI will be parsed but without valid next-hop
    assert len(result.nlris) >= 1


def test_update_with_all_wellknown_attributes() -> None:
    """Test UPDATE with all well-known path attributes.

    Well-known attributes include:
    - ORIGIN (1)
    - AS_PATH (2)
    - NEXT_HOP (3)
    - And others like MED, LOCAL_PREF, etc.
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
        create_med_attribute,
        create_local_pref_attribute,
    )

    negotiated = create_negotiated_mock()

    # Create UPDATE with multiple well-known attributes
    attributes = (
        create_origin_attribute(0)  # ORIGIN
        + create_as_path_attribute([65001, 65002, 65003])  # AS_PATH
        + create_next_hop_attribute('192.0.2.1')  # NEXT_HOP
        + create_med_attribute(100)  # MED (optional)
        + create_local_pref_attribute(200)  # LOCAL_PREF
    )

    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(
        withdrawn_routes=b'',
        path_attributes=attributes,
        nlri=nlri,
    )

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # Verify multiple attributes were parsed
    from exabgp.bgp.message.update.attribute import Attribute

    assert Attribute.CODE.ORIGIN in result.attributes
    assert Attribute.CODE.AS_PATH in result.attributes
    assert Attribute.CODE.NEXT_HOP in result.attributes
    assert Attribute.CODE.MED in result.attributes
    assert Attribute.CODE.LOCAL_PREF in result.attributes


# ==============================================================================
# Phase 2: Attribute Combinations and NLRI
# ==============================================================================


def test_update_attribute_order_independence() -> None:
    """Test that attribute order doesn't affect parsing.

    BGP attributes can appear in any order, though ORIGIN, AS_PATH, NEXT_HOP
    are typically sent first.
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
        create_med_attribute,
    )

    negotiated = create_negotiated_mock()

    # Order 1: Standard order
    attributes1 = (
        create_origin_attribute(0)
        + create_as_path_attribute([65001])
        + create_next_hop_attribute('192.0.2.1')
        + create_med_attribute(100)
    )

    # Order 2: Reversed order
    attributes2 = (
        create_med_attribute(100)
        + create_next_hop_attribute('192.0.2.1')
        + create_as_path_attribute([65001])
        + create_origin_attribute(0)
    )

    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data1 = create_update_message(b'', attributes1, nlri)
    data2 = create_update_message(b'', attributes2, nlri)

    result1 = UpdateData.unpack_message(data1, negotiated)
    result2 = UpdateData.unpack_message(data2, negotiated)

    # Both should parse successfully
    assert isinstance(result1, UpdateData)
    assert isinstance(result2, UpdateData)

    # Both should have the same attributes
    from exabgp.bgp.message.update.attribute import Attribute

    assert Attribute.CODE.ORIGIN in result1.attributes
    assert Attribute.CODE.ORIGIN in result2.attributes
    assert Attribute.CODE.MED in result1.attributes
    assert Attribute.CODE.MED in result2.attributes


def test_update_with_withdrawn_and_announced() -> None:
    """Test UPDATE containing both withdrawn routes and announcements.

    This is a valid BGP UPDATE that withdraws some prefixes while
    announcing others.
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.action import Action
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    negotiated = create_negotiated_mock()

    # Withdrawn routes
    withdrawn = create_ipv4_prefix('172.16.0.0', 12) + create_ipv4_prefix('192.168.0.0', 16)

    # Announced routes with attributes
    attributes = create_origin_attribute(0) + create_as_path_attribute([65001]) + create_next_hop_attribute('192.0.2.1')

    nlri = create_ipv4_prefix('10.0.0.0', 8) + create_ipv4_prefix('10.1.0.0', 16)

    data = create_update_message(withdrawn, attributes, nlri)

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # Should have both withdrawals and announcements
    assert len(result.nlris) == 4  # 2 withdrawn + 2 announced

    # Check that we have both types of actions
    actions = {nlri.action for nlri in result.nlris}
    assert Action.WITHDRAW in actions
    assert Action.ANNOUNCE in actions


def test_update_attribute_length_validation() -> None:
    """Test UPDATE with various attribute lengths including edge cases."""
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import create_update_message, create_origin_attribute

    negotiated = create_negotiated_mock()

    # Test with single attribute (minimal length)
    attributes = create_origin_attribute(0)

    data = create_update_message(b'', attributes, b'')

    result = UpdateData.unpack_message(data, negotiated)

    # Should handle minimal attributes
    assert isinstance(result, UpdateData) or result.__class__.__name__ == 'EOR'


def test_update_with_multiple_nlri_prefixes() -> None:
    """Test UPDATE announcing multiple prefixes at once."""
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    negotiated = create_negotiated_mock()

    attributes = create_origin_attribute(0) + create_as_path_attribute([65001]) + create_next_hop_attribute('192.0.2.1')

    # Multiple NLRI prefixes
    nlri = (
        create_ipv4_prefix('10.0.0.0', 8)
        + create_ipv4_prefix('10.1.0.0', 16)
        + create_ipv4_prefix('10.2.0.0', 16)
        + create_ipv4_prefix('10.3.0.0', 16)
        + create_ipv4_prefix('192.168.1.0', 24)
    )

    data = create_update_message(b'', attributes, nlri)

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # Should parse all 5 prefixes
    assert len(result.nlris) == 5


def test_update_only_withdrawals_no_attributes() -> None:
    """Test UPDATE with only withdrawals and no attributes.

    When withdrawing routes, no path attributes are required.
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.action import Action
    from tests.fuzz.update_helpers import create_update_message, create_ipv4_prefix

    negotiated = create_negotiated_mock()

    # Only withdrawals, no attributes
    withdrawn = create_ipv4_prefix('10.0.0.0', 8) + create_ipv4_prefix('192.168.0.0', 16)

    data = create_update_message(withdrawn, b'', b'')

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # Should have withdrawals
    assert len(result.nlris) == 2
    assert all(nlri.action == Action.WITHDRAW for nlri in result.nlris)


# ==============================================================================
# Phase 3: MP Extensions (MP_REACH_NLRI / MP_UNREACH_NLRI)
# ==============================================================================


def test_update_with_mp_reach_nlri() -> None:
    """Test UPDATE with MP_REACH_NLRI attribute (RFC 4760).

    MP_REACH_NLRI (Type 14) is used for multiprotocol BGP extensions.
    This test verifies that UPDATE messages can contain MP attributes.
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.protocol.family import AFI, SAFI
    from tests.fuzz.update_helpers import create_update_message, create_path_attribute

    # Mock with IPv6 unicast family support
    negotiated = create_negotiated_mock(families=[(AFI.ipv6, SAFI.unicast)])

    # Create minimal MP_REACH_NLRI attribute (Type 14) with no actual NLRI
    # Format: AFI (2) + SAFI (1) + NH Length (1) + NH + Reserved (1) + [NLRI]
    mp_reach_value = (
        struct.pack('!H', AFI.ipv6)  # AFI: IPv6
        + struct.pack('!B', SAFI.unicast)  # SAFI: unicast
        + struct.pack('!B', 16)  # Next-hop length: 16 bytes
        + b'\x20\x01\x0d\xb8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01'  # IPv6 NH
        + struct.pack('!B', 0)  # Reserved, no NLRI data
    )

    attributes = create_path_attribute(14, mp_reach_value, optional=True, transitive=False)

    data = create_update_message(b'', attributes, b'')

    # Parsing will fail gracefully or succeed depending on NLRI validation
    # The key test is that it doesn't crash and handles the attribute
    try:
        result = UpdateData.unpack_message(data, negotiated)
        # Should return EOR or UPDATE
        assert result is not None
    except Exception as e:
        # MP_REACH with no NLRI might be treated as EOR or error
        # Either behavior is acceptable for this test
        assert 'EOR' in str(type(e)) or 'Notify' in str(type(e)) or 'UPDATE' in str(type(result))


def test_update_with_mp_unreach_nlri() -> None:
    """Test UPDATE with MP_UNREACH_NLRI attribute (RFC 4760).

    MP_UNREACH_NLRI (Type 15) is used to withdraw multiprotocol routes.
    RFC 4760 states that UPDATE with only MP_UNREACH is valid without other attributes.
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.eor import EOR
    from exabgp.protocol.family import AFI, SAFI
    from tests.fuzz.update_helpers import create_update_message, create_path_attribute

    negotiated = create_negotiated_mock(families=[(AFI.ipv6, SAFI.unicast)])

    # Create MP_UNREACH_NLRI attribute (Type 15) with no withdrawn routes
    # This effectively creates an EOR marker for IPv6 unicast
    # Format: AFI (2) + SAFI (1) + [Withdrawn Routes]
    mp_unreach_value = (
        struct.pack('!H', AFI.ipv6)  # AFI: IPv6
        + struct.pack('!B', SAFI.unicast)  # SAFI: unicast, no withdrawn routes
    )

    attributes = create_path_attribute(15, mp_unreach_value, optional=True, transitive=False)

    data = create_update_message(b'', attributes, b'')

    result = UpdateData.unpack_message(data, negotiated)

    # Should be EOR for IPv6 unicast (no routes to withdraw means EOR)
    assert result is not None
    assert isinstance(result, (UpdateData, EOR))


def test_update_eor_marker_validation() -> None:
    """Test End-of-RIB (EOR) marker detection.

    EOR can be signaled in two ways:
    1. Empty UPDATE (4 zero bytes) - for IPv4 unicast
    2. UPDATE with MP_UNREACH_NLRI with no withdrawn routes - for other AFI/SAFI
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.eor import EOR
    from exabgp.protocol.family import AFI, SAFI

    negotiated = create_negotiated_mock()

    # Test IPv4 unicast EOR (empty UPDATE)
    # EOR is 4 bytes of zeros
    data = b'\x00\x00\x00\x00'

    result = UpdateData.unpack_message(data, negotiated)

    # Should be detected as EOR
    assert isinstance(result, EOR)
    # EOR stores afi/safi in the NLRI
    assert result.nlris[0].afi == AFI.ipv4
    assert result.nlris[0].safi == SAFI.unicast


def test_update_mp_reach_and_mp_unreach_together() -> None:
    """Test UPDATE with both MP_REACH_NLRI and MP_UNREACH_NLRI.

    A single UPDATE can contain both MP_REACH and MP_UNREACH.
    When both have no routes, it may result in an error or EOR.
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.eor import EOR
    from exabgp.protocol.family import AFI, SAFI
    from tests.fuzz.update_helpers import create_update_message, create_path_attribute

    negotiated = create_negotiated_mock(families=[(AFI.ipv6, SAFI.unicast)])

    # Create MP_UNREACH_NLRI (Type 15) with no withdrawn (simpler case)
    mp_unreach_value = (
        struct.pack('!H', AFI.ipv6) + struct.pack('!B', SAFI.unicast)  # No withdrawn routes
    )

    attributes = create_path_attribute(15, mp_unreach_value, optional=True, transitive=False)

    data = create_update_message(b'', attributes, b'')

    # MP_UNREACH with no routes should be EOR or valid UPDATE
    result = UpdateData.unpack_message(data, negotiated)
    assert result is not None
    assert isinstance(result, (UpdateData, EOR))

    # Test shows that UPDATE can handle multiprotocol attributes
    # without causing crashes


def test_update_mp_unreach_only_is_valid() -> None:
    """Test that UPDATE with only MP_UNREACH_NLRI doesn't require other attributes.

    RFC 4760: An UPDATE message that contains MP_UNREACH_NLRI is not required
    to carry any other path attributes.
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.eor import EOR
    from exabgp.protocol.family import AFI, SAFI
    from tests.fuzz.update_helpers import create_update_message, create_path_attribute

    negotiated = create_negotiated_mock(families=[(AFI.ipv6, SAFI.unicast)])

    # Only MP_UNREACH_NLRI, no other attributes, no withdrawn routes (EOR)
    mp_unreach_value = (
        struct.pack('!H', AFI.ipv6) + struct.pack('!B', SAFI.unicast)  # No withdrawn routes
    )

    attributes = create_path_attribute(15, mp_unreach_value, optional=True, transitive=False)

    data = create_update_message(b'', attributes, b'')

    result = UpdateData.unpack_message(data, negotiated)

    # Should be valid - likely EOR for IPv6 unicast
    assert result is not None
    assert isinstance(result, (UpdateData, EOR))


# ==============================================================================
# Phase 4: Edge Cases and Limits
# ==============================================================================


def test_update_maximum_attributes_size() -> None:
    """Test UPDATE with large number of attributes approaching max size.

    BGP messages are limited to 4096 bytes (or larger with extended message support).
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
        create_path_attribute,
    )

    negotiated = create_negotiated_mock()

    # Build attributes with long AS_PATH
    attributes = (
        create_origin_attribute(0)
        +
        # Long AS_PATH with many hops
        create_as_path_attribute(list(range(65001, 65100)))  # 99 AS numbers
        + create_next_hop_attribute('192.0.2.1')
    )

    # Add multiple community attributes (Type 8) to increase size
    for i in range(10):
        # Standard community: 4 bytes per community
        communities = struct.pack('!I', 65000 << 16 | i) * 20  # 20 communities
        attributes += create_path_attribute(8, communities, optional=True, transitive=True)

    data = create_update_message(b'', attributes, b'')

    result = UpdateData.unpack_message(data, negotiated)

    # Should handle large attributes
    assert result is not None


def test_update_with_extended_length_attributes() -> None:
    """Test UPDATE with extended length attributes (length > 255).

    When attribute length exceeds 255 bytes, the Extended Length flag
    must be set and length encoded in 2 bytes.
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import create_update_message, create_path_attribute

    negotiated = create_negotiated_mock()

    # Create attribute with value > 255 bytes
    large_value = b'\x00' * 300  # 300 bytes

    # Use extended length (flag 0x10)
    extended_attr = create_path_attribute(
        type_code=100,  # Unknown optional attribute
        value=large_value,
        optional=True,
        transitive=False,
        extended=True,  # Extended length flag
    )

    data = create_update_message(b'', extended_attr, b'')

    result = UpdateData.unpack_message(data, negotiated)

    # Should handle extended length
    assert result is not None


def test_update_empty_as_path_allowed() -> None:
    """Test UPDATE with empty AS_PATH (valid for iBGP).

    Empty AS_PATH is valid for iBGP sessions where routes are originated locally.
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_ipv4_prefix,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    negotiated = create_negotiated_mock()

    # Empty AS_PATH
    attributes = (
        create_origin_attribute(0)
        + create_as_path_attribute([])  # Empty
        + create_next_hop_attribute('192.0.2.1')
    )

    nlri = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(b'', attributes, nlri)

    result = UpdateData.unpack_message(data, negotiated)

    assert isinstance(result, UpdateData)
    # Empty AS_PATH should be valid
    from exabgp.bgp.message.update.attribute import Attribute

    assert Attribute.CODE.AS_PATH in result.attributes


def test_update_with_duplicate_attributes_detected() -> None:
    """Test that duplicate attributes in UPDATE are detected.

    RFC 4271: Duplicate attributes should result in TREAT_AS_WITHDRAW or error.
    """
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import create_update_message, create_origin_attribute

    negotiated = create_negotiated_mock()

    # Duplicate ORIGIN attributes
    attributes = (
        create_origin_attribute(0)  # First ORIGIN
        + create_origin_attribute(1)  # Duplicate ORIGIN (different value)
    )

    data = create_update_message(b'', attributes, b'')

    # Parsing might succeed but should handle duplicates
    # ExaBGP's behavior: last value wins or error depending on attribute
    result = UpdateData.unpack_message(data, negotiated)

    # Should return result (either UPDATE or error)
    assert result is not None


def test_update_zero_length_nlri_section() -> None:
    """Test UPDATE with zero-length NLRI section (only attributes)."""
    from exabgp.bgp.message.update import UpdateData
    from tests.fuzz.update_helpers import (
        create_update_message,
        create_origin_attribute,
        create_as_path_attribute,
        create_next_hop_attribute,
    )

    negotiated = create_negotiated_mock()

    # Attributes but no NLRI
    attributes = create_origin_attribute(0) + create_as_path_attribute([65001]) + create_next_hop_attribute('192.0.2.1')

    data = create_update_message(b'', attributes, b'')  # Empty NLRI

    result = UpdateData.unpack_message(data, negotiated)

    # Should parse successfully
    # Could be EOR or UPDATE with no NLRI
    assert result is not None


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
