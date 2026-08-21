"""Attribute equality counted the attributes rather than reading them.

Attribute.__eq__ compared the ID and the FLAG and never the value:

    def __eq__(self, other):
        return bool(self.ID == other.ID and self.FLAG == other.FLAG)

Ten registered attribute classes inherit it without overriding, so any two extended
community sets, large community sets, BGP-LS attributes or prefix SIDs compared equal
whatever they carried.

AttributeCollection.sameValuesAs falls through to this for everything its community branch
does not cover, and that branch tests isinstance(value, Communities), which
ExtendedCommunities is not.  Route.__eq__ is built on sameValuesAs, so "do these two
routes carry the same attributes" was answered by counting them.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.community.extended import RouteTargetASN2Number as RouteTarget
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
from exabgp.bgp.message.update.attribute.community.extended.encapsulation import Encapsulation
from exabgp.bgp.message.update.attribute.community.large.communities import LargeCommunities

BGPLS_ADMIN_GROUP = 1088  # a four byte BGP-LS TLV, so two payloads can differ in one bit
PREFIX_SID_LABEL_INDEX = 1  # RFC 8669 3.1, a seven byte TLV

# each entry is a class a peer controls, and two well formed payloads which differ
DIFFERENT_VALUES: list[tuple[str, int, bytes, bytes]] = [
    ('extended communities', int(Attribute.CODE.EXTENDED_COMMUNITY), bytes(8), bytes(7) + bytes([1])),
    ('large communities', int(Attribute.CODE.LARGE_COMMUNITY), bytes(12), bytes(11) + bytes([1])),
    (
        'bgp-ls',
        int(Attribute.CODE.BGP_LS),
        pack('!HH', BGPLS_ADMIN_GROUP, 4) + bytes(4),
        pack('!HH', BGPLS_ADMIN_GROUP, 4) + bytes(3) + bytes([1]),
    ),
    (
        'prefix sid',
        int(Attribute.CODE.BGP_PREFIX_SID),
        bytes([PREFIX_SID_LABEL_INDEX]) + pack('!H', 7) + bytes(7),
        bytes([PREFIX_SID_LABEL_INDEX]) + pack('!H', 7) + bytes(6) + bytes([1]),
    ),
]

IDS = [row[0] for row in DIFFERENT_VALUES]


def decode(code: int, payload: bytes) -> Attribute:
    klass = Attribute.klass_by_id(code)
    assert klass is not None, f'attribute {code} is not registered, so this pins nothing'
    decoded = klass.unpack_attribute(payload, Negotiated.UNSET)
    assert decoded is not None, f'attribute {code} decoded to nothing'
    return decoded


@pytest.mark.parametrize('name, code, one, other', DIFFERENT_VALUES, ids=IDS)
def test_two_different_values_are_not_equal(name: str, code: int, one: bytes, other: bytes) -> None:
    """The whole point.  Equal meant "both are attribute 16", not "both say 16:1"."""
    assert decode(code, one) != decode(code, other), f'{name} calls two different values the same'


@pytest.mark.parametrize('name, code, one, other', DIFFERENT_VALUES, ids=IDS)
def test_the_same_value_is_still_equal(name: str, code: int, one: bytes, other: bytes) -> None:
    """A comparison which never returns True satisfies the test above and nothing else."""
    assert decode(code, one) == decode(code, one), f'{name} is not equal to itself'


@pytest.mark.parametrize('other', [None, 'attribute', 42, object()], ids=['none', 'string', 'int', 'object'])
def test_an_attribute_is_not_equal_to_something_which_is_not_one(other: object) -> None:
    """It reached for other.ID, which raised AttributeError rather than answering False."""
    attribute = ExtendedCommunities().add(Encapsulation.make_encapsulation(Encapsulation.Type.VXLAN))

    assert not (attribute == other)
    assert attribute != other


def test_a_collection_holding_one_community_differs_from_one_holding_two() -> None:
    """The path which reaches a route: sameValuesAs, which Route.__eq__ is built on.

    Its order-independent branch tests isinstance(value, Communities), and
    ExtendedCommunities is not a Communities subclass, so this fell straight through to
    the value-blind comparison and answered "same".
    """
    one = AttributeCollection()
    one.add(ExtendedCommunities().add(Encapsulation.make_encapsulation(Encapsulation.Type.VXLAN)))

    two = AttributeCollection()
    two.add(
        ExtendedCommunities()
        .add(Encapsulation.make_encapsulation(Encapsulation.Type.VXLAN))
        .add(RouteTarget.make_route_target(64512, 1))
    )

    assert not one.sameValuesAs(two)
    assert not two.sameValuesAs(one)


def test_large_communities_are_read_rather_than_counted() -> None:
    """LargeCommunities inherits the same __eq__ and is not a Communities subclass either.

    The two communities have to differ: the class drops duplicates, so 0:0:0 twice packs
    to the same bytes as 0:0:0 once and would compare equal for a reason which is correct.
    """
    one = LargeCommunities.unpack_attribute(bytes(12), Negotiated.UNSET)
    two = LargeCommunities.unpack_attribute(bytes(12) + bytes(11) + bytes([7]), Negotiated.UNSET)

    assert len(two.communities) == 2, 'the second seed does not hold two communities'
    assert one != two, 'one large community equals two'


# The tests above name four classes.  Session 5.0 found on its branch that fixing the base
# class did not reach OriginatorID, which carried its own copy of the defect, and that they
# only saw it by measuring against the registry rather than by reading the report.
#
# Thirteen classes here override __eq__.  All thirteen compare the value today; nothing
# said so, so an edit to any one of them was invisible.

MAX_PROBE_WIDTH = 33
MIN_CLASSES_REACHED = 19  # a ratchet: raise it when a probe reaches more, never lower it

# a payload of zeroes decodes for most attributes and for some decodes only to a sentinel,
# which pins nothing about the class.  These carry a header the generic probe cannot guess.
SHAPED: dict[str, tuple[bytes, bytes]] = {
    'AIGP': (b'\x01\x00\x0b' + bytes(8), b'\x01\x00\x0b' + bytes(7) + bytes([1])),
    'LinkState': (
        pack('!HH', BGPLS_ADMIN_GROUP, 4) + bytes(4),
        pack('!HH', BGPLS_ADMIN_GROUP, 4) + bytes(3) + bytes([1]),
    ),
    'PrefixSid': (
        bytes([PREFIX_SID_LABEL_INDEX]) + pack('!H', 7) + bytes(7),
        bytes([PREFIX_SID_LABEL_INDEX]) + pack('!H', 7) + bytes(6) + bytes([1]),
    ),
    # AS_SEQUENCE of one two byte ASN, since the sweep runs with asn4 off
    'ASPath': (bytes([2, 1]) + pack('!H', 65000), bytes([2, 1]) + pack('!H', 65001)),
    'AS4Path': (bytes([2, 1]) + pack('!L', 65000), bytes([2, 1]) + pack('!L', 65001)),
    'TunnelEncap': (pack('!HH', 1, 4) + bytes(4), pack('!HH', 2, 4) + bytes(4)),
}

# named rather than silently absent, so "not covered" is a decision and not an oversight
NO_TWO_VALUES = {
    'AtomicAggregate': 'carries no value at all, so two of them are equal and must be',
    'MPRNLRI': 'takes a whole NLRI encoding as its payload, covered by the round trip tests',
    'MPURNLRI': 'takes a whole NLRI encoding as its payload, covered by the round trip tests',
}


def session_with_aigp() -> object:
    """AIGP decodes to Discard unless the neighbour enables it.

    Without this the sweep below reports AIGP as covered while never once building one:
    both payloads come back as the same discard decision, which compares equal for a
    reason that is correct and tells you nothing about AIGP.
    """
    from unittest.mock import Mock

    session = Mock()
    session.neighbor = {'aigp': True}
    # a Mock auto-creates a truthy attribute for anything unset, so asn4 read as True and
    # ASPath expected four byte ASNs: the mock was answering a question nobody had set
    session.asn4 = False
    return session


def two_decodings(klass: type[Attribute], session: object) -> tuple[Attribute, Attribute] | None:
    """The shortest width at which this class decodes two payloads which differ."""
    shaped = SHAPED.get(klass.__name__)
    if shaped is not None:
        try:
            one, other = (klass.unpack_attribute(payload, session) for payload in shaped)
        except Exception:
            # a seed which no longer decodes is a broken seed, and the shape test below
            # says so by name rather than letting it error out of every test in the file
            return None
        return (one, other) if type(one) is klass and type(other) is klass else None

    for width in range(1, MAX_PROBE_WIDTH):
        try:
            one = klass.unpack_attribute(bytes(width), session)
            other = klass.unpack_attribute(bytes(width - 1) + bytes([1]), session)
        except Exception:
            continue
        if one is None or other is None or type(one) is not type(other):
            continue
        if type(one) is not klass:
            # decoded to a sentinel rather than to the class, so it pins nothing about it
            continue
        return one, other
    return None


def reachable_classes() -> dict[str, tuple[Attribute, Attribute]]:
    session = session_with_aigp()
    found = {}
    for klass in sorted(set(Attribute.registered_attributes.values()), key=lambda k: k.__name__):
        pair = two_decodings(klass, session)
        if pair is not None:
            found[klass.__name__] = pair
    return found


def test_no_registered_attribute_calls_two_different_values_equal() -> None:
    """Every class the probe can build, held to the rule, whether it overrides __eq__ or not."""
    blind = [name for name, (one, other) in reachable_classes().items() if one == other]

    assert not blind, f'these classes compare two different values as equal: {blind}'


@pytest.mark.registry_floor
def test_the_sweep_above_reaches_the_classes_it_claims_to() -> None:
    """A sweep which builds nothing reports no failures, which is the trap this series keeps hitting.

    The count is a ratchet.  It drops when a class stops decoding the probe widths, which
    is worth knowing about, and it rises when someone widens the probe.
    """
    reached = reachable_classes()

    assert len(reached) >= MIN_CLASSES_REACHED, (
        f'the probe reached {len(reached)} classes, down from {MIN_CLASSES_REACHED}: {sorted(reached)}'
    )


def test_every_registered_attribute_can_be_compared_at_all() -> None:
    """_comparable raises for a class which keeps neither wire bytes nor an override.

    That is deliberate, and it is the failure the value-blind comparison silently was, but
    it must not be reachable: an exception out of == would come from AttributeCollection
    while the reactor is deciding whether a route changed.
    """
    session = session_with_aigp()
    uncomparable = []
    for klass in sorted(set(Attribute.registered_attributes.values()), key=lambda k: k.__name__):
        for width in range(0, MAX_PROBE_WIDTH):
            try:
                decoded = klass.unpack_attribute(bytes(width), session)
            except Exception:
                continue
            if decoded is None:
                continue
            try:
                decoded == decoded
            except NotImplementedError:
                uncomparable.append(klass.__name__)
            break

    assert not uncomparable, f'these classes raise when compared: {uncomparable}'


def test_every_shaped_seed_still_decodes_to_its_own_attribute() -> None:
    """A seed which decays into a sentinel keeps the sweep green while testing nothing.

    Session 5.0 asked for this after finding their own sweep reached five attributes of
    twenty one.  The reachability ratchet above notices the count dropping; this says
    which seed went wrong and what it became, which is the difference between a number
    moving and knowing why.
    """
    session = session_with_aigp()
    wrong = {}
    for name, payloads in SHAPED.items():
        klass = next((k for k in Attribute.registered_attributes.values() if k.__name__ == name), None)
        assert klass is not None, f'{name} has a seed but is not registered'
        for payload in payloads:
            try:
                decoded = klass.unpack_attribute(payload, session)
            except Exception as exc:
                wrong[name] = f'raises {type(exc).__name__}'
                break
            if type(decoded) is not klass:
                wrong[name] = f'decodes to {type(decoded).__name__}'
                break

    assert not wrong, f'these seeds no longer build the attribute they are seeds for: {wrong}'


def test_the_classes_left_out_are_left_out_on_purpose() -> None:
    """Anything not reached is either named as a deliberate exclusion or it is a gap.

    Without this, an attribute quietly stops decoding the probe and the only signal is the
    ratchet, which says a number moved and not which class went missing.
    """
    reached = set(reachable_classes())
    registered = {klass.__name__ for klass in Attribute.registered_attributes.values()}

    unexplained = sorted(registered - reached - set(NO_TWO_VALUES))
    assert not unexplained, f'these registered attributes are neither reached nor named as an exclusion: {unexplained}'
