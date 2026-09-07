"""A FlowSpec traffic-rate of NaN or infinity reset the session with no NOTIFICATION.

The rate of a `traffic-rate` extended community is an IEEE-754 single (RFC 8955 7.1), and
the wire can carry NaN, +Inf and -Inf as easily as it carries 1000.0.  Nothing rejected
them, so the community decoded, the route was installed, and the first thing which asked
for its text or JSON rendering ran `'rate-limit:%d' % self.rate`.  `%d` puts a float
through `int()`, which raises `ValueError` for NaN and `OverflowError` for an infinity.

That happened in `Processes.message()`, outside the UPDATE decode error boundary, so the
peer's catch-all logged EXABGP MISBEHAVED and dropped the connection without sending a
NOTIFICATION.  With `-d` the debug formatter rendered the same UPDATE while still inside
the boundary and the peer got `NOTIFICATION (1,0)` instead: the protocol result depended
on whether debug logging was on.

`ExtendedCommunities.unpack` on this branch already decodes each community as it parses,
so refusing the rate in `TrafficRate.unpack` is enough to put the error where the peer can
be told about it.

See https://github.com/Exa-Networks/exabgp/issues/1426.
"""

from __future__ import annotations

from struct import pack
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficRate
from exabgp.environment import getenv
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI

# Update.unpack_message logs the payload it was handed, so the logger has to exist before
# the decoder can be called at all.
log.init(getenv())

TRAFFIC_RATE_TYPE = 0x80
TRAFFIC_RATE_SUBTYPE = 0x06

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
    '800E0B000185000005'  # MP_REACH, ipv4 flowspec
    '01180A0509'  # one destination prefix, 10.5.9.0/24
    'C01008'  # EXTENDED_COMMUNITY, eight bytes
    '80060000'  # traffic-rate, AS 0
    '7F800001'  # a rate of NaN
)


def community(rate_bits):
    """An eight byte traffic-rate extended community carrying that exact float."""
    return pack('!BBH', TRAFFIC_RATE_TYPE, TRAFFIC_RATE_SUBTYPE, 0) + pack('!L', rate_bits)


def negotiated():
    session = Mock()
    session.asn4 = False
    session.addpath = Mock()
    session.addpath.receive = Mock(return_value=False)
    session.addpath.send = Mock(return_value=False)
    session.families = [(AFI.ipv4, SAFI.flow_ip)]
    session.nexthop = []
    session.msg_size = 4096
    session.direction = Action.ANNOUNCE
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value=False)
    session.neighbor = neighbor
    return session


@pytest.mark.parametrize('rate_bits', NON_FINITE_RATES, ids=NON_FINITE_IDS)
def test_a_non_finite_traffic_rate_is_refused_by_the_decoder(rate_bits) -> None:
    """The decoder must not hand back a rate its own repr cannot print."""
    with pytest.raises(Notify) as raised:
        TrafficRate.unpack(community(rate_bits))

    assert raised.value.code == 3, 'a malformed UPDATE is an UPDATE error'
    assert raised.value.subcode == 9, 'the extended community attribute is optional'


@pytest.mark.parametrize('rate_bits', NON_FINITE_RATES, ids=NON_FINITE_IDS)
def test_the_attribute_refuses_it_rather_than_the_renderer(rate_bits) -> None:
    """The attribute decoder is the boundary, so that is where the peer's bytes are judged.

    Before the fix this call returned an attribute and the `ValueError` came out of its
    rendering later, in the API writer, where no NOTIFICATION can be sent.
    """
    with pytest.raises(Notify):
        ExtendedCommunities.unpack(community(rate_bits), Direction.IN, negotiated())


def test_a_good_community_beside_a_bad_one_does_not_hide_it() -> None:
    """Every community in the attribute is decoded, not just the first."""
    good = community(0x49742400)  # 1000000.0
    bad = community(NOT_A_NUMBER)

    with pytest.raises(Notify):
        ExtendedCommunities.unpack(good + bad, Direction.IN, negotiated())


def test_the_reported_update_raises_notify_not_value_error() -> None:
    """The exact UPDATE from the report, decoded the way the reactor decodes it.

    `Update.unpack_message` raising `Notify` is what lets the peer send a NOTIFICATION.
    A `ValueError` escaping instead is the reported bug: it reached the reactor's
    catch-all, which closes the connection silently.
    """
    with pytest.raises(Notify):
        Update.unpack_message(REPORTED_UPDATE, Direction.IN, negotiated())


@pytest.mark.parametrize(
    'rate_bits, expected',
    [(0x00000000, 'rate-limit:0'), (0x49742400, 'rate-limit:1000000'), (0xC97423F0, 'rate-limit:-999999')],
    ids=['zero', 'one-megabyte', 'negative'],
)
def test_a_finite_rate_still_decodes_and_renders(rate_bits, expected) -> None:
    """The check rejects the non-finite values and nothing else, including zero and a negative."""
    decoded = TrafficRate.unpack(community(rate_bits))

    assert repr(decoded) == expected
    assert bytes(decoded.pack()) == community(rate_bits)


@pytest.mark.parametrize('rate', [float('nan'), float('inf'), float('-inf')], ids=['nan', '+inf', '-inf'])
def test_a_non_finite_rate_cannot_be_built_either(rate) -> None:
    """Configuration is not the wire, so this is a `ValueError`, but it is still refused.

    Nothing may construct a community whose `__repr__` raises, however it got there.
    """
    with pytest.raises(ValueError, match='finite'):
        TrafficRate(ASN(0), rate)
