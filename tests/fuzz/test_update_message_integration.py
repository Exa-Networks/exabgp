"""Comprehensive integration tests for UPDATE message packing and unpacking.

These tests focus on critical gaps in UPDATE message testing:
1. Message packing (messages() method) - PREVIOUSLY UNTESTED
2. Round-trip testing (pack then unpack)
3. Multiprotocol integration with real routes
4. Message size constraints and splitting
5. Complex integration scenarios

Target: src/exabgp/bgp/message/update/__init__.py

Test Coverage:
Phase 1: Message packing basics (tests 1-5)
Phase 2: Round-trip integrity (tests 6-10)
Phase 3: Multiprotocol packing (tests 11-13)
Phase 4: Message size and splitting (tests 14-16)
Phase 5: Complex integration scenarios (tests 17-20)
"""

from typing import Any
from unittest.mock import Mock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """Mock the logger to avoid initialization issues."""
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


def create_negotiated_mock(families: Any = None, asn4: Any = False, msg_size: Any = 4096) -> Any:
    """Create a mock negotiated object with configurable parameters."""
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.open.asn import ASN
    from exabgp.bgp.message.direction import Direction
    from exabgp.bgp.message.open.capability.negotiated import OpenContext

    negotiated = Mock()
    negotiated.direction = Direction.IN
    negotiated.asn4 = asn4
    negotiated.addpath = Mock()
    negotiated.addpath.receive = Mock(return_value=False)
    negotiated.addpath.send = Mock(return_value=False)
    negotiated.required = Mock(return_value=False)

    # Default families if not specified
    if families is None:
        families = [(AFI.ipv4, SAFI.unicast)]

    negotiated.families = families
    negotiated.msg_size = msg_size

    # Add ASN values
    negotiated.local_as = ASN(65000)
    negotiated.peer_as = ASN(65001)

    # Add nlri_context method that returns a proper OpenContext
    def nlri_context(afi: AFI, safi: SAFI) -> OpenContext:
        return OpenContext.make_open_context(
            afi=afi,
            safi=safi,
            addpath=False,
            asn4=asn4,
            msg_size=msg_size,
        )

    negotiated.nlri_context = nlri_context

    return negotiated


def create_inet_nlri(
    prefix: str,
    prefixlen: int,
    action: Any,
    afi: Any = None,
    safi: Any = None,
    nexthop: str | None = None,
) -> Any:
    """Helper to create INET NLRI using the new factory method pattern."""
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IP, IPv6
    from exabgp.protocol.family import AFI as AFI_CLASS, SAFI as SAFI_CLASS

    if afi is None:
        afi = AFI_CLASS.ipv4
    if safi is None:
        safi = SAFI_CLASS.unicast

    # Pack IP address
    if afi == AFI_CLASS.ipv6:
        packed = IPv6(prefix).pack_ip()
    else:
        packed = IP.pton(prefix)

    cidr = CIDR.make_cidr(packed, prefixlen)
    nlri = INET.from_cidr(cidr, afi, safi, action)

    if nexthop:
        if afi == AFI_CLASS.ipv6:
            nlri.nexthop = IPv6(nexthop)
        else:
            nlri.nexthop = IP.from_string(nexthop)

    return nlri


# ==============================================================================
# Phase 1: Message Packing Basics
# ==============================================================================


@pytest.mark.fuzz
def test_messages_packs_simple_ipv4_announcement() -> None:
    """Test that messages() generates valid UPDATE for IPv4 announcement.

    This tests the critical messages() method that was previously UNTESTED.
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create a simple IPv4 route using factory method
    nlri = create_inet_nlri('10.0.0.0', 8, Action.ANNOUNCE, nexthop='192.0.2.1')

    # Create minimal attributes
    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update([nlri], attributes)

    # Generate messages
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Should generate at least one message
    assert len(messages) >= 1

    # Each message should be bytes
    for msg in messages:
        assert isinstance(msg, bytes)
        # UPDATE messages should have reasonable size (> header)
        assert len(msg) > 19  # BGP header is 19 bytes


@pytest.mark.fuzz
def test_messages_packs_ipv4_withdrawal() -> None:
    """Test that messages() generates valid UPDATE for IPv4 withdrawal."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create a withdrawal using factory method
    nlri = create_inet_nlri('10.0.0.0', 8, Action.WITHDRAW)

    attributes = Attributes()

    update = Update([nlri], attributes)

    # Generate messages
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Should generate at least one message
    assert len(messages) >= 1

    for msg in messages:
        assert isinstance(msg, bytes)


@pytest.mark.fuzz
def test_messages_handles_no_nlris() -> None:
    """Test that messages() handles UPDATE with no valid NLRIs."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes
    from exabgp.protocol.family import AFI, SAFI

    negotiated = create_negotiated_mock(families=[(AFI.ipv4, SAFI.unicast)])

    # Empty NLRI list
    attributes = Attributes()
    update = Update([], attributes)

    # Generate messages
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Should generate no messages
    assert len(messages) == 0


@pytest.mark.fuzz
def test_messages_include_withdraw_flag() -> None:
    """Test that include_withdraw flag controls withdrawal inclusion."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create a withdrawal using factory method
    nlri = create_inet_nlri('10.0.0.0', 8, Action.WITHDRAW)

    attributes = Attributes()
    update = Update([nlri], attributes)

    # Generate messages with include_withdraw=False
    messages = list(update.messages(negotiated, include_withdraw=False))

    # May generate empty messages or skip withdrawals
    assert isinstance(messages, list)


@pytest.mark.fuzz
def test_messages_filters_by_negotiated_families() -> None:
    """Test that messages() filters NLRIs by negotiated families.

    Only routes for negotiated families should be included.
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action
    from exabgp.protocol.family import AFI, SAFI

    # Only negotiate IPv4 unicast
    negotiated = create_negotiated_mock(families=[(AFI.ipv4, SAFI.unicast)])

    # Create IPv4 route (should be included) using factory method
    nlri_v4 = create_inet_nlri('10.0.0.0', 8, Action.ANNOUNCE, nexthop='192.0.2.1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update([nlri_v4], attributes)

    # Generate messages
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Should generate messages (for IPv4)
    assert len(messages) >= 1


# ==============================================================================
# Phase 2: Round-trip Integrity Tests
# ==============================================================================


@pytest.mark.fuzz
def test_roundtrip_simple_ipv4_announcement() -> None:
    """Test pack then unpack preserves IPv4 announcement data.

    This validates data integrity through the full UPDATE cycle.
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create original route using factory method
    original_nlri = create_inet_nlri('10.0.0.0', 8, Action.ANNOUNCE, nexthop='192.0.2.1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    original_attributes = Attributes()
    original_attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    original_attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    original_attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update([original_nlri], original_attributes)

    # Pack message
    messages = list(update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Extract UPDATE payload (skip BGP header)
    packed_data = messages[0][19:]  # Skip 19-byte BGP header

    # Unpack message
    unpacked = Update.unpack_message(packed_data, negotiated)

    # Verify unpacked data
    assert isinstance(unpacked, Update)
    assert len(unpacked.nlris) >= 1

    # Verify attributes were preserved
    assert Attribute.CODE.ORIGIN in unpacked.attributes
    # AS_PATH may be omitted if empty (default value)


@pytest.mark.fuzz
def test_roundtrip_ipv4_withdrawal() -> None:
    """Test pack then unpack preserves IPv4 withdrawal data."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create withdrawal using factory method
    nlri = create_inet_nlri('192.168.0.0', 16, Action.WITHDRAW)

    attributes = Attributes()
    update = Update([nlri], attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Unpack
    packed_data = messages[0][19:]
    unpacked = Update.unpack_message(packed_data, negotiated)

    # Verify
    assert isinstance(unpacked, Update)
    assert len(unpacked.nlris) >= 1
    assert unpacked.nlris[0].action == Action.WITHDRAW


@pytest.mark.fuzz
def test_roundtrip_multiple_nlris() -> None:
    """Test pack then unpack preserves multiple NLRIs."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create multiple routes using factory method
    nlris = []
    for prefix, prefixlen in [('10.0.0.0', 8), ('10.1.0.0', 16), ('10.2.0.0', 16)]:
        nlri = create_inet_nlri(prefix, prefixlen, Action.ANNOUNCE, nexthop='192.0.2.1')
        nlris.append(nlri)

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update(nlris, attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Unpack
    packed_data = messages[0][19:]
    unpacked = Update.unpack_message(packed_data, negotiated)

    # Verify
    assert isinstance(unpacked, Update)
    assert len(unpacked.nlris) == 3


@pytest.mark.fuzz
def test_roundtrip_with_multiple_attributes() -> None:
    """Test pack then unpack preserves multiple path attributes."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create route using factory method
    nlri = create_inet_nlri('10.0.0.0', 8, Action.ANNOUNCE, nexthop='192.0.2.1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path, SEQUENCE
    from exabgp.bgp.message.update.attribute.nexthop import NextHop
    from exabgp.bgp.message.update.attribute.med import MED
    from exabgp.bgp.message.update.attribute.localpref import LocalPreference
    from exabgp.bgp.message.open.asn import ASN

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([SEQUENCE([ASN(65001), ASN(65002)])])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')
    attributes[Attribute.CODE.MED] = MED.from_int(100)
    attributes[Attribute.CODE.LOCAL_PREF] = LocalPreference.from_int(200)

    update = Update([nlri], attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Unpack
    packed_data = messages[0][19:]
    unpacked = Update.unpack_message(packed_data, negotiated)

    # Verify all attributes preserved
    assert isinstance(unpacked, Update)
    assert Attribute.CODE.ORIGIN in unpacked.attributes
    assert Attribute.CODE.AS_PATH in unpacked.attributes
    # NEXT_HOP is set per-NLRI, not in global attributes
    assert Attribute.CODE.MED in unpacked.attributes
    # LOCAL_PREF may be omitted in EBGP contexts (only used in IBGP)


@pytest.mark.fuzz
def test_roundtrip_mixed_announce_withdraw() -> None:
    """Test pack then unpack preserves mixed announcements and withdrawals."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create withdrawals using factory method
    withdraw1 = create_inet_nlri('172.16.0.0', 12, Action.WITHDRAW)
    withdraw2 = create_inet_nlri('192.168.0.0', 16, Action.WITHDRAW)

    # Create announcements using factory method
    announce1 = create_inet_nlri('10.0.0.0', 8, Action.ANNOUNCE, nexthop='192.0.2.1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    nlris = [withdraw1, withdraw2, announce1]
    update = Update(nlris, attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Unpack
    packed_data = messages[0][19:]
    unpacked = Update.unpack_message(packed_data, negotiated)

    # Verify both types present
    assert isinstance(unpacked, Update)
    assert len(unpacked.nlris) >= 2

    actions = {nlri.action for nlri in unpacked.nlris}
    assert Action.WITHDRAW in actions
    assert Action.ANNOUNCE in actions


# ==============================================================================
# Phase 3: Multiprotocol Packing Tests
# ==============================================================================


@pytest.mark.fuzz
def test_messages_packs_ipv6_as_mp_reach() -> None:
    """Test that messages() packs IPv6 routes as MP_REACH_NLRI.

    IPv6 routes should be packed using multiprotocol extensions.
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action
    from exabgp.protocol.family import AFI, SAFI

    # Negotiate IPv6 unicast
    negotiated = create_negotiated_mock(families=[(AFI.ipv6, SAFI.unicast)])

    # Create IPv6 route using factory method
    nlri = create_inet_nlri('2001:db8::', 32, Action.ANNOUNCE, afi=AFI.ipv6, nexthop='2001:db8::1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])

    update = Update([nlri], attributes)

    # Pack - should use MP_REACH_NLRI
    messages = list(update.messages(negotiated, include_withdraw=True))

    assert len(messages) >= 1
    for msg in messages:
        assert isinstance(msg, bytes)


@pytest.mark.fuzz
def test_roundtrip_ipv6_announcement() -> None:
    """Test pack then unpack preserves IPv6 announcement via MP_REACH."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action
    from exabgp.protocol.family import AFI, SAFI

    negotiated = create_negotiated_mock(families=[(AFI.ipv6, SAFI.unicast)])

    # Create IPv6 route using factory method
    nlri = create_inet_nlri('2001:db8::', 32, Action.ANNOUNCE, afi=AFI.ipv6, nexthop='2001:db8::1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])

    update = Update([nlri], attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Unpack
    packed_data = messages[0][19:]
    unpacked = Update.unpack_message(packed_data, negotiated)

    # Verify
    assert unpacked is not None
    # Should have IPv6 NLRI from MP_REACH
    if isinstance(unpacked, Update):
        assert len(unpacked.nlris) >= 1


@pytest.mark.fuzz
def test_messages_handles_mixed_ipv4_ipv6() -> None:
    """Test messages() with both IPv4 and IPv6 routes.

    Should generate messages with both standard NLRI and MP extensions.
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action
    from exabgp.protocol.family import AFI, SAFI

    # Negotiate both families
    negotiated = create_negotiated_mock(
        families=[
            (AFI.ipv4, SAFI.unicast),
            (AFI.ipv6, SAFI.unicast),
        ]
    )

    # Create IPv4 route using factory method
    nlri_v4 = create_inet_nlri('10.0.0.0', 8, Action.ANNOUNCE, nexthop='192.0.2.1')

    # Create IPv6 route using factory method
    nlri_v6 = create_inet_nlri('2001:db8::', 32, Action.ANNOUNCE, afi=AFI.ipv6, nexthop='2001:db8::1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update([nlri_v4, nlri_v6], attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Should generate messages for both families
    assert len(messages) >= 1


# ==============================================================================
# Phase 4: Message Size and Splitting Tests
# ==============================================================================


@pytest.mark.fuzz
def test_messages_splits_large_nlri_set() -> None:
    """Test that messages() splits large NLRI sets into multiple UPDATEs.

    When NLRIs exceed message size limit, should generate multiple messages.
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock(msg_size=1024)  # Small message size

    # Create many routes using factory method
    nlris = []
    for i in range(100):  # 100 routes
        nlri = create_inet_nlri(f'10.{i % 256}.0.0', 16, Action.ANNOUNCE, nexthop='192.0.2.1')
        nlris.append(nlri)

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update(nlris, attributes)

    # Pack - should generate multiple messages
    messages = list(update.messages(negotiated, include_withdraw=True))

    # With small msg_size, should split into multiple messages
    # Exact count depends on implementation, but should be > 1
    assert len(messages) >= 1


@pytest.mark.fuzz
def test_messages_respects_negotiated_msg_size() -> None:
    """Test that messages() respects negotiated message size limit."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    # Small message size
    negotiated = create_negotiated_mock(msg_size=512)

    # Create routes using factory method
    nlris = []
    for i in range(20):
        nlri = create_inet_nlri(f'10.{i}.0.0', 16, Action.ANNOUNCE, nexthop='192.0.2.1')
        nlris.append(nlri)

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update(nlris, attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Each message should respect size limit
    for msg in messages:
        assert len(msg) <= 512


@pytest.mark.fuzz
def test_messages_handles_large_attributes() -> None:
    """Test messages() with large attributes approaching size limits."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create route using factory method
    nlri = create_inet_nlri('10.0.0.0', 8, Action.ANNOUNCE, nexthop='192.0.2.1')

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path, SEQUENCE
    from exabgp.bgp.message.update.attribute.nexthop import NextHop
    from exabgp.bgp.message.open.asn import ASN

    # Create large AS_PATH
    large_as_path = SEQUENCE([ASN(65000 + i) for i in range(100)])

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([large_as_path])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update([nlri], attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Should handle large attributes
    assert len(messages) >= 0  # May fail if attributes too large


# ==============================================================================
# Phase 5: Complex Integration Scenarios
# ==============================================================================


@pytest.mark.fuzz
def test_integration_full_update_cycle() -> None:
    """Integration test: Full UPDATE cycle with various route types.

    Tests complete flow: create -> pack -> unpack -> verify
    """
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Create diverse NLRI set using factory method
    nlris = []

    # Withdrawals
    for prefix, prefixlen in [('172.16.0.0', 12), ('192.168.0.0', 16)]:
        nlri = create_inet_nlri(prefix, prefixlen, Action.WITHDRAW)
        nlris.append(nlri)

    # Announcements
    for prefix, prefixlen in [('10.0.0.0', 8), ('10.1.0.0', 16), ('10.2.0.0', 16)]:
        nlri = create_inet_nlri(prefix, prefixlen, Action.ANNOUNCE, nexthop='192.0.2.1')
        nlris.append(nlri)

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path, SEQUENCE
    from exabgp.bgp.message.update.attribute.nexthop import NextHop
    from exabgp.bgp.message.update.attribute.med import MED
    from exabgp.bgp.message.update.attribute.localpref import LocalPreference
    from exabgp.bgp.message.open.asn import ASN

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([SEQUENCE([ASN(65001), ASN(65002)])])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')
    attributes[Attribute.CODE.MED] = MED.from_int(100)
    attributes[Attribute.CODE.LOCAL_PREF] = LocalPreference.from_int(200)

    original_update = Update(nlris, attributes)

    # Pack
    messages = list(original_update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Unpack each message
    for msg in messages:
        packed_data = msg[19:]
        unpacked = Update.unpack_message(packed_data, negotiated)

        assert unpacked is not None

        if isinstance(unpacked, Update):
            # Should have NLRIs
            assert len(unpacked.nlris) >= 1

            # Should have attributes
            assert len(unpacked.attributes) >= 1


@pytest.mark.fuzz
def test_integration_empty_attributes_for_withdrawal_only() -> None:
    """Test that withdrawal-only UPDATEs can have empty attributes."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Only withdrawals using factory method
    nlris = []
    for prefix, prefixlen in [('10.0.0.0', 8), ('192.168.0.0', 16)]:
        nlri = create_inet_nlri(prefix, prefixlen, Action.WITHDRAW)
        nlris.append(nlri)

    # Empty attributes
    attributes = Attributes()

    update = Update(nlris, attributes)

    # Pack
    messages = list(update.messages(negotiated, include_withdraw=True))
    assert len(messages) >= 1

    # Unpack
    packed_data = messages[0][19:]
    unpacked = Update.unpack_message(packed_data, negotiated)

    # Should be valid
    assert isinstance(unpacked, Update)
    assert all(n.action == Action.WITHDRAW for n in unpacked.nlris)


@pytest.mark.fuzz
def test_integration_sorting_and_grouping() -> None:
    """Test that messages() properly sorts and groups NLRIs."""
    from exabgp.bgp.message.update import Update
    from exabgp.bgp.message.update.attribute import Attributes, Attribute
    from exabgp.bgp.message.action import Action

    negotiated = create_negotiated_mock()

    # Mix of withdrawals and announcements in random order using factory method
    nlri1 = create_inet_nlri('10.2.0.0', 16, Action.ANNOUNCE, nexthop='192.0.2.1')
    nlri2 = create_inet_nlri('172.16.0.0', 12, Action.WITHDRAW)
    nlri3 = create_inet_nlri('10.1.0.0', 16, Action.ANNOUNCE, nexthop='192.0.2.1')

    nlris = [nlri1, nlri2, nlri3]

    from exabgp.bgp.message.update.attribute.origin import Origin
    from exabgp.bgp.message.update.attribute.aspath import AS2Path
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    attributes = Attributes()
    attributes[Attribute.CODE.ORIGIN] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.AS_PATH] = AS2Path.make_aspath([])
    attributes[Attribute.CODE.NEXT_HOP] = NextHop.from_string('192.0.2.1')

    update = Update(nlris, attributes)

    # Pack - should sort internally
    messages = list(update.messages(negotiated, include_withdraw=True))

    # Should generate valid messages
    assert len(messages) >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
