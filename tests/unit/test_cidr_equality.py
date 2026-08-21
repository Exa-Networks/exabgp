"""Two prefixes are the same prefix only if the mask and the bytes both agree.

CIDR underlies every address family, and its equality had no test. Mutation testing turned

    return self.mask == other.mask and self._packed == other._packed

into `or`, which makes 10.0.0.0/24 equal to 10.1.0.0/24, and nothing failed. It also
inverted the isinstance guard in __ne__ with the same silence.

Nothing in the RIB keys on CIDR equality today, so this is not a live defect: it is a
primitive whose meaning nobody had written down, one edit away from being wrong everywhere
at once.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.protocol.family import AFI


def cidr(mask: int, *octets: int) -> CIDR:
    return CIDR(bytes([mask, *octets]), AFI.ipv4)


def test_the_same_prefix_is_equal_to_itself() -> None:
    assert cidr(24, 10, 0, 0) == cidr(24, 10, 0, 0)
    assert not cidr(24, 10, 0, 0) != cidr(24, 10, 0, 0)


def test_a_different_prefix_under_the_same_mask_is_not_equal() -> None:
    """The `and` matters: with `or` these are the same route."""
    assert cidr(24, 10, 0, 0) != cidr(24, 10, 1, 0)
    assert not cidr(24, 10, 0, 0) == cidr(24, 10, 1, 0)


def test_the_same_bytes_under_a_different_mask_are_not_equal() -> None:
    """10.0.0.0/24 and 10.0.0.0/16 are different routes, and one covers the other."""
    assert cidr(24, 10, 0, 0) != cidr(16, 10, 0)
    assert not cidr(24, 10, 0, 0) == cidr(16, 10, 0)


@pytest.mark.parametrize('other', [42, 'ten', None, b'\x18\x0a\x00\x00', object()])
def test_something_which_is_not_a_prefix_is_never_equal(other: object) -> None:
    """__eq__ returns NotImplemented, which Python turns into False, and __ne__ into True.

    The isinstance guard in __ne__ was inverted by mutation testing without a test noticing,
    which would have made a prefix unequal to itself and equal to a string.
    """
    prefix = cidr(24, 10, 0, 0)
    assert not prefix == other
    assert prefix != other


def test_equality_is_symmetric_and_hashable_together() -> None:
    """Equal prefixes must hash together, or a set or dict keyed on them loses entries."""
    first, second = cidr(24, 10, 0, 0), cidr(24, 10, 0, 0)
    assert first == second and second == first
    assert len({first, second}) == 1, 'two equal prefixes are one key'


# The ordering half of the same object.  Session 5.0 found that a __lt__ mutation survived
# its whole suite; on main the operators were worse than mutable, they were inconsistent
# with the equality above, and nothing looked because __eq__ and __hash__ being right is
# what makes the ordering appear fine.  Same pair rule as index()/prefix_index().


def test_the_ordering_agrees_with_equality() -> None:
    """<= and >= cannot both hold for two prefixes __eq__ says are different.

    They did: the operators compared the address bytes alone and ignored the mask, so
    10.0.0.0/24 and 10.0.0.0/25 sorted as one prefix.  bisect and sorted-merge callers
    are entitled to assume an ordering and an equality agree.
    """
    short = CIDR.create_cidr(bytes([10, 0, 0, 0]), 24)
    long = CIDR.create_cidr(bytes([10, 0, 0, 0]), 25)

    assert short != long
    assert not (short <= long and short >= long), 'the ordering calls two different prefixes equal'
    assert (short < long) != (long < short), 'exactly one of the two must be the smaller'


def test_the_address_stays_the_primary_key() -> None:
    """The mask is a tiebreak, not the leading term.

    Update.messages() packs sorted(self.nlris), so this decides the order prefixes go onto
    the wire.  Sorting by mask first would reorder every update a working deployment
    already sends; sorting by address first cannot move anything which already had a
    defined order.
    """
    low_address_long_mask = CIDR.create_cidr(bytes([10, 0, 0, 0]), 32)
    high_address_short_mask = CIDR.create_cidr(bytes([10, 0, 1, 0]), 8)

    assert low_address_long_mask < high_address_short_mask


def test_a_prefix_is_not_ordered_against_something_which_is_not_one() -> None:
    """The data model asks for NotImplemented, which Python turns into TypeError.

    Reaching for other._packed raised AttributeError instead, which is not what any caller
    catches and not what sorted() reports when a list holds the wrong thing.
    """
    prefix = CIDR.create_cidr(bytes([10, 0, 0, 0]), 24)

    for other in (None, 'ten dot zero', 42, object()):
        for operation in (
            lambda o: prefix < o,
            lambda o: prefix <= o,
            lambda o: prefix > o,
            lambda o: prefix >= o,
        ):
            with pytest.raises(TypeError):
                operation(other)


def test_the_ordering_is_a_total_order_over_a_mixed_set() -> None:
    """Sorting must be reproducible, and every pair must be decided.

    A relation which leaves pairs undecided sorts differently depending on the order the
    list arrived in, which for Update.messages() means the bytes on the wire depend on
    dictionary iteration order.
    """
    prefixes = [
        CIDR.create_cidr(bytes([10, 0, 0, 0]), 24),
        CIDR.create_cidr(bytes([10, 0, 0, 0]), 25),
        CIDR.create_cidr(bytes([10, 0, 1, 0]), 24),
        CIDR.create_cidr(bytes([192, 168, 0, 0]), 16),
    ]

    forward = sorted(prefixes)
    backward = sorted(reversed(prefixes))
    assert forward == backward, 'the sort depends on the order the prefixes arrived in'

    for earlier, later in zip(forward, forward[1:]):
        assert earlier < later, 'two entries in a sorted list compare as neither smaller'
