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


def _ip(octet):
    return bytes([octet, octet, octet, octet])


def _aspath(asn):
    return bytes([2, 1]) + pack('!L', asn)


# The floor is a ratchet: raise it when a new attribute gains a seed, never lower
# it to make a red sweep go green.
SWEEP_FLOOR = 18

# Shaped payloads, one pair per attribute, chosen so BOTH decode to the attribute
# itself and render differently. Deliberately absent:
#   atomic-aggregate  carries no value at all, so two of them are equal and right
#   mp-reach-nlri     their payload is a whole NLRI encoding; they are covered by
#   mp-unreach-nlri   the round trip tests rather than by a two byte seed here
SHAPED_SEEDS = {
    1: (bytes([0]), bytes([1])),  # origin
    2: (_aspath(64500), _aspath(64501)),  # as-path
    3: (_ip(10), _ip(9)),  # next-hop
    4: (pack('!L', 10), pack('!L', 99)),  # med
    5: (pack('!L', 100), pack('!L', 200)),  # local-preference
    7: (pack('!L', 64500) + _ip(10), pack('!L', 64501) + _ip(9)),  # aggregator
    8: (pack('!L', 0xFFFF0001), pack('!L', 0xFFFF0002)),  # community
    9: (_ip(10), _ip(9)),  # originator-id
    10: (_ip(10), _ip(9)),  # cluster-list
    16: (bytes([0, 2]) + pack('!HL', 1, 1), bytes([0, 2]) + pack('!HL', 2, 2)),  # extended-community
    17: (_aspath(64500), _aspath(64501)),  # as4-path
    18: (pack('!L', 64500) + _ip(10), pack('!L', 64501) + _ip(9)),  # as4-aggregator
    22: (bytes([1, 1, 1, 1] * 3), bytes([9, 9, 9, 9] * 3)),  # pmsi-tunnel
    25: (bytes([0, 2]) + b'\x00' * 16 + pack('!H', 1), bytes([0, 2]) + b'\x00' * 16 + pack('!H', 2)),
    26: (bytes([1]) + pack('!H', 11) + pack('!Q', 10), bytes([1]) + pack('!H', 11) + pack('!Q', 99)),  # aigp
    29: (pack('!HH', 1028, 4) + _ip(10), pack('!HH', 1028, 4) + _ip(9)),  # bgp-ls
    32: (pack('!LLL', 1, 1, 1), pack('!LLL', 9, 9, 9)),  # large-community
    40: (bytes([1, 0, 7]) + b'\x00' * 7, bytes([1, 0, 7]) + b'\x00' * 6 + b'\x09'),  # bgp-prefix-sid
}

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
        """Sweep the registry, not a hand picked list

        A class whose __eq__ is blind to the value answers True for any two
        instances of itself, so decode two different payloads and compare.

        The seeds have to be SHAPED. A blob of repeated bytes is the wrong shape
        for most attributes: they raise Notify before a value exists, and the
        sweep then reports no failures because it built almost nothing. Twelve
        repeated bytes reached 5 of the 21 registered attributes and looked
        exactly as green as this does.
        """
        blind, reached = [], []
        for aid in sorted(Attribute.attributes_known):
            seeds = SHAPED_SEEDS.get(int(aid))
            if seeds is None:
                continue
            try:
                one, two = decode(aid, seeds[0]), decode(aid, seeds[1])
            except Exception:
                continue
            if one is None or two is None or str(one) == str(two):
                continue
            reached.append(Attribute.CODE.names.get(aid, str(aid)))
            try:
                if one == two:
                    blind.append(type(one).__name__)
            except RuntimeError:
                continue

        assert not blind, f'these compare equal while rendering differently: {blind}'
        # a sweep which builds nothing reports no failures, so the coverage is
        # asserted as well as the result
        assert len(reached) >= SWEEP_FLOOR, f'only reached {len(reached)} attributes: {reached}'

    def test_the_sweep_reaches_what_it_claims(self) -> None:
        """The seeds must decode to the attribute they are seeds for

        AIGP is the cautionary one: it decodes to a Discard unless the neighbour
        enables it, and two Discards are equal for a reason which is correct and
        says nothing whatever about AIGP. A sweep counting that as coverage is
        counting a class it never compared.
        """
        wrong = []
        for aid, seeds in sorted(SHAPED_SEEDS.items()):
            try:
                value = decode(aid, seeds[0])
            except Exception as exc:
                wrong.append(f'{aid} raised {type(exc).__name__}')
                continue
            if value is None:
                wrong.append(f'{aid} decoded to None')
                continue
            if type(value).__name__ in ('Discard', 'TreatAsWithdraw', 'GenericAttribute'):
                wrong.append(f'{aid} decoded to {type(value).__name__}, not the attribute itself')
        assert not wrong, wrong
