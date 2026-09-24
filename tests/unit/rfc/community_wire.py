"""Wire helpers shared by the three community attribute RFC test files.

RFC 1997, RFC 4360 and RFC 8092 describe three attributes with the same shape: an
optional transitive attribute whose value is a whole number of fixed width communities.
They therefore fail in the same place, and the tests for all three need the same two
things: a way to wrap a value in an attribute header, and a way to run it through the
real `AttributeCollection.parse` rather than through the individual decoder.

Parsing through the collection is the part which matters.  Every one of these decoders
raises `Notify` on a bad length, and a `Notify` on its own is a session reset.  What turns
it into RFC 7606 treat-as-withdraw is `TREAT_AS_WITHDRAW` on the attribute class, which
only `AttributeCollection.parse` reads.  A test which called `from_packet` directly would
prove the decoder noticed and prove nothing at all about what happens to the session.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection

# Attribute flag bytes, from RFC 4271 section 4.3.  All three community attributes are
# optional transitive, so all three carry 0xC0.
OPTIONAL_TRANSITIVE = 0xC0

TREAT_AS_WITHDRAW = int(Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW)

# The longest value these helpers will build a one byte length header for.
MAX_SHORT_ATTRIBUTE_BYTES = 255


def session() -> Any:
    """A negotiated session with the attribute cache off.

    The cache is keyed on the packed bytes and is a per session object.  Leaving it on
    would let one test's parse answer another test's, which is exactly the class of bug
    `Negotiated.attribute_cache` was moved off the class to stop.
    """
    negotiated = Mock()
    negotiated.asn4 = False
    negotiated.families = []
    negotiated.nexthop = []
    negotiated.msg_size = 4096
    negotiated.direction = Action.ANNOUNCE
    negotiated.attribute_cache = None
    negotiated.attribute_cache_packed = b''
    negotiated.attribute_cache_enabled = False
    return negotiated


def attribute(code: int, value: bytes) -> bytes:
    """One optional transitive attribute carrying `value`, with an honest length byte."""
    assert len(value) <= MAX_SHORT_ATTRIBUTE_BYTES, 'value needs the extended length header'
    return bytes([OPTIONAL_TRANSITIVE, code, len(value)]) + value


def parse(code: int, value: bytes) -> AttributeCollection:
    """Run one attribute through the real attribute section parser."""
    return AttributeCollection().parse(attribute(code, value), session())


def withdrawn(collection: AttributeCollection) -> bool:
    """Did the parser decide this UPDATE takes the treat-as-withdraw approach?"""
    return TREAT_AS_WITHDRAW in collection
