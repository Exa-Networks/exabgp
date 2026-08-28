"""test_ip_from_string.py

IP.from_string() is the single way to build an address from its string form.
It decides the address family once, and a concrete subclass demands its own
family rather than letting the string choose.

License: 3-clause BSD
"""

from __future__ import annotations

import pytest

from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP, IPRange, IPv4, IPv6


# ==============================================================================
# The family the caller asked for
# ==============================================================================


def test_ip_accepts_either_family_and_returns_the_matching_class() -> None:
    assert isinstance(IP.from_string('192.0.2.1'), IPv4)
    assert isinstance(IP.from_string('2001:db8::1'), IPv6)


def test_a_concrete_class_returns_its_own_type() -> None:
    assert type(IPv4.from_string('192.0.2.1')) is IPv4
    assert type(IPv6.from_string('2001:db8::1')) is IPv6


def test_ipv4_refuses_an_ipv6_string() -> None:
    with pytest.raises(ValueError, match='expected an ipv4 address'):
        IPv4.from_string('2001:db8::1')


def test_ipv6_refuses_an_ipv4_string() -> None:
    with pytest.raises(ValueError, match='expected an ipv6 address'):
        IPv6.from_string('192.0.2.1')


def test_an_unrecognisable_string_is_a_value_error() -> None:
    with pytest.raises(ValueError):
        IP.from_string('not-an-address')


# ==============================================================================
# The bytes and the family agree
# ==============================================================================


@pytest.mark.parametrize(
    'string, afi, size',
    [
        ('192.0.2.1', AFI.ipv4, 4),
        ('2001:db8::1', AFI.ipv6, 16),
        ('fe80::1', AFI.ipv6, 16),
    ],
)
def test_packed_form_matches_the_family(string: str, afi: AFI, size: int) -> None:
    ip = IP.from_string(string)

    assert ip.afi == afi
    assert len(ip.pack_ip()) == size
    assert ip.top() == string


# ==============================================================================
# Ranges carry a mask, so they get their own constructor
# ==============================================================================


def test_make_range_builds_a_range() -> None:
    prefix = IPRange.make_range('10.0.0.0', 24)

    assert prefix.top() == '10.0.0.0'
    assert int(prefix.mask) == 24
    assert repr(prefix) == '10.0.0.0/24'


def test_make_range_works_for_ipv6() -> None:
    prefix = IPRange.make_range('2001:db8::', 32)

    assert repr(prefix) == '2001:db8::/32'


def test_a_range_can_not_be_built_without_a_mask() -> None:
    with pytest.raises(NotImplementedError, match='make_range'):
        IPRange.from_string('10.0.0.0')
