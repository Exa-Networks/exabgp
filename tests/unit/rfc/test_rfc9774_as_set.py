"""RFC 9774 section 3: AS_SET and AS_CONFED_SET are deprecated.

A route received with either kind of set in its path is treated as withdrawn, unless the
operator configured the neighbour with `as-set accept`, which section 3 allows and which a
route collector wants.  On the sending side exabgp never makes a set itself.

The UPDATEs are real wire bytes through Update.unpack_message, as in the RFC 7606 tests.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE

from rfc.rfc7606_wire import (
    NEXT_HOP,
    ORIGIN_IGP,
    OPTIONAL_TRANSITIVE,
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

SET, SEQ, CONFED_SEQ, CONFED_SET = 1, 2, 3, 4


def segment(kind: int, *asns: int) -> bytes:
    return bytes([kind, len(asns)]) + b''.join(pack('!L', asn) for asn in asns)


def as_path(*segments: bytes) -> bytes:
    return attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, b''.join(segments))


def accepting(negotiated: Negotiated) -> Negotiated:
    negotiated.neighbor.as_set = 'accept'
    return negotiated


# ------------------------------------------------------------------ receive


@pytest.mark.rfc('rfc9774#3-treat-as-withdraw-on-as-set')
@pytest.mark.parametrize(
    'name,path',
    [
        ('AS_SET', as_path(segment(SEQ, 65002), segment(SET, 65010, 65011))),
        ('AS_CONFED_SET', as_path(segment(CONFED_SET, 65020, 65021), segment(SEQ, 65002))),
    ],
)
def test_a_route_with_a_set_in_its_as_path_is_withdrawn(name: str, path: bytes) -> None:
    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), session())

    assert announced(parsed) == [], f'a route with an {name} was still advertised'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24'], f'a route with an {name} was not treated as withdraw'


@pytest.mark.rfc('rfc9774#3-treat-as-withdraw-on-as-set')
def test_a_set_arriving_in_the_as4_path_of_an_old_speaker_withdraws_the_route() -> None:
    # a two octet session: the AS_PATH holds AS_TRANS, the AS4_PATH the real path with a set
    two_octet = attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, bytes([SEQ, 2]) + pack('!HH', 23456, 23456))
    as4 = attribute(OPTIONAL_TRANSITIVE, CODE.AS4_PATH, segment(SEQ, 70000) + segment(SET, 70001, 70002))

    parsed = parse(update(ORIGIN_IGP + two_octet + NEXT_HOP + as4), session(asn4=False))

    assert announced(parsed) == [], 'an AS_SET in the AS4_PATH was not noticed'
    assert withdrawn_routes(parsed) == ['10.0.0.0/24']


@pytest.mark.rfc('rfc9774#3-treat-as-withdraw-on-as-set', polarity='negative')
@pytest.mark.parametrize(
    'name,path,internal',
    [
        ('AS_SEQUENCE', as_path(segment(SEQ, 65002, 65003)), False),
        # from an internal peer: an external one may not send confederation segments at
        # all (RFC 5065 5), which would withdraw the route for another reason than a set
        ('AS_CONFED_SEQUENCE', as_path(segment(CONFED_SEQ, 65020), segment(SEQ, 65002)), True),
    ],
)
def test_a_route_with_only_sequences_is_advertised(name: str, path: bytes, internal: bool) -> None:
    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), internal_session() if internal else session())

    assert announced(parsed) == ['10.0.0.0/24'], f'a route with only an {name} was withdrawn'
    assert withdrawn_routes(parsed) == []


def test_as_set_accept_keeps_the_route() -> None:
    """The operator configuration section 3 allows, for collectors."""
    path = as_path(segment(SEQ, 65002), segment(SET, 65010, 65011))

    parsed = parse(update(ORIGIN_IGP + path + NEXT_HOP), accepting(session()))

    assert announced(parsed) == ['10.0.0.0/24'], '`as-set accept` did not keep the route'


def test_the_cached_attributes_are_not_poisoned_by_the_withdraw() -> None:
    """The withdraw is UPDATE context: the session's cached attributes must not keep it."""
    payload = update(ORIGIN_IGP + as_path(segment(SEQ, 65002), segment(SET, 65010, 65011)) + NEXT_HOP)
    negotiated = session()
    negotiated.attribute_cache_enabled = True

    assert announced(parse(payload, negotiated)) == []
    assert negotiated.attribute_cache is not None, 'the attributes were not cached, the test proves nothing'

    assert announced(parse(payload, accepting(negotiated))) == ['10.0.0.0/24']


# ------------------------------------------------------------------ send


@pytest.mark.rfc('rfc9774#3-must-not-advertise-as-set')
@pytest.mark.parametrize('peer_as', [65002, 65001], ids=['ebgp', 'ibgp'])
def test_the_as_path_exabgp_makes_itself_holds_no_set(peer_as: int) -> None:
    negotiated = session(peer_as=peer_as)
    negotiated.neighbor.session.local_as = negotiated.local_as

    packed = AttributeCollection().pack_attribute(negotiated, with_default=True)
    attributes = AttributeCollection.unpack(packed, session(peer_as=peer_as))
    path = attributes[CODE.AS_PATH]

    assert isinstance(path, ASPath)
    assert not path.has_set()
    assert all(isinstance(each, SEQUENCE) for each in path.aspath)
