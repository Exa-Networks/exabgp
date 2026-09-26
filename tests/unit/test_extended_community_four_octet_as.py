"""A route target or route origin with a four octet AS went out as an IPv4 address.

RFC 5668 defines the Four-Octet AS Specific Extended Community, type 0x02, with the route target
as sub-type 0x02 and the route origin as sub-type 0x03: a four octet AS, then a two octet number.
The configuration parser knew two headers for `target:` and `origin:`, the two octet AS one
(0x00) and the IPv4 address one (0x01), and sent everything which was not a two octet AS to the
second. `target:4200000000:100` went on the wire as the address 250.86.234.0, and
etc/exabgp/parse-community.conf's `target:120000L:123 origin:130000:1234` as
`target:0.1.212.192:123 origin:0.1.251.208:1234`. The decoder had the right classes all along.

A dotted value is still an IPv4 address, and a trailing L still forces the four octet form for
an AS which would fit in two.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.attribute.community.extended.origin import (
    OriginASN4Number,
    OriginASNIP,
    OriginIPASN,
)
from exabgp.bgp.message.update.attribute.community.extended.rt import (
    RouteTargetASN2Number,
    RouteTargetASN4Number,
    RouteTargetIPNumber,
)
from exabgp.configuration.static.parser import _extended_community


@pytest.mark.parametrize(
    'text,klass,wire,shown',
    [
        ('target:4200000000:100', RouteTargetASN4Number, '0202FA56EA000064', 'target:4200000000:100'),
        ('target:120000L:123', RouteTargetASN4Number, '02020001D4C0007B', 'target:120000:123'),
        ('target:65001L:1', RouteTargetASN4Number, '02020000FDE90001', 'target:65001:1'),
        ('origin:130000:1234', OriginASN4Number, '02030001FBD004D2', 'origin:130000:1234'),
    ],
)
def test_a_four_octet_as_is_type_two(text, klass, wire, shown) -> None:
    """The defect: these were type 0x01, and read back as an IPv4 address."""
    community = _extended_community(text)
    assert isinstance(community, klass)
    assert bytes(community.pack_attribute(Negotiated.UNSET)).hex().upper() == wire
    assert str(community) == shown


@pytest.mark.parametrize(
    'text,klass,wire',
    [
        ('target:65001:100', RouteTargetASN2Number, '0002FDE900000064'),
        ('target:192.0.2.1:100', RouteTargetIPNumber, '0102C00002010064'),
        ('origin:65001:100', OriginASNIP, '0003FDE900000064'),
        ('origin:192.0.2.1:100', OriginIPASN, '0103C00002010064'),
    ],
)
def test_the_other_forms_are_unchanged(text, klass, wire) -> None:
    community = _extended_community(text)
    assert isinstance(community, klass)
    assert bytes(community.pack_attribute(Negotiated.UNSET)).hex().upper() == wire


@pytest.mark.parametrize('text', ['target:4200000000:65536', 'origin:4200000000:65536', 'target:4294967296:1'])
def test_a_value_too_large_for_the_four_octet_form_is_refused(text) -> None:
    with pytest.raises(ValueError, match='too large'):
        _extended_community(text)
