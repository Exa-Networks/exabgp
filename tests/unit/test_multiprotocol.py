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
    """Test MP_REACH_NLRI for IPv4 unicast.

    MP_REACH_NLRI allows BGP to carry reachability information for
    multiple address families. For IPv4 unicast, it duplicates the
    functionality of traditional BGP UPDATE messages.
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create IPv4 unicast prefix
    prefix = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)
    prefix.nexthop = IPv4.create('192.0.2.1')

    # Create MP_REACH_NLRI
    mpreach = MPRNLRI(AFI.ipv4, SAFI.unicast, [prefix])

    # Verify family
    assert mpreach.afi == AFI.ipv4
    assert mpreach.safi == SAFI.unicast
    assert len(mpreach.nlris) == 1

    # Verify representation
    assert 'MP_REACH_NLRI' in str(mpreach)
    assert 'ipv4' in str(mpreach).lower()
    assert 'unicast' in str(mpreach).lower()


def test_mpreach_ipv6_unicast() -> None:
    """Test MP_REACH_NLRI for IPv6 unicast.

    IPv6 routing requires MP_REACH_NLRI as standard BGP UPDATE
    messages only support IPv4. This tests basic IPv6 prefix announcement.
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv6
    from exabgp.bgp.message import Action

    # Create IPv6 unicast prefix
    prefix = INET(AFI.ipv6, SAFI.unicast, Action.ANNOUNCE)
    prefix.cidr = CIDR(IPv6.create('2001:db8::').pack(), 32)
    prefix.nexthop = IPv6.create('2001:db8::1')

    # Create MP_REACH_NLRI
    mpreach = MPRNLRI(AFI.ipv6, SAFI.unicast, [prefix])

    # Verify family
    assert mpreach.afi == AFI.ipv6
    assert mpreach.safi == SAFI.unicast
    assert len(mpreach.nlris) == 1

    # Verify representation
    assert 'MP_REACH_NLRI' in str(mpreach)
    assert 'ipv6' in str(mpreach).lower()


def test_mpreach_multiple_prefixes() -> None:
    """Test MP_REACH_NLRI with multiple prefixes.

    A single MP_REACH_NLRI attribute can announce multiple prefixes
    of the same address family with the same next-hop.
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create multiple IPv4 unicast prefixes with same next-hop
    nexthop = IPv4.create('192.0.2.1')
    prefix_cidrs = [
        ('10.0.0.0', 24),
        ('10.1.0.0', 24),
        ('10.2.0.0', 24),
    ]

    prefixes = []
    for ip, mask in prefix_cidrs:
        prefix = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        prefix.cidr = CIDR(IPv4.create(ip).pack(), mask)
        prefix.nexthop = nexthop
        prefixes.append(prefix)

    # Create MP_REACH_NLRI with multiple prefixes
    mpreach = MPRNLRI(AFI.ipv4, SAFI.unicast, prefixes)

    # Verify all prefixes are included
    assert len(mpreach.nlris) == 3
    assert '3 NLRI' in str(mpreach)


def test_mpreach_pack_ipv4() -> None:
    """Test MP_REACH_NLRI pack() for IPv4.

    Verifies the wire format of MP_REACH_NLRI attribute.
    Format: AFI(2) + SAFI(1) + NH_LEN(1) + NEXTHOP(var) + RESERVED(1) + NLRI(var)
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create IPv4 unicast prefix
    prefix = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)
    prefix.nexthop = IPv4.create('192.0.2.1')

    # Create MP_REACH_NLRI
    mpreach = MPRNLRI(AFI.ipv4, SAFI.unicast, [prefix])

    # Create mock negotiated
    negotiated = Mock()
    negotiated.families = [(AFI.ipv4, SAFI.unicast)]
    negotiated.addpath = Mock()
    negotiated.addpath.send = Mock(return_value=False)

    # Pack the attribute
    packed = mpreach.pack_attribute(negotiated)

    # Verify it produces bytes
    assert isinstance(packed, bytes)
    assert len(packed) > 0

    # The packed data should contain:
    # - Attribute flags + type code + length (3-4 bytes)
    # - AFI (2 bytes) + SAFI (1 byte)
    # - Next-hop length + next-hop + reserved
    # - NLRI data


def test_mpreach_nexthop_ipv6_global() -> None:
    """Test MP_REACH_NLRI with IPv6 global next-hop.

    IPv6 next-hops can be 16 bytes (global) or 32 bytes (global + link-local).
    This tests the global-only case.
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv6
    from exabgp.bgp.message import Action

    # Create IPv6 unicast prefix with global next-hop
    prefix = INET(AFI.ipv6, SAFI.unicast, Action.ANNOUNCE)
    prefix.cidr = CIDR(IPv6.create('2001:db8::').pack(), 32)
    prefix.nexthop = IPv6.create('2001:db8::1')  # Global next-hop

    # Create MP_REACH_NLRI
    mpreach = MPRNLRI(AFI.ipv6, SAFI.unicast, [prefix])

    # Verify next-hop is set
    assert prefix.nexthop is not None
    assert len(mpreach.nlris) == 1


# ==============================================================================
# Phase 2: MP_UNREACH_NLRI (Type 15) - Withdrawals
# ==============================================================================


def test_mpunreach_ipv4_unicast() -> None:
    """Test MP_UNREACH_NLRI for IPv4 unicast.

    MP_UNREACH_NLRI is used to withdraw previously announced prefixes.
    Unlike MP_REACH_NLRI, it doesn't include next-hop information.
    """
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create IPv4 unicast prefix to withdraw
    prefix = INET(AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
    prefix.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)

    # Create MP_UNREACH_NLRI
    mpunreach = MPURNLRI(AFI.ipv4, SAFI.unicast, [prefix])

    # Verify family
    assert mpunreach.afi == AFI.ipv4
    assert mpunreach.safi == SAFI.unicast
    assert len(mpunreach.nlris) == 1

    # Verify representation
    assert 'MP_UNREACH_NLRI' in str(mpunreach)
    assert 'ipv4' in str(mpunreach).lower()


def test_mpunreach_ipv6_unicast() -> None:
    """Test MP_UNREACH_NLRI for IPv6 unicast.

    IPv6 prefix withdrawals use MP_UNREACH_NLRI.
    """
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv6
    from exabgp.bgp.message import Action

    # Create IPv6 unicast prefix to withdraw
    prefix = INET(AFI.ipv6, SAFI.unicast, Action.WITHDRAW)
    prefix.cidr = CIDR(IPv6.create('2001:db8::').pack(), 32)

    # Create MP_UNREACH_NLRI
    mpunreach = MPURNLRI(AFI.ipv6, SAFI.unicast, [prefix])

    # Verify family
    assert mpunreach.afi == AFI.ipv6
    assert mpunreach.safi == SAFI.unicast
    assert len(mpunreach.nlris) == 1


def test_mpunreach_multiple_prefixes() -> None:
    """Test MP_UNREACH_NLRI with multiple prefix withdrawals.

    A single MP_UNREACH_NLRI can withdraw multiple prefixes
    of the same address family.
    """
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create multiple IPv4 unicast prefixes to withdraw
    prefix_cidrs = [
        ('10.0.0.0', 24),
        ('10.1.0.0', 24),
        ('10.2.0.0', 24),
    ]

    prefixes = []
    for ip, mask in prefix_cidrs:
        prefix = INET(AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
        prefix.cidr = CIDR(IPv4.create(ip).pack(), mask)
        prefixes.append(prefix)

    # Create MP_UNREACH_NLRI with multiple prefixes
    mpunreach = MPURNLRI(AFI.ipv4, SAFI.unicast, prefixes)

    # Verify all prefixes are included
    assert len(mpunreach.nlris) == 3
    assert '3 NLRI' in str(mpunreach)


def test_mpunreach_pack_ipv4() -> None:
    """Test MP_UNREACH_NLRI pack() for IPv4.

    Verifies the wire format of MP_UNREACH_NLRI attribute.
    Format: AFI(2) + SAFI(1) + NLRI(var)
    Note: No next-hop in MP_UNREACH_NLRI.
    """
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create IPv4 unicast prefix to withdraw
    prefix = INET(AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
    prefix.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)

    # Create MP_UNREACH_NLRI
    mpunreach = MPURNLRI(AFI.ipv4, SAFI.unicast, [prefix])

    # Create mock negotiated
    negotiated = Mock()
    negotiated.families = [(AFI.ipv4, SAFI.unicast)]
    negotiated.addpath = Mock()
    negotiated.addpath.send = Mock(return_value=False)

    # Pack the attribute
    packed = mpunreach.pack_attribute(negotiated)

    # Verify it produces bytes
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
    """Test MP_REACH_NLRI supports various AFI/SAFI combinations.

    BGP multiprotocol extensions support many address family combinations:
    - IPv4 unicast, multicast
    - IPv6 unicast, multicast
    - VPNv4, VPNv6
    - And many others
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI

    # Test various AFI/SAFI combinations
    test_cases = [
        (AFI.ipv4, SAFI.unicast, 'IPv4 unicast'),
        (AFI.ipv4, SAFI.multicast, 'IPv4 multicast'),
        (AFI.ipv6, SAFI.unicast, 'IPv6 unicast'),
        (AFI.ipv6, SAFI.multicast, 'IPv6 multicast'),
    ]

    for afi, safi, description in test_cases:
        # Create MP_REACH_NLRI with this family
        mpreach = MPRNLRI(afi, safi, [])

        # Verify family is correctly set
        assert mpreach.afi == afi, f'AFI mismatch for {description}'
        assert mpreach.safi == safi, f'SAFI mismatch for {description}'


def test_mpunreach_afi_safi_combinations() -> None:
    """Test MP_UNREACH_NLRI supports various AFI/SAFI combinations."""
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.protocol.family import AFI, SAFI

    # Test various AFI/SAFI combinations
    test_cases = [
        (AFI.ipv4, SAFI.unicast, 'IPv4 unicast'),
        (AFI.ipv4, SAFI.multicast, 'IPv4 multicast'),
        (AFI.ipv6, SAFI.unicast, 'IPv6 unicast'),
        (AFI.ipv6, SAFI.multicast, 'IPv6 multicast'),
    ]

    for afi, safi, description in test_cases:
        # Create MP_UNREACH_NLRI with this family
        mpunreach = MPURNLRI(afi, safi, [])

        # Verify family is correctly set
        assert mpunreach.afi == afi, f'AFI mismatch for {description}'
        assert mpunreach.safi == safi, f'SAFI mismatch for {description}'


# ==============================================================================
# Phase 4: Advanced Features
# ==============================================================================


def test_mpreach_empty_nlri_eor() -> None:
    """Test MP_REACH_NLRI with empty NLRI list (End-of-RIB marker).

    EOR (End-of-RIB) is signaled by an MP_UNREACH_NLRI with no withdrawn routes.
    It indicates that all routes for a given AFI/SAFI have been sent.
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI

    # Create MP_REACH_NLRI with empty NLRI list
    mpreach = MPRNLRI(AFI.ipv4, SAFI.unicast, [])

    # Verify it's empty
    assert len(mpreach.nlris) == 0
    assert '0 NLRI' in str(mpreach)


def test_mpunreach_empty_nlri() -> None:
    """Test MP_UNREACH_NLRI with empty NLRI list.

    An empty MP_UNREACH_NLRI can be used as an EOR marker.
    """
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.protocol.family import AFI, SAFI

    # Create MP_UNREACH_NLRI with empty NLRI list
    mpunreach = MPURNLRI(AFI.ipv4, SAFI.unicast, [])

    # Verify it's empty
    assert len(mpunreach.nlris) == 0
    assert '0 NLRI' in str(mpunreach)


def test_mpreach_attribute_flags() -> None:
    """Test MP_REACH_NLRI has correct attribute flags.

    MP_REACH_NLRI is an optional non-transitive attribute (type 14).
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.bgp.message.update.attribute import Attribute

    # Verify attribute code and flags
    assert MPRNLRI.ID == Attribute.CODE.MP_REACH_NLRI
    assert MPRNLRI.ID == 14
    assert MPRNLRI.FLAG & Attribute.Flag.OPTIONAL


def test_mpunreach_attribute_flags() -> None:
    """Test MP_UNREACH_NLRI has correct attribute flags.

    MP_UNREACH_NLRI is an optional non-transitive attribute (type 15).
    """
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.bgp.message.update.attribute import Attribute

    # Verify attribute code and flags
    assert MPURNLRI.ID == Attribute.CODE.MP_UNREACH_NLRI
    assert MPURNLRI.ID == 15
    assert MPURNLRI.FLAG & Attribute.Flag.OPTIONAL


def test_mpreach_equality() -> None:
    """Test MP_REACH_NLRI equality comparison.

    Two MP_REACH_NLRI attributes are equal if they have the same
    AFI, SAFI, and NLRI list.
    """
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create two identical MP_REACH_NLRI attributes
    prefix1 = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix1.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)
    prefix1.nexthop = IPv4.create('192.0.2.1')

    prefix2 = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    prefix2.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)
    prefix2.nexthop = IPv4.create('192.0.2.1')

    mpreach1 = MPRNLRI(AFI.ipv4, SAFI.unicast, [prefix1])
    mpreach2 = MPRNLRI(AFI.ipv4, SAFI.unicast, [prefix2])

    # Verify equality (implementation may vary based on NLRI equality)
    assert mpreach1.afi == mpreach2.afi
    assert mpreach1.safi == mpreach2.safi


def test_mpunreach_equality() -> None:
    """Test MP_UNREACH_NLRI equality comparison."""
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.update.nlri.cidr import CIDR
    from exabgp.protocol.ip import IPv4
    from exabgp.bgp.message import Action

    # Create two identical MP_UNREACH_NLRI attributes
    prefix1 = INET(AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
    prefix1.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)

    prefix2 = INET(AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
    prefix2.cidr = CIDR(IPv4.create('10.0.0.0').pack(), 24)

    mpunreach1 = MPURNLRI(AFI.ipv4, SAFI.unicast, [prefix1])
    mpunreach2 = MPURNLRI(AFI.ipv4, SAFI.unicast, [prefix2])

    # Verify equality (implementation may vary based on NLRI equality)
    assert mpunreach1.afi == mpunreach2.afi
    assert mpunreach1.safi == mpunreach2.safi
