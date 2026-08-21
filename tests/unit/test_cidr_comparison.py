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
