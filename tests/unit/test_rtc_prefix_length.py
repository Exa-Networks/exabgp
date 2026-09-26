"""An RTC prefix shorter than 96 bits was read as if it were 96, and took the next NLRI with it.

RFC 4684 section 4: "The NLRI field in the MP_REACH_NLRI and MP_UNREACH_NLRI is a prefix of 0 to
96 bits, encoded as defined in Section 4 of [5]", that is RFC 4760: a length in bits, then as
many octets as the length needs, rounded up. "Route targets can then be expressed as prefixes,
where, for instance, a prefix would encompass all route target extended communities assigned by
a given Global Administrator."

The decoder checked the length was between 32 and 96 and then always took 13 octets. A 64 bit
prefix is 9 octets on the wire, so the decoder swallowed the first four octets of the NLRI after
it and read that one from the wrong place, or refused the UPDATE as truncated when it was last.
The section has no RFC 2119 keyword, so these tests carry no rfc() marker.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.community.extended.rt import RouteTargetASN2Number
from exabgp.bgp.message.update.nlri.rtc import RTC
from exabgp.protocol.family import AFI, SAFI

ORIGIN = bytes.fromhex('0000FDE9')  # AS 65001
TARGET = bytes.fromhex('0002FDE900000064')  # target:65001:100
FULL = bytes([96]) + ORIGIN + TARGET


def negotiated() -> Negotiated:
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.IN)


def unpack(data: bytes) -> tuple[RTC, bytes]:
    nlri, left = RTC.unpack_nlri(AFI.ipv4, SAFI.rtc, data, Action.ANNOUNCE, False, negotiated())
    return nlri, bytes(left)


@pytest.mark.parametrize(
    'bits,carried',
    [
        (32, ORIGIN),  # the origin AS alone: every route target from that AS
        (40, ORIGIN + TARGET[:1]),  # a length which is not a whole number of octets
        (48, ORIGIN + TARGET[:2]),  # the route target type: every target of one Global Administrator
        (64, ORIGIN + TARGET[:4]),
        (95, ORIGIN + TARGET[:8]),
    ],
)
def test_a_short_prefix_consumes_only_its_own_octets(bits, carried) -> None:
    """The defect: the NLRI after a short prefix was read from the wrong place."""
    nlri, left = unpack(bytes([bits]) + carried + FULL)

    assert left == FULL
    assert nlri.prefix_length == bits
    assert nlri.origin == 65001
    following, rest = unpack(left)
    assert following.origin == 65001
    assert str(following.rt) == 'target:65001:100'
    assert rest == b''


def test_a_short_prefix_last_in_the_update_is_not_refused_as_truncated() -> None:
    nlri, left = unpack(bytes([64]) + ORIGIN + TARGET[:4])
    assert left == b''
    assert nlri.prefix_length == 64


def test_a_short_prefix_is_not_a_route_target() -> None:
    """Half a route target is not one, and must not be reported as if it were."""
    nlri, _ = unpack(bytes([64]) + ORIGIN + TARGET[:4])
    assert nlri.rt is None
    assert '"prefix-length": 64' in nlri.json()
    assert '"origin": 65001' in nlri.json()


def test_a_short_prefix_packs_back_to_what_was_received() -> None:
    wire = bytes([64]) + ORIGIN + TARGET[:4]
    nlri, _ = unpack(wire)
    assert bytes(nlri.pack_nlri(negotiated())) == wire


def test_two_prefixes_of_different_length_are_different_routes() -> None:
    short, _ = unpack(bytes([64]) + ORIGIN + TARGET[:4])
    full, _ = unpack(FULL)
    assert short.index() != full.index()


def test_the_full_and_default_forms_are_unchanged() -> None:
    target = RouteTargetASN2Number.make_route_target(ASN(65001), 100)
    full = RTC.make_rtc(ASN(65001), target)
    assert bytes(full.pack_nlri(negotiated())) == FULL
    assert full.prefix_length == 96
    assert full.json() == '{ "origin": 65001, "route-target": "target:65001:100" }'
    default = RTC.make_rtc(ASN(0), None)
    assert bytes(default.pack_nlri(negotiated())) == b'\x00'
    assert default.prefix_length == 0


@pytest.mark.parametrize(
    'data,why',
    [
        (bytes([64]) + ORIGIN + TARGET[:3], 'truncated'),  # says 64 bits, carries 56
        (bytes([31]) + ORIGIN, 'length'),  # between the default and the origin AS
        (bytes([97]) + ORIGIN + TARGET + b'\x00', 'length'),  # past origin AS and target
    ],
)
def test_a_malformed_prefix_is_refused(data, why) -> None:
    with pytest.raises(Notify, match=why):
        unpack(data)
