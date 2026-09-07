"""A FlowSpec traffic-rate of NaN or infinity reset the session with no NOTIFICATION.

The rate of a `traffic-rate` extended community is an IEEE-754 single (RFC 8955 7.1),
and the wire can carry NaN, +Inf and -Inf as easily as it carries 1000.0.  Nothing
rejected them, so the community decoded, the route was installed, and the first thing
which asked for its text or JSON rendering ran `'rate-limit:%d' % self.rate`.  `%d` puts
a float through `int()`, which raises `ValueError` for NaN and `OverflowError` for an
infinity.

That happened in `Processes.message()`, outside the UPDATE decode error boundary, so the
peer's catch-all logged EXABGP MISBEHAVED and dropped the connection without sending a
NOTIFICATION.  With `-d` the debug formatter rendered the same UPDATE while still inside
the boundary, and the peer got `NOTIFICATION (1,0)` instead: the protocol result depended
on whether debug logging was on.

Two things were wrong and both are pinned here:

1.  The decoder accepted a rate it could not render.  A non-finite rate is now a
    `Notify(3, 9)` raised where the UPDATE is decoded, which is what puts a NOTIFICATION
    on the wire.

2.  `ExtendedCommunities` only checked that the attribute was a multiple of eight bytes.
    The individual communities were decoded by the lazy `communities` property, so a
    decoder raising inside one of them raised from `json()` and `__repr__()`, wherever in
    the process those happened to be called, rather than from the attribute parser.

See https://github.com/Exa-Networks/exabgp/issues/1426.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRatePackets
from exabgp.protocol.family import AFI, SAFI

TRAFFIC_RATE_TYPE = 0x80
TRAFFIC_RATE_SUBTYPE = 0x06
TRAFFIC_RATE_PACKETS_SUBTYPE = 0x0C

# The four byte patterns of the IEEE-754 singles no rate may be.  A signalling NaN is
# included because it is the one from the report and because `struct` hands it back
# unchanged rather than quieting it.
NOT_A_NUMBER = 0x7F800001
POSITIVE_INFINITY = 0x7F800000
NEGATIVE_INFINITY = 0xFF800000
NEGATIVE_NOT_A_NUMBER = 0xFFC00001

NON_FINITE_RATES = [NOT_A_NUMBER, POSITIVE_INFINITY, NEGATIVE_INFINITY, NEGATIVE_NOT_A_NUMBER]
NON_FINITE_IDS = ['nan', '+inf', '-inf', '-nan']

# The UPDATE from the report: ORIGIN, an empty AS_PATH, an MP_REACH carrying one IPv4
# FlowSpec NLRI, and an EXTENDED_COMMUNITY holding traffic-rate with a rate of NaN.
REPORTED_UPDATE = bytes.fromhex(
    '0000'  # no withdrawn routes
    '0020'  # thirty two bytes of path attributes
    '40010100'  # ORIGIN igp
    '400200'  # an empty AS_PATH
    '800E0B000185000005' + '01180A0509'  # MP_REACH, ipv4 flowspec, one destination prefix
    'C01008' + '80060000' + '7F800001'  # EXTENDED_COMMUNITY, traffic-rate, a rate of NaN
)


def community(subtype: int, rate_bits: int) -> bytes:
    """An eight byte traffic-rate extended community carrying that exact float."""
    return pack('!BBH', TRAFFIC_RATE_TYPE, subtype, 0) + pack('!L', rate_bits)


def negotiated() -> Any:
    session = Mock()
    session.asn4 = False
    session.addpath = Mock()
    session.addpath.receive = Mock(return_value=False)
    session.addpath.send = Mock(return_value=False)
    session.required = Mock(return_value=False)
    session.families = [(AFI.ipv4, SAFI.flow_ip)]
    session.nexthop = []
    session.msg_size = 4096
    session.direction = Action.ANNOUNCE
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value=False)
    neighbor.session.local_address = None
    session.neighbor = neighbor
    session.attribute_cache = None
    session.attribute_cache_packed = b''
    session.attribute_cache_enabled = False
    return session


@pytest.mark.parametrize('rate_bits', NON_FINITE_RATES, ids=NON_FINITE_IDS)
def test_a_non_finite_traffic_rate_is_refused_by_the_decoder(rate_bits: int) -> None:
    """The decoder must not hand back a rate its own repr cannot print."""
    with pytest.raises(Notify) as raised:
        TrafficRate.unpack_attribute(community(TRAFFIC_RATE_SUBTYPE, rate_bits), None)

    assert raised.value.code == 3, 'a malformed UPDATE is an UPDATE error'
    assert raised.value.subcode == 9, 'the extended community attribute is optional'


@pytest.mark.parametrize('rate_bits', NON_FINITE_RATES, ids=NON_FINITE_IDS)
def test_a_non_finite_packet_rate_is_refused_by_the_decoder(rate_bits: int) -> None:
    """RFC 8955 traffic-rate-packets carries the same float and needs the same check.

    Its `rate` clamps a negative rate to zero with `max(value, 0.0)`, which lets a NaN
    straight through: every comparison against a NaN is false, so `max` returns it.
    """
    with pytest.raises(Notify):
        TrafficRatePackets.unpack_attribute(community(TRAFFIC_RATE_PACKETS_SUBTYPE, rate_bits), None)


@pytest.mark.parametrize('rate_bits', NON_FINITE_RATES, ids=NON_FINITE_IDS)
def test_the_attribute_refuses_it_rather_than_the_renderer(rate_bits: int) -> None:
    """`from_packet` is the boundary, so that is where the peer's bytes are judged.

    Before the fix this call returned an attribute and the `ValueError` came out of
    `json()` later, in the API writer, where no NOTIFICATION can be sent.
    """
    with pytest.raises(Notify):
        ExtendedCommunities.from_packet(community(TRAFFIC_RATE_SUBTYPE, rate_bits))


def test_a_good_community_beside_a_bad_one_does_not_hide_it() -> None:
    """The walk covers every community in the attribute, not just the first."""
    good = community(TRAFFIC_RATE_SUBTYPE, 0x49742400)  # 1000000.0
    bad = community(TRAFFIC_RATE_SUBTYPE, NOT_A_NUMBER)

    with pytest.raises(Notify):
        ExtendedCommunities.from_packet(good + bad)


def test_the_reported_update_raises_notify_not_value_error() -> None:
    """The exact UPDATE from the report, decoded the way the reactor decodes it.

    `Update.unpack_message` raising `Notify` is what lets the peer send a NOTIFICATION.
    A `ValueError` escaping instead is the reported bug: it reached the reactor's
    catch-all, which closes the connection silently.
    """
    with pytest.raises(Notify):
        Update.unpack_message(REPORTED_UPDATE, negotiated()).parse(negotiated())


@pytest.mark.parametrize(
    'rate_bits, expected',
    [(0x00000000, 'rate-limit:0'), (0x49742400, 'rate-limit:1000000'), (0xC97423F0, 'rate-limit:-999999')],
    ids=['zero', 'one-megabyte', 'negative'],
)
def test_a_finite_rate_still_decodes_and_renders(rate_bits: int, expected: str) -> None:
    """The check rejects the non-finite values and nothing else, including zero and a negative."""
    decoded = TrafficRate.unpack_attribute(community(TRAFFIC_RATE_SUBTYPE, rate_bits), None)

    assert repr(decoded) == expected
    assert bytes(decoded.pack_attribute(Mock())) == community(TRAFFIC_RATE_SUBTYPE, rate_bits)


def test_a_finite_packet_rate_still_decodes_and_renders() -> None:
    decoded = TrafficRatePackets.unpack_attribute(community(TRAFFIC_RATE_PACKETS_SUBTYPE, 0x447A0000), None)

    assert decoded.rate == 1000.0
    assert repr(decoded) == 'rate-limit:1000:packets'


@pytest.mark.parametrize('rate', [float('nan'), float('inf'), float('-inf')], ids=['nan', '+inf', '-inf'])
def test_a_non_finite_rate_cannot_be_built_either(rate: float) -> None:
    """Configuration is not the wire, so this is a `ValueError`, but it is still refused.

    Nothing may construct a community whose `__repr__` raises, however it got there.
    """
    with pytest.raises(ValueError, match='finite'):
        TrafficRate.make_traffic_rate(ASN(0), rate)

    with pytest.raises(ValueError, match='finite'):
        TrafficRatePackets.make_traffic_rate_packets(ASN(0), rate)
