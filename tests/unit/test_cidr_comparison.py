#!/usr/bin/env python3
# encoding: utf-8

"""What it means for two prefixes to be equal, written down

CIDR is a primitive the rest of the code reasons with, and nothing said what its
comparisons mean. Every one of these mutations passed the whole suite:

    __eq__     `and` -> `or`      making 10.0.0.0/24 equal 10.1.0.0/24
    __ne__     `or`  -> `and`     making a prefix unequal to itself
    __hash__   dropping the mask  making /24 and /25 collide in a dict
    __lt__     inverted           reversing the order NLRIs are packed in, since
                                  Update.messages() sorts them

Found by the session on main, whose mutation testing surfaced the first two.
Testing showed the other two were equally unheld here.

Comparing with a non-CIDR also raised AttributeError rather than returning
False, so `cidr == None` threw and a mixed collection could not be searched.
"""

import pytest

from exabgp.bgp.message.update.nlri.cidr import CIDR

BASE = CIDR(b'\x0a\x00\x00\x00', 24)
SAME = CIDR(b'\x0a\x00\x00\x00', 24)
OTHER_PREFIX = CIDR(b'\x0a\x01\x00\x00', 24)
OTHER_MASK = CIDR(b'\x0a\x00\x00\x00', 25)


class TestEquality:
    def test_the_same_prefix_and_mask_are_equal(self) -> None:
        assert BASE == SAME

    def test_a_different_prefix_is_not(self) -> None:
        # `and` -> `or` makes this pass
        assert BASE != OTHER_PREFIX
        assert not BASE == OTHER_PREFIX

    def test_a_different_mask_is_not(self) -> None:
        assert BASE != OTHER_MASK
        assert not BASE == OTHER_MASK

    def test_ne_is_exactly_the_negation_of_eq(self) -> None:
        # the two used to be written out separately, which is how they drift
        for left in (BASE, OTHER_PREFIX, OTHER_MASK):
            for right in (BASE, SAME, OTHER_PREFIX, OTHER_MASK):
                assert (left == right) is not (left != right)


class TestComparingWithSomethingElse:
    """The data model says return NotImplemented, not raise"""

    @pytest.mark.parametrize('other', [None, 'a string', 7, b'bytes', object()])
    def test_equality_does_not_raise(self, other) -> None:
        assert (BASE == other) is False
        assert (BASE != other) is True

    def test_a_mixed_collection_can_be_searched(self) -> None:
        assert BASE in [None, 'x', SAME]

    @pytest.mark.parametrize('other', [None, 'a string', 7])
    def test_ordering_refuses_rather_than_guessing(self, other) -> None:
        with pytest.raises(TypeError):
            BASE < other


class TestHashing:
    def test_equal_prefixes_hash_equal(self) -> None:
        assert hash(BASE) == hash(SAME)

    def test_the_mask_is_part_of_the_hash(self) -> None:
        # dropping it collides /24 with /25 in every dict and set
        assert hash(BASE) != hash(OTHER_MASK)

    def test_a_set_keeps_them_apart(self) -> None:
        assert len({BASE, SAME, OTHER_MASK, OTHER_PREFIX}) == 3


class TestOrdering:
    """Update.messages() sorts the NLRIs, so this decides the order on the wire"""

    def test_a_lower_prefix_sorts_first(self) -> None:
        assert BASE < OTHER_PREFIX
        assert not OTHER_PREFIX < BASE

    def test_sorting_is_by_prefix(self) -> None:
        ordered = sorted([OTHER_PREFIX, BASE])
        assert ordered[0] == BASE

    def test_the_four_operators_agree(self) -> None:
        assert BASE <= SAME and BASE >= SAME
        assert BASE < OTHER_PREFIX and BASE <= OTHER_PREFIX
        assert OTHER_PREFIX > BASE and OTHER_PREFIX >= BASE


class TestOrderingAgreesWithEquality:
    """Unequal prefixes must not compare equal for ordering

    The operators compared self._packed and nothing else, so 10.0.0.0/24 and
    10.0.0.0/25 hold the same four address bytes and answered:

        a == b   False        the mask is part of equality and of the hash
        a <  b   False
        b <  a   False        neither sorts first
        a <= b   True
        b <= a   True         each is "not greater" than the other

    An ordering which disagrees with equality is not a total order, and every
    bisect and sorted-merge caller is entitled to assume it is one. Update.messages()
    packs sorted(self.nlris), so on the wire two prefixes differing only in mask came
    out in whatever order the list already held them.

    Fixed by giving the operators a key of (address, mask). The address stays the
    primary component, so nothing which already had a defined order moves; the mask
    is only a tiebreak. Ported from the session working main, where the same defect
    was found by mutation testing rather than by reading the operators.
    """

    NARROW = CIDR(bytes([10, 0, 0, 0]), 25)

    def test_the_mask_breaks_the_tie(self) -> None:
        assert BASE < self.NARROW
        assert not self.NARROW < BASE

    def test_exactly_one_direction_holds(self) -> None:
        # the assertion the old code failed: both were False
        assert (BASE < self.NARROW) != (self.NARROW < BASE)

    def test_le_is_not_true_both_ways(self) -> None:
        assert BASE <= self.NARROW
        assert not self.NARROW <= BASE

    def test_sorting_is_stable_whichever_order_it_is_given(self) -> None:
        first = [str(_) for _ in sorted([BASE, self.NARROW])]
        second = [str(_) for _ in sorted([self.NARROW, BASE])]
        assert first == second, 'the order depended on the input order, so it is not an order'

    def test_the_address_is_still_the_primary_key(self) -> None:
        # the mask must be a TIEBREAK: a lower address with a wider mask still
        # sorts before a higher address, or this reordered the wire
        lower = CIDR(bytes([9, 0, 0, 0]), 8)
        assert lower < BASE
        assert sorted([BASE, lower])[0] == lower

    def test_equality_still_disagrees_where_it_should(self) -> None:
        # a key which folded the mask in would make these equal, which is the
        # opposite defect and passes every assertion above
        assert BASE != self.NARROW
        assert hash(BASE) != hash(self.NARROW)
