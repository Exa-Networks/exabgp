"""A malformed BGP Prefix-SID attribute is discarded, not answered with a NOTIFICATION.

RFC 8669 section 6 is explicit: a BGP speaker which receives a BGP Prefix-SID attribute it
cannot process "MUST ignore the received BGP Prefix-SID attribute and not advertise it to
other BGP peers", and says in the same breath that this is "equivalent to the 'Attribute
discard' action specified in [RFC7606]".

PrefixSid declared neither TREAT_AS_WITHDRAW nor DISCARD, so both of the ways its decoder
signals malformed input escaped AttributeCollection.parse:

1.  Every Notify raised while walking the TLVs, which reset the session.  A label-index TLV
    declaring a length of 3 rather than 7 is enough.

2.  Worse, the ValueError out of SrGb.__init__ for an SRGB TLV whose value is not
    2 + N*6 bytes.  That is not a decoder result at all: it left Update.unpack_message
    untyped, reached the catch-all in reactor/protocol.py, and came back as
    Notify(1, 0) "can not decode update message" -- a Message Header Error reported for an
    attribute problem, which tells the peer something that is not true about its own
    framing.  TIGER_STYLE 1.1 is the general rule this breaks: peer bytes produce Notify,
    never a Python exception.

Both are fixed the same way as LinkState, which had the identical shape and cites RFC 7752
in its own comment: the attribute carries DISCARD, and the decoder raises Notify rather
than ValueError for what the peer sent.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb
from exabgp.protocol.family import AFI

BGP_PREFIX_SID = int(Attribute.CODE.BGP_PREFIX_SID)
OPTIONAL_TRANSITIVE = 0xC0
WELL_KNOWN_TRANSITIVE = 0x40

IPV4_PREFIX = bytes([24, 10, 0, 0])

LABEL_INDEX_TLV = 1
SRGB_TLV = 3

# A label-index TLV is seven bytes of value (RFC 8669 3.1), an SRGB TLV is 2 + N*6 (3.2).
# Each of these declares a length the decoder cannot parse as that TLV.
MALFORMED_TLVS = [
    # type, declared length, value
    (LABEL_INDEX_TLV, 3, bytes(3)),  # label-index which is not seven bytes
    (SRGB_TLV, 4, bytes(4)),  # SRGB whose value is not 2 + N*6
    (SRGB_TLV, 2 + 6 + 1, bytes(2 + 6 + 1)),  # one entry plus a trailing byte
    (SRGB_TLV, 1, bytes(1)),  # shorter than the flags
]
MALFORMED_IDS = ['label-index-3', 'srgb-4', 'srgb-9', 'srgb-1']


def negotiated() -> Any:
    session = Mock()
    session.asn4 = False
    session.addpath = Mock()
    session.addpath.receive = Mock(return_value=False)
    session.addpath.send = Mock(return_value=False)
    session.required = Mock(return_value=False)
    session.families = []
    session.nexthop = []
    session.msg_size = 4096
    session.direction = Action.ANNOUNCE
    neighbour = Mock()
    neighbour.__getitem__ = Mock(return_value={'aigp': False})
    neighbour.session = Mock()
    neighbour.session.local_address = Mock()
    neighbour.session.local_address.afi = AFI.ipv4
    session.neighbor = neighbour
    session.attribute_cache = None
    session.attribute_cache_packed = b''
    session.attribute_cache_enabled = False
    return session


def prefix_sid(tlv_type: int, declared_length: int, value: bytes) -> bytes:
    """One BGP Prefix-SID attribute carrying a single TLV."""
    tlv = pack('!BH', tlv_type, declared_length) + value
    return bytes([OPTIONAL_TRANSITIVE, BGP_PREFIX_SID, len(tlv)]) + tlv


def update_announcing_one_route(attribute: bytes) -> bytes:
    """An UPDATE announcing IPV4_PREFIX with that attribute and the mandatory ones."""
    attributes = attribute
    attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.ORIGIN, 1]) + bytes(1)
    attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.NEXT_HOP, 4]) + bytes([10, 0, 0, 1])
    attributes += bytes([WELL_KNOWN_TRANSITIVE, Attribute.CODE.AS_PATH, 0])
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes + IPV4_PREFIX


def test_prefix_sid_declares_discard() -> None:
    """RFC 8669 6 names the action, and this flag is how the parser is told about it."""
    assert PrefixSid.DISCARD, 'RFC 8669 6 says attribute discard for a malformed Prefix-SID'
    assert not PrefixSid.TREAT_AS_WITHDRAW, 'RFC 8669 6 says discard the attribute, which leaves the route standing'


@pytest.mark.parametrize('tlv_type,length,value', MALFORMED_TLVS, ids=MALFORMED_IDS)
def test_a_malformed_prefix_sid_is_discarded_and_the_route_survives(tlv_type: int, length: int, value: bytes) -> None:
    """The session stays up, the attribute is dropped, the announcement stands."""
    session = negotiated()

    try:
        parsed = Update.unpack_message(update_announcing_one_route(prefix_sid(tlv_type, length, value)), session).parse(
            session
        )
    except Notify as exc:
        pytest.fail(
            f'a malformed Prefix-SID reset the session (Notify {exc.code}/{exc.subcode}), RFC 8669 6 says discard'
        )

    assert BGP_PREFIX_SID not in parsed.attributes, 'the malformed Prefix-SID was kept'
    assert parsed.announces, 'attribute discard leaves the route standing, it does not withdraw it'
    assert not parsed.withdraws, 'the route was withdrawn, which is treat-as-withdraw rather than discard'


@pytest.mark.parametrize('tlv_type,length,value', MALFORMED_TLVS, ids=MALFORMED_IDS)
def test_nothing_untyped_escapes_the_prefix_sid_decoder(tlv_type: int, length: int, value: bytes) -> None:
    """TIGER_STYLE 1.1: what the peer sends produces Notify, never a Python exception.

    Asserted against the attribute decoder directly rather than through the UPDATE, because
    DISCARD makes the parser swallow both a Notify and a ValueError, so the UPDATE level
    cannot tell one from the other.  The distinction matters: a ValueError escaping any
    other caller of this decoder is still laundered into a Message Header Error.
    """
    tlv = pack('!BH', tlv_type, length) + value

    with pytest.raises(Notify) as raised:
        PrefixSid.unpack_attribute(tlv, negotiated())

    assert raised.value.code == 3, 'a malformed attribute is an UPDATE message error'


def test_a_well_formed_prefix_sid_still_arrives() -> None:
    """The discard must not have swallowed the working case.

    Every assertion above is satisfied by a parser which drops BGP_PREFIX_SID always.
    """
    label_index = pack('!BH', LABEL_INDEX_TLV, 7) + bytes([0, 0, 0, 0, 0, 0x27, 0x10])
    attribute = bytes([OPTIONAL_TRANSITIVE, BGP_PREFIX_SID, len(label_index)]) + label_index
    session = negotiated()

    parsed = Update.unpack_message(update_announcing_one_route(attribute), session).parse(session)

    assert BGP_PREFIX_SID in parsed.attributes, 'a valid Prefix-SID was discarded with the malformed ones'
    assert parsed.announces, 'a valid Prefix-SID lost the route it was attached to'


def test_the_srgb_decoder_reports_the_peer_rather_than_raising_value_error() -> None:
    """The specific shape which reached reactor/protocol.py as Notify(1, 0).

    SrGb.__init__ still raises ValueError, which is right: it guards our own construction
    through make_srgb, where a bad payload is a programming error rather than a peer.  The
    wire path is unpack_attribute, and that is where the peer is judged.
    """
    with pytest.raises(Notify) as raised:
        SrGb.unpack_attribute(bytes(4), length=4)

    assert raised.value.code == 3

    # the internal guard is untouched: make_srgb and direct construction still fail loudly
    with pytest.raises(ValueError, match='SRGB payload'):
        SrGb(b'\x00\x00\x01\x02\x03')
