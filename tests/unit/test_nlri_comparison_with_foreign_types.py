"""An NLRI compared to something that is not an NLRI must not raise.

`__eq__`, `__ne__` and the ordering dunders took `Any` and went straight for
`other.index()`, so `nlri == None` raised AttributeError and `nlri in [1, 2, 3]`
crashed instead of answering False. They now answer NotImplemented and let
Python decide, which is what the protocol asks for.

The ordering between two NLRI is unchanged: it exists so that the NLRI of a
generated update come out in a deterministic order, and index() starts with the
family so two families never interleave.
"""

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI


def _inet(packed: bytes) -> INET:
    nlri, _ = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, memoryview(packed), Action.ANNOUNCE, False, Negotiated.UNSET)
    assert isinstance(nlri, INET)
    return nlri


FOREIGN = [3, None, 'a string', object()]


@pytest.mark.parametrize('other', FOREIGN)
def test_equality_with_a_foreign_type_is_false_not_an_exception(other):
    nlri = _inet(b'\x18\x0a\x00\x00')
    assert (nlri == other) is False
    assert (nlri != other) is True


def test_membership_of_a_list_of_foreign_values_does_not_raise():
    nlri = _inet(b'\x18\x0a\x00\x00')
    assert nlri not in [1, 2, 3]


@pytest.mark.parametrize('other', FOREIGN)
def test_ordering_against_a_foreign_type_raises_type_error(other):
    nlri = _inet(b'\x18\x0a\x00\x00')
    for compare in (
        lambda: nlri < other,
        lambda: nlri <= other,
        lambda: nlri > other,
        lambda: nlri >= other,
    ):
        with pytest.raises(TypeError):
            compare()


def test_ordering_between_nlri_stays_deterministic():
    low = _inet(b'\x18\x0a\x00\x00')
    high = _inet(b'\x18\x0a\x00\x01')
    assert low < high
    assert low <= high
    assert high > low
    assert high >= low
    assert sorted([high, low]) == [low, high]
