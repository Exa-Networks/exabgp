#!/usr/bin/env python3
# encoding: utf-8
"""test_ip_link_local.py

Tests for IP address link-local detection.

Tests the is_link_local() method on IP, IPv4, and IPv6 classes
as required by the Link-Local Next Hop Capability (draft-ietf-idr-linklocal-capability).

Created for ExaBGP testing framework
License: 3-clause BSD
"""

from exabgp.protocol.ip import IPv4, IPv6


# ==============================================================================
# IPv4 Link-Local Tests
# ==============================================================================


def test_ipv4_is_link_local_always_false() -> None:
    """IPv4 link-local not supported by link-local nexthop capability.

    The capability only applies to IPv6 addresses.
    """
    # Standard IPv4 addresses
    assert IPv4(IPv4.pton('10.0.0.1')).is_link_local() is False
    assert IPv4(IPv4.pton('192.168.1.1')).is_link_local() is False
    assert IPv4(IPv4.pton('172.16.0.1')).is_link_local() is False

    # Even IPv4 link-local range (169.254.x.x) returns False
    # because capability doesn't apply to IPv4
    assert IPv4(IPv4.pton('169.254.0.1')).is_link_local() is False
    assert IPv4(IPv4.pton('169.254.255.255')).is_link_local() is False


# ==============================================================================
# IPv6 Link-Local Tests (fe80::/10)
# ==============================================================================


def test_ipv6_link_local_fe80() -> None:
    """Test standard fe80:: link-local addresses."""
    assert IPv6(IPv6.pton('fe80::1')).is_link_local() is True
    assert IPv6(IPv6.pton('fe80::dead:beef')).is_link_local() is True
    assert IPv6(IPv6.pton('fe80::1:2:3:4')).is_link_local() is True
    assert IPv6(IPv6.pton('fe80:0:0:0:1:2:3:4')).is_link_local() is True


def test_ipv6_link_local_fe80_to_febf() -> None:
    """Test fe80::/10 range (fe80:: to febf::).

    Link-local is fe80::/10, meaning first 10 bits are 1111111010.
    - First byte: 0xfe (11111110)
    - Second byte high 2 bits: 10
    So valid range is fe80:: through febf::
    """
    # Lower bound
    assert IPv6(IPv6.pton('fe80::')).is_link_local() is True
    assert IPv6(IPv6.pton('fe80::ffff:ffff:ffff:ffff')).is_link_local() is True

    # Upper bound (febf:ffff:...)
    assert IPv6(IPv6.pton('febf::1')).is_link_local() is True
    assert IPv6(IPv6.pton('febf:ffff:ffff:ffff:ffff:ffff:ffff:ffff')).is_link_local() is True

    # Middle of range
    assert IPv6(IPv6.pton('fe90::1')).is_link_local() is True
    assert IPv6(IPv6.pton('fea0::1')).is_link_local() is True
    assert IPv6(IPv6.pton('feb0::1')).is_link_local() is True


def test_ipv6_not_link_local_global() -> None:
    """Test global unicast addresses are not link-local."""
    assert IPv6(IPv6.pton('2001:db8::1')).is_link_local() is False
    assert IPv6(IPv6.pton('2001:db8:1234:5678::1')).is_link_local() is False
    assert IPv6(IPv6.pton('2607:f8b0:4004:800::200e')).is_link_local() is False


def test_ipv6_not_link_local_loopback() -> None:
    """Test loopback is not link-local."""
    assert IPv6(IPv6.pton('::1')).is_link_local() is False


def test_ipv6_not_link_local_unspecified() -> None:
    """Test unspecified address is not link-local."""
    assert IPv6(IPv6.pton('::')).is_link_local() is False


def test_ipv6_not_link_local_multicast() -> None:
    """Test multicast addresses are not link-local."""
    assert IPv6(IPv6.pton('ff02::1')).is_link_local() is False
    assert IPv6(IPv6.pton('ff00::')).is_link_local() is False


def test_ipv6_not_link_local_fec0() -> None:
    """Test site-local (deprecated fec0::/10) is not link-local."""
    assert IPv6(IPv6.pton('fec0::1')).is_link_local() is False
    assert IPv6(IPv6.pton('fed0::1')).is_link_local() is False
    assert IPv6(IPv6.pton('fee0::1')).is_link_local() is False
    assert IPv6(IPv6.pton('fef0::1')).is_link_local() is False


def test_ipv6_not_link_local_fc00() -> None:
    """Test unique local (fc00::/7) is not link-local."""
    assert IPv6(IPv6.pton('fc00::1')).is_link_local() is False
    assert IPv6(IPv6.pton('fd00::1')).is_link_local() is False


def test_ipv6_not_link_local_boundary() -> None:
    """Test addresses just outside fe80::/10 range."""
    # Just below fe80::
    assert IPv6(IPv6.pton('fe7f::1')).is_link_local() is False

    # Just above febf::
    assert IPv6(IPv6.pton('fec0::1')).is_link_local() is False


# ==============================================================================
# Summary
# ==============================================================================
# Total tests: 11
#
# Coverage:
# - IPv4 always returns False (1 test)
# - IPv6 valid link-local detection (2 tests)
# - IPv6 non-link-local addresses (7 tests)
# ==============================================================================
