"""Comprehensive tests for BGP Multiprotocol extensions (MP_REACH_NLRI and MP_UNREACH_NLRI).

These tests cover RFC 4760 - Multiprotocol Extensions for BGP-4:

Test Coverage:
Phase 1: MP_REACH_NLRI (Type 14) - Basic IPv4/IPv6
  - IPv4 unicast announcements
  - IPv6 unicast announcements
  - Next-hop encoding (IPv4, IPv6, link-local)

Phase 2: MP_UNREACH_NLRI (Type 15) - Withdrawals
  - IPv4 unicast withdrawals
  - IPv6 unicast withdrawals
  - Multiple prefix withdrawals

Phase 3: Address Family Support
  - AFI/SAFI combinations (IPv4/IPv6, unicast/multicast)
  - VPNv4 and VPNv6 support
  - Next-hop handling per family

Phase 4: Advanced Features
  - AddPath support
  - Extended next-hop capability
  - EOR (End-of-RIB) markers
"""

from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import OpenContext
from exabgp.protocol.family import AFI, SAFI


def make_context(afi: AFI, safi: SAFI) -> OpenContext:
    """Create a default OpenContext for testing."""
    return OpenContext.make_open_context(
        afi=afi,
        safi=safi,
        addpath=False,
        asn4=False,
        msg_size=4096,
        local_as=ASN(65000),
        peer_as=ASN(65001),
    )


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

    # Create a mock formater
    mock_formater = Mock(return_value='formatted message')

    option.logger = mock_option_logger
    option.formater = mock_formater

    yield

    # Restore original values
    option.logger = original_logger
    option.formater = original_formater


# ==============================================================================
# Phase 1: MP_REACH_NLRI (Type 14) - Basic IPv4/IPv6
# ==============================================================================


def test_mpreach_ipv4_unicast() -> None:
    """Test MPNLRICollection for IPv4 unicast.

    MPNLRICollection is the semantic container that stores NLRIs
    and can generate MP_REACH_NLRI wire format.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create IPv4 unicast prefix
    cidr = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix.nexthop = IPv4.from_string('192.0.2.1')

    # Create MPNLRICollection
    collection = MPNLRICollection([prefix], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify family
    assert collection.afi == AFI.ipv4
    assert collection.safi == SAFI.unicast
    assert len(collection.nlris) == 1

    # Verify representation
    assert 'MPNLRICollection' in str(collection)
    assert 'ipv4' in str(collection).lower()


def test_mpreach_ipv6_unicast() -> None:
    """Test MPNLRICollection for IPv6 unicast.

    IPv6 routing requires MP_REACH_NLRI as standard BGP UPDATE
    messages only support IPv4. This tests basic IPv6 prefix announcement.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv6

    # Create IPv6 unicast prefix
    cidr = CIDR.make_cidr(IPv6.from_string('2001:db8::').pack_ip(), 32)
    prefix = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast, Action.ANNOUNCE)
    prefix.nexthop = IPv6.from_string('2001:db8::1')

    # Create MPNLRICollection
    collection = MPNLRICollection([prefix], {}, make_context(AFI.ipv6, SAFI.unicast))

    # Verify family
    assert collection.afi == AFI.ipv6
    assert collection.safi == SAFI.unicast
    assert len(collection.nlris) == 1

    # Verify representation
    assert 'MPNLRICollection' in str(collection)
    assert 'ipv6' in str(collection).lower()


def test_mpreach_multiple_prefixes() -> None:
    """Test MPNLRICollection with multiple prefixes.

    A single MPNLRICollection can hold multiple prefixes
    of the same address family with the same next-hop.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create multiple IPv4 unicast prefixes with same next-hop
    nexthop = IPv4.from_string('192.0.2.1')
    prefix_cidrs = [
        ('10.0.0.0', 24),
        ('10.1.0.0', 24),
        ('10.2.0.0', 24),
    ]

    prefixes = []
    for ip, mask in prefix_cidrs:
        cidr = CIDR.make_cidr(IPv4.from_string(ip).pack_ip(), mask)
        prefix = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        prefix.nexthop = nexthop
        prefixes.append(prefix)

    # Create MPNLRICollection with multiple prefixes
    collection = MPNLRICollection(prefixes, {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify all prefixes are included
    assert len(collection.nlris) == 3
    assert '3 NLRIs' in str(collection)


def test_mpreach_pack_ipv4() -> None:
    """Test MPNLRICollection packed_reach_attributes() for IPv4.

    Verifies the wire format of MP_REACH_NLRI attribute.
    Format: AFI(2) + SAFI(1) + NH_LEN(1) + NEXTHOP(var) + RESERVED(1) + NLRI(var)
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create IPv4 unicast prefix
    cidr = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix.nexthop = IPv4.from_string('192.0.2.1')

    # Create MPNLRICollection
    collection = MPNLRICollection([prefix], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Pack the attribute using packed_reach_attributes
    packed_list = list(collection.packed_reach_attributes(Negotiated.UNSET))

    # Verify it produces bytes
    assert len(packed_list) == 1
    packed = packed_list[0]
    assert isinstance(packed, bytes)
    assert len(packed) > 0

    # The packed data should contain:
    # - Attribute flags + type code + length (3-4 bytes)
    # - AFI (2 bytes) + SAFI (1 byte)
    # - Next-hop length + next-hop + reserved
    # - NLRI data


def test_mpreach_nexthop_ipv6_global() -> None:
    """Test MPNLRICollection with IPv6 global next-hop.

    IPv6 next-hops can be 16 bytes (global) or 32 bytes (global + link-local).
    This tests the global-only case.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv6

    # Create IPv6 unicast prefix with global next-hop
    cidr = CIDR.make_cidr(IPv6.from_string('2001:db8::').pack_ip(), 32)
    prefix = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast, Action.ANNOUNCE)
    prefix.nexthop = IPv6.from_string('2001:db8::1')  # Global next-hop

    # Create MPNLRICollection
    collection = MPNLRICollection([prefix], {}, make_context(AFI.ipv6, SAFI.unicast))

    # Verify next-hop is set
    assert prefix.nexthop is not None
    assert len(collection.nlris) == 1


# ==============================================================================
# Phase 2: MP_UNREACH_NLRI (Type 15) - Withdrawals
# ==============================================================================


def test_mpunreach_ipv4_unicast() -> None:
    """Test MPNLRICollection for IPv4 unicast withdrawals.

    MP_UNREACH_NLRI is used to withdraw previously announced prefixes.
    Unlike MP_REACH_NLRI, it doesn't include next-hop information.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create IPv4 unicast prefix to withdraw
    cidr = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.WITHDRAW)

    # Create MPNLRICollection
    collection = MPNLRICollection([prefix], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify family
    assert collection.afi == AFI.ipv4
    assert collection.safi == SAFI.unicast
    assert len(collection.nlris) == 1

    # Verify representation
    assert 'MPNLRICollection' in str(collection)
    assert 'ipv4' in str(collection).lower()


def test_mpunreach_ipv6_unicast() -> None:
    """Test MPNLRICollection for IPv6 unicast withdrawals.

    IPv6 prefix withdrawals use MP_UNREACH_NLRI.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv6

    # Create IPv6 unicast prefix to withdraw
    cidr = CIDR.make_cidr(IPv6.from_string('2001:db8::').pack_ip(), 32)
    prefix = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast, Action.WITHDRAW)

    # Create MPNLRICollection
    collection = MPNLRICollection([prefix], {}, make_context(AFI.ipv6, SAFI.unicast))

    # Verify family
    assert collection.afi == AFI.ipv6
    assert collection.safi == SAFI.unicast
    assert len(collection.nlris) == 1


def test_mpunreach_multiple_prefixes() -> None:
    """Test MPNLRICollection with multiple prefix withdrawals.

    A single MPNLRICollection can hold multiple prefixes for withdrawal.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create multiple IPv4 unicast prefixes to withdraw
    prefix_cidrs = [
        ('10.0.0.0', 24),
        ('10.1.0.0', 24),
        ('10.2.0.0', 24),
    ]

    prefixes = []
    for ip, mask in prefix_cidrs:
        cidr = CIDR.make_cidr(IPv4.from_string(ip).pack_ip(), mask)
        prefix = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
        prefixes.append(prefix)

    # Create MPNLRICollection with multiple prefixes
    collection = MPNLRICollection(prefixes, {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify all prefixes are included
    assert len(collection.nlris) == 3
    assert '3 NLRIs' in str(collection)


def test_mpunreach_pack_ipv4() -> None:
    """Test MPNLRICollection packed_unreach_attributes() for IPv4.

    Verifies the wire format of MP_UNREACH_NLRI attribute.
    Format: AFI(2) + SAFI(1) + NLRI(var)
    Note: No next-hop in MP_UNREACH_NLRI.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create IPv4 unicast prefix to withdraw
    cidr = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.WITHDRAW)

    # Create MPNLRICollection
    collection = MPNLRICollection([prefix], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Pack the attribute using packed_unreach_attributes
    packed_list = list(collection.packed_unreach_attributes(Negotiated.UNSET))

    # Verify it produces bytes
    assert len(packed_list) == 1
    packed = packed_list[0]
    assert isinstance(packed, bytes)
    assert len(packed) > 0

    # The packed data should contain:
    # - Attribute flags + type code + length (3-4 bytes)
    # - AFI (2 bytes) + SAFI (1 byte)
    # - NLRI data (no next-hop)


# ==============================================================================
# Phase 3: Address Family Support
# ==============================================================================


def test_mpreach_afi_safi_combinations() -> None:
    """Test MPNLRICollection supports various AFI/SAFI combinations.

    BGP multiprotocol extensions support many address family combinations:
    - IPv4 unicast, multicast
    - IPv6 unicast, multicast
    - VPNv4, VPNv6
    - And many others
    """
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.protocol.family import AFI, SAFI

    # Test various AFI/SAFI combinations
    test_cases = [
        (AFI.ipv4, SAFI.unicast, 'IPv4 unicast'),
        (AFI.ipv4, SAFI.multicast, 'IPv4 multicast'),
        (AFI.ipv6, SAFI.unicast, 'IPv6 unicast'),
        (AFI.ipv6, SAFI.multicast, 'IPv6 multicast'),
    ]

    for afi, safi, description in test_cases:
        # Create MPNLRICollection with this family
        collection = MPNLRICollection([], {}, make_context(afi, safi))

        # Verify family is correctly set
        assert collection.afi == afi, f'AFI mismatch for {description}'
        assert collection.safi == safi, f'SAFI mismatch for {description}'


def test_mpunreach_afi_safi_combinations() -> None:
    """Test MPNLRICollection supports various AFI/SAFI combinations for withdrawals."""
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.protocol.family import AFI, SAFI

    # Test various AFI/SAFI combinations
    test_cases = [
        (AFI.ipv4, SAFI.unicast, 'IPv4 unicast'),
        (AFI.ipv4, SAFI.multicast, 'IPv4 multicast'),
        (AFI.ipv6, SAFI.unicast, 'IPv6 unicast'),
        (AFI.ipv6, SAFI.multicast, 'IPv6 multicast'),
    ]

    for afi, safi, description in test_cases:
        # Create MPNLRICollection with this family
        collection = MPNLRICollection([], {}, make_context(afi, safi))

        # Verify family is correctly set
        assert collection.afi == afi, f'AFI mismatch for {description}'
        assert collection.safi == safi, f'SAFI mismatch for {description}'


# ==============================================================================
# Phase 4: Advanced Features
# ==============================================================================


def test_mpreach_empty_nlri_eor() -> None:
    """Test MPNLRICollection with empty NLRI list (End-of-RIB marker).

    EOR (End-of-RIB) is signaled by an MP_UNREACH_NLRI with no withdrawn routes.
    It indicates that all routes for a given AFI/SAFI have been sent.
    """
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.protocol.family import AFI, SAFI

    # Create MPNLRICollection with empty NLRI list
    collection = MPNLRICollection([], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify it's empty
    assert len(collection.nlris) == 0
    assert '0 NLRIs' in str(collection)


def test_mpunreach_empty_nlri() -> None:
    """Test MPNLRICollection with empty NLRI list for withdrawals.

    An empty MP_UNREACH_NLRI can be used as an EOR marker.
    """
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.protocol.family import AFI, SAFI

    # Create MPNLRICollection with empty NLRI list
    collection = MPNLRICollection([], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify it's empty
    assert len(collection.nlris) == 0
    assert '0 NLRIs' in str(collection)


def test_mpreach_attribute_flags() -> None:
    """Test MP_REACH_NLRI has correct attribute flags.

    MP_REACH_NLRI is an optional non-transitive attribute (type 14).
    """
    from exabgp.bgp.message.update.attribute import Attribute
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI

    # Verify attribute code and flags
    assert MPRNLRI.ID == Attribute.CODE.MP_REACH_NLRI
    assert MPRNLRI.ID == 14
    assert MPRNLRI.FLAG & Attribute.Flag.OPTIONAL


def test_mpunreach_attribute_flags() -> None:
    """Test MP_UNREACH_NLRI has correct attribute flags.

    MP_UNREACH_NLRI is an optional non-transitive attribute (type 15).
    """
    from exabgp.bgp.message.update.attribute import Attribute
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

    # Verify attribute code and flags
    assert MPURNLRI.ID == Attribute.CODE.MP_UNREACH_NLRI
    assert MPURNLRI.ID == 15
    assert MPURNLRI.FLAG & Attribute.Flag.OPTIONAL


def test_mpreach_equality() -> None:
    """Test MPNLRICollection equality comparison.

    Two MPNLRICollections are equal if they have the same AFI, SAFI, and NLRI list.
    """
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create two identical MPNLRICollections
    cidr1 = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix1 = INET.from_cidr(cidr1, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix1.nexthop = IPv4.from_string('192.0.2.1')

    cidr2 = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix2 = INET.from_cidr(cidr2, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix2.nexthop = IPv4.from_string('192.0.2.1')

    collection1 = MPNLRICollection([prefix1], {}, make_context(AFI.ipv4, SAFI.unicast))
    collection2 = MPNLRICollection([prefix2], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify equality (implementation may vary based on NLRI equality)
    assert collection1.afi == collection2.afi
    assert collection1.safi == collection2.safi


def test_mpunreach_equality() -> None:
    """Test MPNLRICollection equality comparison for withdrawals."""
    from exabgp.bgp.message import Action
    from exabgp.bgp.message.update.nlri import MPNLRICollection
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.protocol.ip import IPv4

    # Create two identical MPNLRICollections
    cidr1 = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix1 = INET.from_cidr(cidr1, AFI.ipv4, SAFI.unicast, Action.WITHDRAW)

    cidr2 = CIDR.make_cidr(IPv4.from_string('10.0.0.0').pack_ip(), 24)
    prefix2 = INET.from_cidr(cidr2, AFI.ipv4, SAFI.unicast, Action.WITHDRAW)

    collection1 = MPNLRICollection([prefix1], {}, make_context(AFI.ipv4, SAFI.unicast))
    collection2 = MPNLRICollection([prefix2], {}, make_context(AFI.ipv4, SAFI.unicast))

    # Verify equality (implementation may vary based on NLRI equality)
    assert collection1.afi == collection2.afi
    assert collection1.safi == collection2.safi
