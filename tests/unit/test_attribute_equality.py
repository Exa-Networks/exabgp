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
