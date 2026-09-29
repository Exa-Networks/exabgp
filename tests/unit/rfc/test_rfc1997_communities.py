"""RFC 1997: the one sentence in it which binds the bytes exabgp puts on the wire.

RFC 1997 is four pages and says less than its reputation suggests.  It has three
capitalised MUST NOTs, all about not re-advertising a route carrying a well-known
community.  exabgp re-advertises nothing on its own, but a route decoded off one session
remembers the peer it came from (`AttributeCollection.learned_from`), and the outgoing
RIB of any other neighbour honours the three values on it.  The end of this file proves
it, and proves too that a route we originate is left alone.  What it
does not have, anywhere, is the rule it is usually cited for: that the COMMUNITIES
attribute length is a multiple of four.  The document states the encoding flatly - "The
attribute consists of a set of four octet values" - with no keyword, so there is no
requirement in RFC 1997 to record for it.  The normative form of that rule is RFC 7606
section 7.8.  The last two tests in this file still pin the behaviour, without an
`rfc()` marker, because the behaviour is worth a regression test wherever the sentence
that demands it lives.

That leaves one recordable obligation with teeth:

    The rest of the community attribute values shall be encoded using an autonomous
    system number in the first two octets.

"The rest" is what survives the two reserved ranges named in the sentence before it, so
the well-known values are outside its scope, and `ASN:value` in the configuration is how
exabgp implements it.

Two of the tests below were once `xfail`.  The legacy parser bounded both halves of
`ASN:value` against `Community.MAX`, which is 0xFFFFFFFF, when each half is sixteen bits.
Nothing in it was sixteen bit aware, so the check never fired for a value which overflowed
its half, and the two failures fell out of the same wrong constant:

    community 1:65536   is encoded as 0x00020000 and reported back as 2:0
    community 65536:1   escapes the configuration parser as a struct.error

The first is the serious one.  A typo in a configuration file does not produce an error,
it produces a community belonging to a different autonomous system, announced to every
peer, and the daemon reports the value it invented rather than the value that was typed.
"""

from __future__ import annotations

import re
from struct import pack

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.asn4 import ASN4
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community import Communities, Community
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB
from exabgp.rib.route import Route
from exabgp.configuration.grammar.types.bgp import community as _community

from rfc.community_wire import attribute, parse, withdrawn

COMMUNITY = int(Attribute.CODE.COMMUNITY)
COMMUNITY_SIZE_BYTES = 4

# RFC 1997: "The community attribute values ranging from 0x0000000 through 0x0000FFFF
# and 0xFFFF0000 through 0xFFFFFFFF are hereby reserved."  Everything outside these is
# what "the rest" in the requirement refers to.
RESERVED_LOW_LAST = 0x0000FFFF
RESERVED_HIGH_FIRST = 0xFFFF0000

# <asn>:<value> pairs which are all outside the reserved ranges, so all in scope.
ASSIGNABLE = [
    (1, 0),
    (64496, 1234),
    (65000, 666),
    (65534, 65535),
]

WELL_KNOWN = [
    ('no-export', Community.NO_EXPORT),
    ('no-advertise', Community.NO_ADVERTISE),
    ('no-export-subconfed', Community.NO_EXPORT_SUBCONFED),
    ('blackhole', Community.BLACKHOLE),
]

CANONICAL = re.compile(r'^\d+:\d+$')


@pytest.mark.rfc('rfc1997#values-encoded-with-asn')
@pytest.mark.parametrize('asn,value', ASSIGNABLE, ids=[f'{a}:{v}' for a, v in ASSIGNABLE])
def test_a_configured_community_carries_the_asn_in_the_first_two_octets(asn: int, value: int) -> None:
    """`<asn>:<value>` in the configuration puts that ASN, and no other, in octets 0 and 1."""
    packed = bytes(_community(f'{asn}:{value}').community)

    assert len(packed) == COMMUNITY_SIZE_BYTES
    assert int.from_bytes(packed[:2], 'big') == asn, (
        f'{asn}:{value} was encoded as {packed.hex()}, whose first two octets are '
        f'AS {int.from_bytes(packed[:2], "big")} rather than the AS which was configured'
    )
    assert int.from_bytes(packed[2:], 'big') == value


@pytest.mark.rfc('rfc1997#values-encoded-with-asn')
@pytest.mark.parametrize('asn,value', ASSIGNABLE, ids=[f'{a}:{v}' for a, v in ASSIGNABLE])
def test_a_community_off_the_wire_is_read_back_as_the_same_asn(asn: int, value: int) -> None:
    """The decode direction of the same rule: octets 0 and 1 are read as the ASN.

    A packer and a reader which disagree about where the ASN lives would each pass their
    own half of this file, so the round trip is the assertion that matters.
    """
    rendered = repr(Community(pack('!HH', asn, value)))

    assert CANONICAL.match(rendered), f'{rendered!r} is not <asn>:<value>'
    assert rendered == f'{asn}:{value}'


@pytest.mark.rfc('rfc1997#values-encoded-with-asn')
@pytest.mark.parametrize('name,packed', WELL_KNOWN, ids=[name for name, _ in WELL_KNOWN])
def test_a_reserved_value_is_not_given_the_asn_reading(name: str, packed: bytes) -> None:
    """The requirement says "the rest", so the reserved ranges are outside it.

    All five well-known values live in 0xFFFF0000-0xFFFFFFFF.  Reading 0xFFFFFF01 as
    "AS 65535, community 65281" would be applying the ASN convention where the RFC
    excludes it, and would put a reserved value into an operator's AS namespace.
    """
    value = int.from_bytes(packed, 'big')

    assert value >= RESERVED_HIGH_FIRST or value <= RESERVED_LOW_LAST, f'{name} is not in a range RFC 1997 reserves'
    assert repr(Community(packed)) == name, 'a reserved value was rendered as an ASN pair'


@pytest.mark.rfc('rfc1997#values-encoded-with-asn', polarity='negative')
def test_a_value_too_large_for_its_half_does_not_overflow_into_the_asn() -> None:
    """16 bits of value must not carry into the 16 bits of ASN above it.

    This is the failure which matters, because it is silent.  `community 1:65536` is
    accepted, announced to every peer as 0x00020000, and reported back through the API as
    2:0, so the operator is told a community they did not configure, belonging to an AS
    they do not hold.
    """
    with pytest.raises(ValueError):
        _community('1:65536')


@pytest.mark.rfc('rfc1997#values-encoded-with-asn', polarity='negative')
def test_an_asn_too_large_for_two_octets_is_refused_by_the_parser() -> None:
    """A 32 bit ASN does not fit the first two octets, so the configuration is invalid.

    EXA_STYLE 1.2: bad operator configuration raises `ValueError` with the parser
    context.  `struct.error` is neither, and the grammar only turns a `ValueError` into a
    `ConfigError`, so a `struct.error` would leave the parser as an unhandled exception
    rather than as a message naming the line which is wrong.
    """
    with pytest.raises(ValueError):
        _community('65536:1')


# ---------------------------------------------------------------------------
# No rfc() marker below this line.  RFC 1997 nowhere states the multiple-of-four rule
# with a keyword; RFC 7606 section 7.8 does, and that ledger is elsewhere.  The tests
# stay because the code they cover is here.


@pytest.mark.parametrize('count', [1, 2, 8])
def test_a_whole_number_of_communities_is_accepted(count: int) -> None:
    value = bytes(count * COMMUNITY_SIZE_BYTES)
    collection = parse(COMMUNITY, value)

    assert not withdrawn(collection), f'{len(value)} bytes of COMMUNITY were refused'
    decoded = collection[Attribute.CODE.COMMUNITY]
    assert isinstance(decoded, Communities)
    assert len(decoded.communities) == count


@pytest.mark.parametrize('length', [0, 1, 3, 5, 7, 9])
def test_a_length_which_is_not_a_whole_number_of_communities_withdraws_the_route(length: int) -> None:
    """Treat-as-withdraw, not a NOTIFICATION: this is an optional transitive attribute.

    Zero is in the list on purpose.  `Communities.from_packet` accepts it, because
    0 % 4 == 0; what refuses it is `VALID_ZERO` being false on the class, checked by
    `AttributeCollection.parse` before the decoder is reached.  Split across two places
    like that, the zero case is the one a refactor drops.
    """
    assert withdrawn(parse(COMMUNITY, bytes(length))), f'{length} bytes of COMMUNITY were accepted'


# ---------------------------------------------------------------------------
# The three well-known communities, and the SHALL which says they must be acted on.
#
# All three bind a route received and re-advertised.  The tests below take the closest
# path exabgp has: a route is decoded off the wire from one session, exactly as
# reactor/protocol.py does, and handed to the outgoing RIB of another.  The outgoing RIB
# is where egress policy lives (RFC 9234 suppresses OTC routes there too), and
# OutgoingRIB._community_allowed is where a well-known community stops the route.
#
# A route the configuration or the API gives us is originated by us, not received, and
# the rule does not touch it: `community no-export` towards a transit is how an operator
# asks that transit to keep a blackhole or a more specific to itself.

LOCAL_AS = 65001
CONFEDERATION_ID = 65000
OTHER_MEMBER_AS = 65002
LEARNED_FROM_AS = 64999
EXTERNAL_AS = 64998

LEARNED_FROM = '192.0.2.1'
READVERTISED_TO = '192.0.2.2'
OUR_ADDRESS = '192.0.2.254'

ORIGIN_IGP = bytes([0x40, 0x01, 0x01, 0x00])
AS_PATH_FROM_PEER = bytes([0x40, 0x02, 0x06, 0x02, 0x01]) + pack('!L', LEARNED_FROM_AS)
NEXT_HOP = bytes([0x40, 0x03, 0x04, 192, 0, 2, 1])
PREFIX_10_0_0_0_24 = bytes([24, 10, 0, 0])

# our Member-AS is LOCAL_AS, and the neighbour is in another member of the same confederation
IN_CONFEDERATION = f'confederation {{ identifier {CONFEDERATION_ID}; members [ {OTHER_MEMBER_AS} ]; }}'


@pytest.fixture
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """RIB keeps a process wide cache keyed by neighbour name; tests must not share it."""
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour(address: str, peer_as: int, extra: str = '') -> Neighbor:
    """A neighbour built by the real configuration parser."""
    text = f"""
neighbor {address} {{
    router-id {OUR_ADDRESS};
    local-address {OUR_ADDRESS};
    local-as {LOCAL_AS};
    peer-as {peer_as};
    {extra}
    family {{ ipv4 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    parsed: Neighbor = next(iter(configuration.neighbors.values()))
    return parsed


def established(neighbor: Neighbor, peer_as: int) -> Negotiated:
    """Run the real OPEN negotiation against a peer which offered what we did."""
    sent = Capabilities().new(neighbor, False, local_as=ASN(LOCAL_AS))
    negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(LOCAL_AS), HoldTime(180), RouterID(OUR_ADDRESS), sent))
    negotiated.received(
        Open.make_open(Version(4), ASN(peer_as), HoldTime(180), RouterID(LEARNED_FROM), theirs(sent, peer_as))
    )
    return negotiated


def theirs(sent: Capabilities, peer_as: int) -> Capabilities:
    """The peer's capabilities, ours copied with its own AS: RFC 6793 4.1 reads the AS there."""
    capabilities = Capabilities(sent)
    capabilities[Capability.CODE.FOUR_BYTES_ASN] = ASN4(ASN(peer_as))
    return capabilities


def received(communities: list[bytes]) -> UpdateCollection:
    """10.0.0.0/24 as an external peer sends it, carrying `communities`, decoded for real."""
    session = established(neighbour(LEARNED_FROM, LEARNED_FROM_AS), LEARNED_FROM_AS)
    attributes = ORIGIN_IGP + AS_PATH_FROM_PEER + NEXT_HOP
    if communities:
        attributes += attribute(COMMUNITY, b''.join(communities))
    payload = pack('!H', 0) + pack('!H', len(attributes)) + attributes + PREFIX_10_0_0_0_24
    message = Update.unpack_message(payload, session)
    assert isinstance(message, Update)
    return message.parse(session)


def readvertised(communities: list[bytes], peer_as: int, extra: str = '') -> list[str]:
    """The prefixes a second neighbour is sent, after it is handed a received route.

    What is counted is what the outgoing RIB hands the encoder, and not what a decode of
    the wire makes of it: decoding with our own session would apply the checks a receiver
    makes (RFC 5065 wants a member AS leftmost, RFC 7606 then withdraws), and a route
    turned into a withdraw on the way back in would look as though it was never sent.
    """
    target = neighbour(READVERTISED_TO, peer_as, extra)
    session = established(target, peer_as)
    learned = received(communities)
    assert learned.announces, 'the received UPDATE carried no route to re-advertise'
    for routed in learned.announces:
        target.rib.outgoing.add_to_rib(Route(routed.nlri, learned.attributes, routed.nexthop))

    sent: list[str] = []
    for update in target.rib.outgoing.updates(True, None, session):
        if not isinstance(update, UpdateCollection) or not update.announces:
            continue
        assert list(update.messages(session)), 'the UPDATE for the route did not encode'
        sent.extend(str(routed.nlri) for routed in update.announces)
    return sent


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.parametrize(
    'peer_as,extra',
    [(EXTERNAL_AS, ''), (LOCAL_AS, ''), (OTHER_MEMBER_AS, IN_CONFEDERATION)],
    ids=['external', 'internal', 'other-member-as'],
)
def test_a_received_route_without_a_well_known_community_does_reach_another_peer(peer_as: int, extra: str) -> None:
    """The control for the tests below: the plumbing carries an ordinary route.

    One case per kind of neighbour they use.  Without it a test expecting nothing to be
    sent would pass because the route never left at all.
    """
    assert readvertised([], peer_as, extra) == ['10.0.0.0/24']


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.rfc('rfc1997#wellknown-no-export')
def test_a_route_received_with_no_export_is_not_advertised_to_an_external_peer() -> None:
    """NO_EXPORT keeps the route inside the AS, and a plain eBGP neighbour is outside it."""
    sent = readvertised([Community.NO_EXPORT], EXTERNAL_AS)

    assert sent == [], f'a route carrying no-export was sent to AS {EXTERNAL_AS}: {sent}'


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.rfc('rfc1997#wellknown-no-advertise')
def test_a_route_received_with_no_advertise_is_not_advertised_even_to_an_internal_peer() -> None:
    """NO_ADVERTISE is the strictest of the three: no other BGP peer at all.

    The target is iBGP on purpose, since that is the one case where NO_EXPORT would let
    the route through and NO_ADVERTISE must not.
    """
    sent = readvertised([Community.NO_ADVERTISE], LOCAL_AS)

    assert sent == [], f'a route carrying no-advertise was sent to an iBGP peer: {sent}'


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.rfc('rfc1997#wellknown-no-export-subconfed')
def test_a_route_received_with_no_export_subconfed_stays_in_our_member_as() -> None:
    """The parenthesis is the point: another member AS of our own confederation counts as
    external here, where for NO_EXPORT it would be inside the boundary."""
    sent = readvertised([Community.NO_EXPORT_SUBCONFED], OTHER_MEMBER_AS, IN_CONFEDERATION)

    assert sent == [], f'a route carrying no-export-subconfed was sent to member AS {OTHER_MEMBER_AS}: {sent}'


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.rfc('rfc1997#wellknown-operations-implemented')
@pytest.mark.parametrize(
    'name,community',
    WELL_KNOWN[:3],
    ids=[name for name, _ in WELL_KNOWN[:3]],
)
def test_every_well_known_community_keeps_a_received_route_from_an_external_peer(name: str, community: bytes) -> None:
    """Each of the three forbids an eBGP neighbour outside any confederation, so "their
    operations shall be implemented" means none of them reaches one."""
    sent = readvertised([community], EXTERNAL_AS)

    assert sent == [], f'a route carrying {name} was sent to AS {EXTERNAL_AS}: {sent}'


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.rfc('rfc1997#wellknown-no-export')
@pytest.mark.parametrize(
    'peer_as,extra',
    [(LOCAL_AS, ''), (OTHER_MEMBER_AS, IN_CONFEDERATION)],
    ids=['internal', 'other-member-as'],
)
def test_a_route_received_with_no_export_stays_inside_the_confederation_boundary(peer_as: int, extra: str) -> None:
    """The boundary is the confederation, not the Member-AS: both of these are inside it.

    A check which refused every neighbour would pass the tests above and fail this one.
    """
    assert readvertised([Community.NO_EXPORT], peer_as, extra) == ['10.0.0.0/24']


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.rfc('rfc1997#wellknown-no-export-subconfed')
def test_a_route_received_with_no_export_subconfed_reaches_an_internal_peer() -> None:
    """Our own Member-AS is inside the boundary NO_EXPORT_SUBCONFED draws."""
    assert readvertised([Community.NO_EXPORT_SUBCONFED], LOCAL_AS) == ['10.0.0.0/24']


def originated(communities: str, peer_as: int) -> list[str]:
    """The prefixes an external neighbour is sent for a route the configuration gave us."""
    target = neighbour(READVERTISED_TO, peer_as)
    session = established(target, peer_as)
    configuration = Configuration([''], text=True)
    line = f'route 10.0.0.0/24 next-hop {LEARNED_FROM} community [ {communities} ]'
    assert configuration.partial('static', line, 'announce'), str(configuration.error)
    for route in configuration.pop_routes():
        target.rib.outgoing.add_to_rib(route)

    sent: list[str] = []
    for update in target.rib.outgoing.updates(True, None, session):
        if isinstance(update, UpdateCollection):
            sent.extend(str(routed.nlri) for routed in update.announces)
    return sent


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.parametrize('name', ['no-export', 'no-advertise', 'no-export-subconfed'])
def test_a_route_we_originate_goes_out_whatever_well_known_community_it_carries(name: str) -> None:
    """Unmarked: the RFC binds "routes received", and this one was configured.

    The community is for the peer to act on.  Refusing to send it would take away the way
    an operator tells a transit to keep a blackhole route to itself.
    """
    assert originated(name, EXTERNAL_AS) == ['10.0.0.0/24']
