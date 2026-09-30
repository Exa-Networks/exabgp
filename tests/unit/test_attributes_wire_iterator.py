"""The wire container, Attributes, read its headers and values without checking their length.

`Attributes.__iter__` indexed `data[0]`, `data[1]`, `data[2]` and `data[2:4]` straight off
the buffer, and sliced the value to whatever the length field claimed.  A buffer ending
inside a header raised a raw IndexError or struct.error, and a length past the end handed
the attribute fewer bytes than it said it had.  Each now raises Notify 3/1, Malformed
Attribute List, before the read.
"""

from __future__ import annotations


import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import Attributes
from exabgp.bgp.message.open.capability.negotiated import Negotiated

# flag=TRANSITIVE (0x40), ORIGIN, length 1, IGP
ORIGIN = bytes([0x40, 0x01, 0x01, 0x00])


def _attributes(packed: bytes) -> Attributes:
    # ORIGIN ignores negotiated, and every other case raises before Attribute.unpack
    return Attributes(packed, Negotiated.UNSET)


def test_a_well_formed_list_is_iterated() -> None:
    assert [attribute.ID for attribute in _attributes(ORIGIN)] == [Attribute.CODE.ORIGIN]


def test_an_extended_length_attribute_is_iterated() -> None:
    extended = bytes([0x50, 0x01, 0x00, 0x01, 0x00])
    assert [attribute.ID for attribute in _attributes(extended)] == [Attribute.CODE.ORIGIN]


@pytest.mark.parametrize(
    'tail',
    [
        bytes([0x40]),  # a flag and nothing else
        bytes([0x40, 0x01]),  # no length
        bytes([0x50, 0x01, 0x00]),  # an extended length cut after its first byte
        bytes([0x40, 0x01, 0x02, 0x00]),  # a length of two with one byte left
        bytes([0x50, 0x01, 0x01, 0x00, 0x00]),  # an extended length of 256 with one byte left
    ],
)
def test_a_truncated_attribute_is_a_malformed_attribute_list(tail: bytes) -> None:
    with pytest.raises(Notify) as raised:
        list(_attributes(ORIGIN + tail))
    assert (raised.value.code, raised.value.subcode) == (3, 1)
