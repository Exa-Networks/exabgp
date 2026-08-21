#!/usr/bin/env python3
# encoding: utf-8

"""Two attributes are the same attribute when they carry the same value

Attribute.__eq__ compared the ID and the FLAG and never the value:

    def __eq__(self, other):
        return self.ID == other.ID and self.FLAG == other.FLAG

40 of the 59 registered classes inherit it, so any two BGP-LS attributes, prefix
SIDs, large or extended community sets compared equal whatever they carried.
Attributes.sameValuesAs falls through to this for everything its Communities
branch does not cover, so two BGP-LS attributes with entirely different contents
answered "same values" and a route whose attribute had changed was never
re-advertised. OriginatorID overrode the base method with the same defect, which
is why fixing the base class alone was not enough.

The obvious fix, comparing vars(self), is wrong in the opposite direction and was
tried first: the decoded state holds nested objects which define no __eq__, so
they compare by identity and two attributes decoded from the very same bytes come
out unequal. That re-advertises everything forever. Both directions are asserted
below for that reason, because a test which only checks that different values
differ passes happily with an __eq__ that answers False to everything.
"""

from struct import pack

from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute import Attribute, Attributes


def negotiated():
    stub = Mock()
    stub.families = []
    stub.asn4 = True
    return stub


def flag_for(aid):
    """The flag an attribute is registered under

    Attribute.unpack keys the registry on (id, flag | EXTENDED_LENGTH), so a
    hand picked flag silently misses every attribute registered under a
    different one: the lookup fails and Notify is raised before any decoder
    runs. Reading the flag back from the registry is what makes this file
    exercise the attributes it names rather than a handful of them.
    """
    for registered_id, registered_flag in Attribute.registered_attributes:
        if registered_id == aid:
            return registered_flag
    raise LookupError(f'attribute {aid} is not registered')


def decode(aid, payload, flag=None):
    return Attribute.unpack(aid, flag_for(aid) if flag is None else flag, payload, Direction.IN, negotiated())


ORIGIN = 1
MED = 4
LOCAL_PREF = 5
ORIGINATOR_ID = 9
CLUSTER_LIST = 10
LARGE_COMMUNITY = 32
BGP_LS = 29


def bgpls(address):
    """A BGP-LS attribute holding one Local TE Router ID"""
    return pack('!HH', 1028, 4) + bytes(address)


# (attribute code, one payload, a different payload)
PAIRS = [
    pytest.param(ORIGIN, bytes([0]), bytes([1]), id='origin'),
    pytest.param(MED, pack('!L', 10), pack('!L', 20), id='med'),
    pytest.param(LOCAL_PREF, pack('!L', 100), pack('!L', 200), id='local-preference'),
    pytest.param(ORIGINATOR_ID, bytes([10, 0, 0, 1]), bytes([9, 9, 9, 9]), id='originator-id'),
    pytest.param(CLUSTER_LIST, bytes([10, 0, 0, 1]), bytes([9, 9, 9, 9]), id='cluster-list'),
    pytest.param(LARGE_COMMUNITY, bytes(12), bytes([0, 0, 0, 9] * 3), id='large-communities'),
    pytest.param(BGP_LS, bgpls([10, 0, 0, 1]), bgpls([9, 9, 9, 9]), id='bgp-ls'),
]


class TestADifferentValueIsADifferentAttribute:
    @pytest.mark.parametrize('aid,one,two', PAIRS)
    def test_they_are_not_equal(self, aid, one, two) -> None:
        assert decode(aid, one) != decode(aid, two)

    @pytest.mark.parametrize('aid,one,two', PAIRS)
    def test_and_the_route_comparison_agrees(self, aid, one, two) -> None:
        # what the RIB asks before deciding an announcement is unchanged
        first, second = Attributes(), Attributes()
        first.add(decode(aid, one))
        second.add(decode(aid, two))
        assert not first.sameValuesAs(second)


class TestTheSameValueIsTheSameAttribute:
    """The half a "different values differ" test cannot catch

    An __eq__ answering False to everything satisfies every assertion above. It
    also makes the RIB re-advertise every route on every refresh, which is the
    failure mode vars(self) produced.
    """

    @pytest.mark.parametrize('aid,one,two', PAIRS)
    def test_two_decodes_of_one_payload_are_equal(self, aid, one, two) -> None:
        assert decode(aid, one) == decode(aid, one)

    @pytest.mark.parametrize('aid,one,two', PAIRS)
    def test_and_the_route_comparison_agrees(self, aid, one, two) -> None:
        first, second = Attributes(), Attributes()
        first.add(decode(aid, one))
        second.add(decode(aid, one))
        assert first.sameValuesAs(second)


class TestComparingWithSomethingElse:
    """`attribute == None` answered with an AttributeError

    Every one of these read other.ID, other.aspath or other.ton() with nothing
    checking what `other` was, so the comparison raised instead of answering.
    """

    @pytest.mark.parametrize('aid,one,two', PAIRS)
    @pytest.mark.parametrize('other', [None, 42, 'x', object(), []])
    def test_it_answers_rather_than_raising(self, aid, one, two, other) -> None:
        attribute = decode(aid, one)
        assert (attribute == other) is False
        assert (attribute != other) is True

    def test_across_every_attribute_which_decodes(self) -> None:
        # the parametrised cases above are hand picked; this one sweeps whatever
        # is registered, so a class added later is covered without being listed
        checked = 0
        for aid in sorted(Attribute.attributes_known):
            for payload in (b'', bytes(4), bytes(8), bytes(12)):
                try:
                    value = decode(aid, payload)
                except Exception:
                    continue
                if value is None:
                    continue
                try:
                    assert (value == None) is False  # noqa: E711 - the point is the operator
                    assert (value != None) is True  # noqa: E711
                except RuntimeError:
                    continue  # NextHopSelf refuses to be compared, deliberately
                checked += 1
        assert checked, 'nothing decoded, so this asserted nothing'


class TestAnOverrideDoesNotReintroduceIt:
    """OriginatorID had its own copy of the bug

    Fixing Attribute.__eq__ does not reach a subclass which overrides it, so the
    subclass keeps answering "equal" for every value. This is the assertion that
    says the fix reached the override too.
    """

    def test_the_originator_id_reads_its_address(self) -> None:
        one = decode(ORIGINATOR_ID, bytes([10, 0, 0, 1]))
        two = decode(ORIGINATOR_ID, bytes([9, 9, 9, 9]))
        assert one != two
        assert one == decode(ORIGINATOR_ID, bytes([10, 0, 0, 1]))

    def test_no_registered_class_still_ignores_its_value(self) -> None:
        # a class whose __eq__ is blind to the value answers True for any two
        # instances of itself; find that by comparing decodes of different bytes
        blind = []
        for aid in sorted(Attribute.attributes_known):
            try:
                one = decode(aid, bytes([1, 1, 1, 1] * 3))
                two = decode(aid, bytes([9, 9, 9, 9] * 3))
            except Exception:
                continue
            if one is None or two is None or str(one) == str(two):
                continue
            try:
                if one == two:
                    blind.append(type(one).__name__)
            except RuntimeError:
                continue
        assert not blind, f'these compare equal while rendering differently: {blind}'
