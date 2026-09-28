"""RFC 5065: exabgp as a member of a BGP confederation (issue #96).

    neighbor 192.0.2.1 {
        local-as 65001;                   # our Member-AS Number
        peer-as 65002;                    # the peer's, inside or outside
        confederation {
            identifier 65000;             # what the world outside sees
            members [ 65002 65003 ];      # the other Member-ASes
        }
    }

exabgp originates routes, it does not propagate what it learns nor select paths, so the
rules which matter are what it says in the OPEN, the AS_PATH it gives the routes it sends,
and which received paths it has to call malformed.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.aspath import CONFED_SEQUENCE, CONFED_SET, SEQUENCE, AS2Path, ASPath
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.configuration.configuration import Configuration

from rfc.rfc7606_wire import (
    NEXT_HOP,
    ORIGIN_IGP,
    WELL_KNOWN_TRANSITIVE,
    announced,
    attribute,
    internal_session,
    parse,
    session,
    update,
    withdrawn_routes,
)

CODE = Attribute.CODE
SEQ, CONFED_SEQ, CONFED_SET_ID = 2, 3, 4

IDENTIFIER = 65000
MEMBER = 65001  # ours
OTHER_MEMBER = 65002
OUTSIDE = 64999


def confederation(peer_as: int, identifier: int = IDENTIFIER, asn4: bool = True) -> Negotiated:
    """A session as the reactor has it: our Member-AS configured, the OPEN AS negotiated."""
    negotiated = session(asn4=asn4, peer_as=peer_as)
    configured = negotiated.neighbor.session
    configured.local_as = ASN(MEMBER)
    configured.peer_as = ASN(peer_as)
    configured.confederation = ASN(identifier)
    configured.confederation_members = (ASN(OTHER_MEMBER), ASN(65003))
    negotiated.local_as = configured.open_asn()
    return negotiated


def segment(kind: int, *asns: int) -> bytes:
    return bytes([kind, len(asns)]) + b''.join(pack('!L', asn) for asn in asns)


def as_path(*segments: bytes) -> bytes:
    return attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, b''.join(segments))


def sent(attributes: AttributeCollection, negotiated: Negotiated) -> AttributeCollection:
    """What the peer decodes from the attributes we pack for it.

    Decoded as an internal neighbour would, because RFC 7606 7.5 has a receiver outside the
    AS discard LOCAL_PREF: decoded as an external one, a LOCAL_PREF we wrongly sent to a peer
    outside the confederation would vanish on receipt and look like one we never sent.
    """
    return AttributeCollection.unpack(attributes.pack_attribute(negotiated, with_default=True), internal_session())


def shape(path: ASPath) -> list[tuple[str, list[int]]]:
    return [(type(each).__name__, [int(asn) for asn in each]) for each in path.aspath]


# ==============================================================================
# 4 Operation: which AS we are
# ==============================================================================


@pytest.mark.rfc('rfc5065#4-identifier-to-non-members')
@pytest.mark.rfc('rfc5065#4-member-as-to-members', polarity='negative')
def test_a_peer_outside_the_confederation_sees_the_identifier() -> None:
    negotiated = confederation(OUTSIDE)

    assert negotiated.neighbor.session.open_asn() == IDENTIFIER
    path = sent(AttributeCollection(), negotiated)[CODE.AS_PATH]
    assert shape(path) == [('SEQUENCE', [IDENTIFIER])]


@pytest.mark.rfc('rfc5065#4-member-as-to-members')
@pytest.mark.rfc('rfc5065#4-identifier-to-non-members', polarity='negative')
@pytest.mark.parametrize('peer_as', [OTHER_MEMBER, MEMBER], ids=['other-member', 'same-member'])
def test_a_peer_inside_the_confederation_sees_our_member_as(peer_as: int) -> None:
    assert confederation(peer_as).neighbor.session.open_asn() == MEMBER


def test_without_a_confederation_the_open_carries_local_as() -> None:
    negotiated = session(peer_as=OUTSIDE)
    negotiated.neighbor.session.local_as = ASN(MEMBER)
    negotiated.neighbor.session.peer_as = ASN(OUTSIDE)

    assert negotiated.neighbor.session.open_asn() == MEMBER


# ==============================================================================
# 4.1 The AS_PATH of a route we originate
# ==============================================================================


def test_an_originated_route_to_another_member_carries_our_member_as_as_a_confed_sequence() -> None:
    path = sent(AttributeCollection(), confederation(OTHER_MEMBER))[CODE.AS_PATH]

    assert shape(path) == [('CONFED_SEQUENCE', [MEMBER])]


@pytest.mark.rfc('rfc5065#4.1a-same-member-as-path-unmodified')
def test_inside_our_own_member_as_the_path_is_not_modified() -> None:
    assert shape(sent(AttributeCollection(), confederation(MEMBER))[CODE.AS_PATH]) == []

    configured = AttributeCollection()
    configured.add(AS2Path.make_aspath([CONFED_SEQUENCE([ASN(65003)]), SEQUENCE([ASN(1)])], True))
    assert shape(sent(configured, confederation(MEMBER))[CODE.AS_PATH]) == [
        ('CONFED_SEQUENCE', [65003]),
        ('SEQUENCE', [1]),
    ]


# ==============================================================================
# 5 Error Handling
# ==============================================================================


def _with_confed_segments() -> AttributeCollection:
    attributes = AttributeCollection()
    attributes.add(
        AS2Path.make_aspath(
            [CONFED_SEQUENCE([ASN(MEMBER)]), CONFED_SET([ASN(65003)]), SEQUENCE([ASN(IDENTIFIER), ASN(1)])],
            True,
        )
    )
    return attributes


@pytest.mark.rfc('rfc5065#5-no-confed-segments-to-non-members')
@pytest.mark.rfc('rfc5065#4.1c1-remove-confed-segments')
def test_confederation_segments_never_leave_the_confederation() -> None:
    path = sent(_with_confed_segments(), confederation(OUTSIDE))[CODE.AS_PATH]

    assert shape(path) == [('SEQUENCE', [IDENTIFIER, 1])]


@pytest.mark.rfc('rfc5065#5-no-confed-segments-to-non-members', polarity='negative')
@pytest.mark.rfc('rfc5065#4.1c1-remove-confed-segments', polarity='negative')
def test_confederation_segments_go_to_another_member() -> None:
    path = sent(_with_confed_segments(), confederation(OTHER_MEMBER))[CODE.AS_PATH]

    assert shape(path)[0] == ('CONFED_SEQUENCE', [MEMBER])
    assert path.has_confed()


@pytest.mark.rfc('rfc5065#5-confed-segments-from-outside-malformed')
@pytest.mark.parametrize('kind', [CONFED_SEQ, CONFED_SET_ID], ids=['confed-sequence', 'confed-set'])
def test_confederation_segments_from_a_peer_outside_withdraw_the_route(kind: int) -> None:
    path = as_path(segment(kind, 65003), segment(SEQ, OUTSIDE))
    negotiated = confederation(OUTSIDE)
    negotiated.neighbor.as_set = 'accept'  # an AS_CONFED_SET is RFC 9774's too: isolate RFC 5065

    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), negotiated)

    assert announced(parsed) == []
    assert withdrawn_routes(parsed) == ['10.0.0.0/24']


@pytest.mark.rfc('rfc5065#5-confed-segments-from-outside-malformed', polarity='negative')
def test_a_plain_path_from_a_peer_outside_is_advertised() -> None:
    parsed = parse(update(ORIGIN_IGP + as_path(segment(SEQ, OUTSIDE)) + NEXT_HOP), confederation(OUTSIDE))

    assert announced(parsed) == ['10.0.0.0/24']


@pytest.mark.rfc('rfc5065#5-member-path-must-start-with-confed-sequence')
@pytest.mark.parametrize(
    'path',
    [as_path(segment(SEQ, OUTSIDE)), as_path()],
    ids=['as-sequence-first', 'empty'],
)
def test_a_path_from_another_member_not_starting_with_a_confed_sequence_withdraws(path: bytes) -> None:
    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), confederation(OTHER_MEMBER))

    assert announced(parsed) == []
    assert withdrawn_routes(parsed) == ['10.0.0.0/24']


@pytest.mark.rfc('rfc5065#5-member-path-must-start-with-confed-sequence', polarity='negative')
def test_a_path_from_another_member_starting_with_a_confed_sequence_is_advertised() -> None:
    path = as_path(segment(CONFED_SEQ, OTHER_MEMBER), segment(SEQ, OUTSIDE))

    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), confederation(OTHER_MEMBER))

    assert announced(parsed) == ['10.0.0.0/24']


def test_without_a_confederation_configured_confed_segments_are_accepted() -> None:
    """What exabgp did before, and what a speaker which is not a member has no rule for."""
    path = as_path(segment(CONFED_SEQ, 65003), segment(SEQ, OUTSIDE))

    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), session(peer_as=OUTSIDE))

    assert announced(parsed) == ['10.0.0.0/24']


# ==============================================================================
# 5.2 MED and LOCAL_PREF
# ==============================================================================


@pytest.mark.rfc('rfc5065#5.2-next-hop-and-med-unchanged-to-members')
def test_med_and_next_hop_go_unchanged_to_another_member() -> None:
    attributes = AttributeCollection()
    attributes.add(MED.from_int(50))

    received = sent(attributes, confederation(OTHER_MEMBER))

    assert received[CODE.MED].med == 50


def test_local_pref_goes_to_another_member_and_not_outside() -> None:
    attributes = AttributeCollection()
    attributes.add(LocalPreference.from_int(200))

    assert sent(attributes, confederation(OTHER_MEMBER))[CODE.LOCAL_PREF].localpref == 200
    assert sent(AttributeCollection(), confederation(OTHER_MEMBER))[CODE.LOCAL_PREF].localpref == 100
    assert CODE.LOCAL_PREF not in sent(attributes, confederation(OUTSIDE))


# ==============================================================================
# 6 Compatibility
# ==============================================================================


@pytest.mark.rfc('rfc5065#6-recognize-confed-segments')
def test_both_confederation_segment_types_are_decoded() -> None:
    path = as_path(segment(CONFED_SEQ, 65002, 65003), segment(CONFED_SET_ID, 65004), segment(SEQ, 1))
    negotiated = session()
    negotiated.neighbor.as_set = 'accept'

    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), negotiated)

    assert shape(parsed.attributes[CODE.AS_PATH]) == [
        ('CONFED_SEQUENCE', [65002, 65003]),
        ('CONFED_SET', [65004]),
        ('SEQUENCE', [1]),
    ]


@pytest.mark.rfc('rfc5065#6-recognize-confed-segments', polarity='negative')
def test_a_segment_type_beyond_the_four_is_malformed() -> None:
    parsed = parse(update(ORIGIN_IGP + as_path(segment(5, 1)) + NEXT_HOP), session())

    assert announced(parsed) == []
    assert withdrawn_routes(parsed) == ['10.0.0.0/24']


# ==============================================================================
# The configuration
# ==============================================================================


def _configure(block: str, local_as: str = str(MEMBER), peer_as: str = str(OUTSIDE)) -> tuple[bool, Configuration]:
    text = f"""neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as {local_as};
    peer-as {peer_as};
    {block}
}}"""
    configuration = Configuration([text], text=True)
    return configuration.reload(), configuration


@pytest.mark.rfc('rfc5065#6-members-support-confederations')
def test_the_confederation_block_reaches_the_session() -> None:
    ok, configuration = _configure('confederation { identifier 65000; members [ 65002 65003 ]; }')
    assert ok, configuration.error

    configured = next(iter(configuration.neighbors.values())).session
    assert configured.confederation == IDENTIFIER
    assert configured.confederation_members == (ASN(65002), ASN(65003))
    assert configured.open_asn() == IDENTIFIER


@pytest.mark.parametrize(
    'block,local_as,message',
    [
        ('confederation { members [ 65002 ]; }', str(MEMBER), 'missing identifier'),
        ('confederation { identifier 65001; }', str(MEMBER), 'can not be the confederation identifier'),
        ('confederation { identifier 65000; members [ 65000 ]; }', str(MEMBER), 'can not also be a member'),
        ('confederation { identifier 65000; }', 'auto', 'auto is not allowed'),
        ('confederation { identifier 0; }', str(MEMBER), 'AS 0'),
    ],
)
def test_a_confederation_which_can_not_work_is_refused(block: str, local_as: str, message: str) -> None:
    ok, configuration = _configure(block, local_as=local_as)

    assert not ok
    assert message in str(configuration.error)


def test_the_neighbor_configuration_shows_the_confederation() -> None:
    ok, configuration = _configure('confederation { identifier 65000; members [ 65002 65003 ]; }')
    assert ok, configuration.error

    shown = str(next(iter(configuration.neighbors.values())))

    assert 'confederation {' in shown
    assert 'identifier 65000;' in shown
    assert 'members [ 65002 65003 ];' in shown
