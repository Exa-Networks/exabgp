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
