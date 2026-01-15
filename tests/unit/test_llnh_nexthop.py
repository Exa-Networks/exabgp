#!/usr/bin/env python3
# encoding: utf-8
"""test_llnh_nexthop.py

Tests for Link-Local Next Hop (LLNH) Capability nexthop encoding.

Tests the _encode_nexthop method in MPNLRICollection per
draft-ietf-idr-linklocal-capability requirements:
- 16-byte nexthop: link-local only (when LLNH negotiated) or global only
- 32-byte nexthop: global + link-local

Created for ExaBGP testing framework
License: 3-clause BSD
"""

from unittest.mock import Mock

from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IPv6, IP


# ==============================================================================
# Test Fixtures
# ==============================================================================


def create_mock_negotiated(
    linklocal_nexthop: bool = False,
    link_local_address: IP | None = None,
    link_local_prefer: bool = False,
    is_multihop: bool = False,
) -> Mock:
    """Create a mock Negotiated object for testing."""
    negotiated = Mock()
    negotiated.linklocal_nexthop = linklocal_nexthop
    negotiated.link_local_address = Mock(return_value=link_local_address)
    negotiated.link_local_prefer = Mock(return_value=link_local_prefer)
    negotiated.is_multihop = Mock(return_value=is_multihop)
    return negotiated


def create_collection() -> MPNLRICollection:
    """Create an MPNLRICollection for testing."""
    return MPNLRICollection([], {}, AFI.ipv6, SAFI.unicast)


# ==============================================================================
# IPv6 Global Nexthop Tests (without LLNH)
# ==============================================================================


def test_global_nexthop_without_llnh() -> None:
    """Global IPv6 nexthop without LLNH returns 16 bytes."""
    collection = create_collection()
    negotiated = create_mock_negotiated(linklocal_nexthop=False)

    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    assert len(result) == 16
    assert result == global_ip.pack_ip()


def test_global_nexthop_with_llnh_no_lla() -> None:
    """Global IPv6 nexthop with LLNH but no link-local address returns 16 bytes."""
    collection = create_collection()
    negotiated = create_mock_negotiated(
        linklocal_nexthop=True,
        link_local_address=None,
    )

    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    assert len(result) == 16
    assert result == global_ip.pack_ip()


# ==============================================================================
# IPv6 Link-Local Nexthop Tests (with LLNH)
# ==============================================================================


def test_link_local_nexthop_with_llnh() -> None:
    """Link-local nexthop with LLNH negotiated returns 16 bytes."""
    collection = create_collection()
    negotiated = create_mock_negotiated(linklocal_nexthop=True)

    lla_ip = IPv6(IPv6.pton('fe80::1'))
    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(lla_ip, family_key, negotiated)

    assert len(result) == 16
    assert result == lla_ip.pack_ip()
    assert lla_ip.is_link_local() is True


def test_link_local_nexthop_without_llnh() -> None:
    """Link-local nexthop without LLNH still returns 16 bytes.

    The sending side should not send link-local-only without LLNH,
    but the encoding method itself doesn't block it.
    """
    collection = create_collection()
    negotiated = create_mock_negotiated(linklocal_nexthop=False)

    lla_ip = IPv6(IPv6.pton('fe80::1'))
    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(lla_ip, family_key, negotiated)

    # Without LLNH, we just pack as-is
    assert len(result) == 16


# ==============================================================================
# 32-byte Nexthop Tests (Global + Link-Local)
# ==============================================================================


def test_global_with_lla_default_order() -> None:
    """Global nexthop with LLA available returns 32 bytes (global first)."""
    collection = create_collection()
    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    lla_ip = IPv6(IPv6.pton('fe80::1'))

    negotiated = create_mock_negotiated(
        linklocal_nexthop=True,
        link_local_address=lla_ip,
        link_local_prefer=False,
    )

    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    # 32 bytes: global (16) + link-local (16)
    assert len(result) == 32
    assert result[:16] == global_ip.pack_ip()
    assert result[16:] == lla_ip.pack_ip()


def test_global_with_lla_prefer_link_local() -> None:
    """Global nexthop with LLA preferred still uses standard wire order.

    Wire format is ALWAYS Global + Link-local per RFC.
    The prefer config affects receiver's forwarding decision, not encoding.
    """
    collection = create_collection()
    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    lla_ip = IPv6(IPv6.pton('fe80::1'))

    negotiated = create_mock_negotiated(
        linklocal_nexthop=True,
        link_local_address=lla_ip,
        link_local_prefer=True,  # Doesn't affect wire order
    )

    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    # 32 bytes: global (16) + link-local (16) - always this order
    assert len(result) == 32
    assert result[:16] == global_ip.pack_ip()
    assert result[16:] == lla_ip.pack_ip()


# ==============================================================================
# IPv4 Tests (LLNH doesn't apply)
# ==============================================================================


def test_ipv4_nexthop_unaffected() -> None:
    """IPv4 nexthop is unaffected by LLNH capability."""
    collection = MPNLRICollection([], {}, AFI.ipv4, SAFI.unicast)
    negotiated = create_mock_negotiated(linklocal_nexthop=True)

    from exabgp.protocol.ip import IPv4

    ipv4_addr = IPv4(IPv4.pton('192.168.1.1'))
    family_key = (AFI.ipv4, SAFI.unicast)

    result = collection._encode_nexthop(ipv4_addr, family_key, negotiated)

    assert len(result) == 4
    assert result == ipv4_addr.pack_ip()


# ==============================================================================
# No Nexthop Tests
# ==============================================================================


def test_no_nexthop_returns_empty() -> None:
    """IP.NoNextHop returns empty bytes."""
    collection = create_collection()
    negotiated = create_mock_negotiated()

    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(IP.NoNextHop, family_key, negotiated)

    assert result == b''


# ==============================================================================
# Multihop Tests (TTL > 1 excludes link-local)
# ==============================================================================


def test_multihop_excludes_link_local() -> None:
    """Multihop session (TTL > 1) excludes link-local from 32-byte nexthop.

    RFC: Link-local addresses only valid for directly connected peers.
    """
    collection = create_collection()
    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    lla_ip = IPv6(IPv6.pton('fe80::1'))

    negotiated = create_mock_negotiated(
        linklocal_nexthop=True,
        link_local_address=lla_ip,
        link_local_prefer=False,
        is_multihop=True,  # TTL > 1
    )

    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    # Should be 16 bytes (global only), not 32 (global + LLA)
    assert len(result) == 16
    assert result == global_ip.pack_ip()


def test_directly_connected_includes_link_local() -> None:
    """Directly connected session includes link-local in 32-byte nexthop."""
    collection = create_collection()
    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    lla_ip = IPv6(IPv6.pton('fe80::1'))

    negotiated = create_mock_negotiated(
        linklocal_nexthop=True,
        link_local_address=lla_ip,
        link_local_prefer=False,
        is_multihop=False,  # Directly connected
    )

    family_key = (AFI.ipv6, SAFI.unicast)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    # Should be 32 bytes (global + LLA)
    assert len(result) == 32


# ==============================================================================
# VPN Family Tests (with RD)
# ==============================================================================


def test_vpnv6_nexthop_with_rd() -> None:
    """VPNv6 nexthop includes 8-byte RD prefix."""
    collection = MPNLRICollection([], {}, AFI.ipv6, SAFI.mpls_vpn)
    negotiated = create_mock_negotiated(linklocal_nexthop=False)

    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    family_key = (AFI.ipv6, SAFI.mpls_vpn)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    # 24 bytes: RD (8) + IPv6 (16)
    assert len(result) == 24
    assert result[:8] == bytes([0] * 8)  # Zero RD
    assert result[8:] == global_ip.pack_ip()


def test_vpnv6_nexthop_with_lla() -> None:
    """VPNv6 with global+LLA includes RD and both addresses."""
    collection = MPNLRICollection([], {}, AFI.ipv6, SAFI.mpls_vpn)
    global_ip = IPv6(IPv6.pton('2001:db8::1'))
    lla_ip = IPv6(IPv6.pton('fe80::1'))

    negotiated = create_mock_negotiated(
        linklocal_nexthop=True,
        link_local_address=lla_ip,
        link_local_prefer=False,
    )

    family_key = (AFI.ipv6, SAFI.mpls_vpn)

    result = collection._encode_nexthop(global_ip, family_key, negotiated)

    # 40 bytes: RD (8) + Global (16) + Link-Local (16)
    assert len(result) == 40
    assert result[:8] == bytes([0] * 8)  # Zero RD
    assert result[8:24] == global_ip.pack_ip()
    assert result[24:] == lla_ip.pack_ip()


# ==============================================================================
# Summary
# ==============================================================================
# Total tests: 11
#
# Coverage:
# - Global nexthop without LLNH (1 test)
# - Global nexthop with LLNH but no LLA (1 test)
# - Link-local nexthop with/without LLNH (2 tests)
# - 32-byte nexthop encoding order (2 tests)
# - IPv4 unaffected (1 test)
# - No nexthop (1 test)
# - VPN family with RD (2 tests)
# ==============================================================================
