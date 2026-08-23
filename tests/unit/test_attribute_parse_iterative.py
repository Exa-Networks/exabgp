"""AttributeCollection.parse recursed once per attribute in the section it was decoding.

Every branch of parse() ended with `return self.parse(left, negotiated)`: a tail call
carrying the not-yet-consumed remainder of the attribute section forward.  One stack frame
was spent per attribute, and the wire format allows an attribute as small as three bytes
(flag, type, zero-length value), so a peer did not need anything close to a full 4096 byte
UPDATE to build a stack deep enough to exhaust Python's default recursion limit.

Binary search against this tree found the crossover directly: 997 repeated attributes of
`bytes([0x80, 0xEF, 0x00])` (flag=OPTIONAL, an attribute id nothing registers, zero-length
value) parsed without error, 998 raised `RecursionError`.  That is about 2991 bytes -- far
below the 4096 byte message bound the brief estimated against, and the repeated frames in
the traceback were all `collection.py: return self.parse(left, negotiated)`, not some other
recursive call.  `sys.getrecursionlimit()` is the untouched default of 1000, and this tree
sets no higher limit anywhere.

The test below is deliberately sized to 1200, past the measured crossover, matching the
probe that found it.  In the real reactor path the crossover is lower still: asyncio task
frames, protocol.py and Update.unpack_message are already on the stack before parse() is
entered, so a real peer needs fewer than 997 attributes to trip this, not more.

RecursionError was not crashing the process -- reactor/protocol.py:269 wraps
`Message.unpack(...)` in `except Exception as exc:` (RecursionError is a RuntimeError, so it
is not one of the `KeyboardInterrupt, SystemExit, Notify` re-raised above it) and converts
it to `raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id) from None`.
So the observable failure was a session reset with a misleading cause: a generic decode
Notify with `RecursionError` buried in the debug log, when the attributes were all
individually well formed.  The bound tree's own rule is that peer-controlled input never
recurses; this was the one path that did.
"""

from __future__ import annotations

from unittest.mock import Mock

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection

# flag=OPTIONAL (0x80), aid=0xEF (registered by nothing), length=0 -- the exact probe payload.
UNKNOWN_NON_TRANSITIVE_ATTRIBUTE = bytes([0x80, 0xEF, 0x00])

# Measured crossover is 997 succeeding / 998 failing on a bare call; 1200 is the brief's
# original probe size, comfortably past it and past the lower real-reactor crossover too.
ATTRIBUTE_COUNT = 1200

ORIGIN = int(Attribute.CODE.ORIGIN)
ORIGIN_IGP = bytes([0x40, ORIGIN, 1, 0])


def fake_negotiated() -> Mock:
    """parse() only threads `negotiated` through to Attribute.unpack for known attributes.

    Every attribute this file decodes either ignores it entirely (the unknown ones never
    reach Attribute.unpack) or ignores it in its own unpack_attribute (Origin.from_packet
    takes only the wire bytes), so a bare Mock is sufficient -- this is a recursion-depth
    test, not a negotiation test.
    """
    return Mock()


def test_1200_unknown_attributes_parse_without_recursion_error() -> None:
    """The Step-1 probe payload: past the 997/998 crossover, still inside one UPDATE.

    Every attribute is unknown and non-transitive, so each is individually ignored and the
    resulting collection carries none of them -- the defect under test is purely about the
    call stack, not about what gets decoded.
    """
    data = UNKNOWN_NON_TRANSITIVE_ATTRIBUTE * ATTRIBUTE_COUNT

    attributes = AttributeCollection().parse(data, fake_negotiated())

    assert len(attributes) == 0, 'unknown non-transitive attributes should all be ignored'


def test_origin_survives_among_1100_unknown_attributes() -> None:
    """A real attribute buried in a long run of unknowns must still be decoded and kept.

    This is the case an off-by-one in a hand rolled loop-conversion would break silently:
    it is not enough for the rewrite to merely avoid RecursionError, the attribute that
    was not skipped must still come out the other end.
    """
    half = 550
    data = UNKNOWN_NON_TRANSITIVE_ATTRIBUTE * half + ORIGIN_IGP + UNKNOWN_NON_TRANSITIVE_ATTRIBUTE * half

    attributes = AttributeCollection().parse(data, fake_negotiated())

    assert ORIGIN in attributes, 'ORIGIN was lost while parsing a long run of unknown attributes'
    assert len(attributes) == 1, 'only ORIGIN should have survived; unknowns must still be ignored'
