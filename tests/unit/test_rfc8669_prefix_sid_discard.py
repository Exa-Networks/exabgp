"""RFC 8669 section 6 says a BGP Prefix-SID we cannot process costs the attribute, not the peering.

    "A BGP Prefix-SID attribute that is not valid ... MUST be considered to be
    'malformed' and the 'Attribute Discard' action of [RFC7606] MUST be applied."

Attribute discard, not treat-as-withdraw: what a malformed Prefix-SID loses is the label
information, not the reachability the route carries, so the route stands and the
attribute goes.  `Attributes.DISCARD` is the list this branch reads to decide that, and
BGP_PREFIX_SID was not on it, so every way the decoder reports malformed input escaped
`Attributes.parse` instead.

Three shapes, and section 6 names all three:

  * a TLV whose length is outside the range the section gives, here a Label-Index
    declaring 3 where 3.1 fixes it at 7.  The decoder raises Notify(3, 5) and it used to
    reach the peer as a NOTIFICATION.
  * an SRGB TLV whose value is not 2 + N*6 bytes.  `SrGb.unpack` did not check, it just
    walked off the end of the buffer, and `struct.error` is not a decoder result at all:
    it left `Update.unpack_message` untyped and came back to the peer from the catch-all
    in reactor/protocol.py as Notify(1, 0) "can not decode update message", a Message
    Header Error for an attribute fault, which tells the peer something untrue about its
    own framing.
  * "not meeting the minimum attribute length requirement", i.e. an empty attribute.
    The generic `length == 0 and aid not in VALID_ZERO` rule in `Attributes.parse` caught
    this one before the DISCARD list was ever consulted and made it treat-as-withdraw, so
    the route was withdrawn where the section says keep the route and drop the attribute.

The third needed a pair of changes rather than one, and the pairing is the point.
Honouring DISCARD inside the generic zero-length rule would also flip AGGREGATOR and
AS4_PATH from withdraw to discard, an unrequested change to two attributes this says
nothing about.  Putting BGP_PREFIX_SID in VALID_ZERO alone would make an empty Prefix-SID
*accepted*, which the section also forbids.  So VALID_ZERO takes the decision away from
the generic rule and the decoder then refuses the empty attribute itself, which routes it
through DISCARD like the other two.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb

OPTIONAL_TRANSITIVE = 0xC0

# a Label-Index TLV (type 1) declaring a 3 byte value where RFC 8669 3.1 fixes it at 7
LABEL_INDEX_WRONG_LENGTH = bytes.fromhex('01' '0003' '000001')

# an Originator SRGB TLV (type 3) whose value is 4 bytes, which is not 2 + N*6
SRGB_WRONG_LENGTH = bytes.fromhex('03' '0004' '00000102')

MALFORMED = [
    ('label-index of the wrong length', LABEL_INDEX_WRONG_LENGTH),
    ('srgb of the wrong length', SRGB_WRONG_LENGTH),
    ('no tlv at all', b''),
]


@pytest.fixture(autouse=True)
def _logger() -> Any:
    """The parser logs every attribute it sees, and the logger is not set up under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


def negotiated() -> Any:
    """The session state the decoders read."""
    session = Mock()
    session.asn4 = False
    session.families = []
    session.nexthop = []
    session.msg_size = 4096

    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    session.neighbor = neighbor
    return session


def prefix_sid_attribute(value: bytes) -> bytes:
    return bytes([OPTIONAL_TRANSITIVE, Attribute.CODE.BGP_PREFIX_SID, len(value)]) + value


@pytest.mark.parametrize('description,value', MALFORMED, ids=[name for name, _ in MALFORMED])
def test_a_malformed_prefix_sid_is_discarded_not_notified(description: str, value: bytes) -> None:
    """The session survives and the parser asks for a discard, so the route stands."""
    try:
        parsed = Attributes.unpack(prefix_sid_attribute(value), Direction.IN, negotiated())
    except Notify as exc:
        pytest.fail(
            f'a Prefix-SID with {description} resets the session (Notify {exc.code}/{exc.subcode}), '
            f'RFC 8669 section 6 says attribute discard'
        )

    assert Attribute.CODE.BGP_PREFIX_SID not in parsed, 'the malformed Prefix-SID was kept'
    assert (
        Attribute.CODE.INTERNAL_DISCARD in parsed
    ), f'a Prefix-SID with {description} did not ask for a discard, RFC 8669 section 6 says it must'
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in parsed, (
        f'a Prefix-SID with {description} withdrew the route; RFC 8669 section 6 loses the label '
        f'information, not the reachability'
    )


@pytest.mark.parametrize('description,value', MALFORMED, ids=[name for name, _ in MALFORMED])
def test_the_decoder_reports_malformed_bytes_as_a_notify(description: str, value: bytes) -> None:
    """Peer bytes produce a Notify and never a Python exception.

    Notify is what `Attributes.parse` knows how to turn into a discard.  Anything else
    walks past it, out of `Update.unpack_message`, and is answered from the catch-all in
    reactor/protocol.py with a code about the message header rather than the attribute.
    """
    with pytest.raises(Notify):
        PrefixSid.unpack(value, Direction.IN, negotiated())


def test_srgb_refuses_a_value_which_is_not_two_plus_a_multiple_of_six() -> None:
    """RFC 8669 3.2: two octets of flags then one or more six octet ranges."""
    with pytest.raises(Notify):
        SrGb.unpack(SRGB_WRONG_LENGTH[3:], len(SRGB_WRONG_LENGTH) - 3)


def test_a_well_formed_prefix_sid_still_decodes() -> None:
    """Otherwise every assertion above is satisfied by a decoder which refuses everything."""
    label_index = bytes.fromhex('01' '0007' '00' '0000' '00000064')
    srgb = bytes.fromhex('03' '0008' '0000' '000064' '00000a')
    parsed = Attributes.unpack(prefix_sid_attribute(label_index + srgb), Direction.IN, negotiated())

    assert Attribute.CODE.BGP_PREFIX_SID in parsed, 'a sound Prefix-SID was dropped'
    assert Attribute.CODE.INTERNAL_DISCARD not in parsed
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in parsed
