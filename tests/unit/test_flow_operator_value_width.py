"""A FlowSpec protocol match wider than one octet took the session down and kept it down.

RFC 8955 4.2.1.1 gives the numeric operator a two bit `len` field: "The length of the value
field for this operator given as (1 << len). This encodes 1 (len=00), 2 (len=01), 4 (len=10),
and 8 (len=11) octets."  All four are legal on the wire for every numeric component, and which
one a peer chooses is its business, not ours.

`FlowIPProtocol` and `FlowNextHeader` decoded with `ord`, which reads exactly one byte and
raises `TypeError` on anything else.  `Flow.unpack_nlri` catches `Notify`, `ValueError` and
`IndexError`, so the `TypeError` walked out of `Update.unpack_message` and reached the
reactor's "UNHANDLED PROBLEMS" clause, which logs a traceback and calls `_reset()`.  No
NOTIFICATION is sent, so the peer has no idea what it did, sends the same UPDATE on the next
attempt, and the peering never comes up.  Every other numeric component already used the
width-agnostic `_number`; these two were the exception.

The width we ENCODE is a separate question and is unchanged: `IOperationByte` still packs a
one octet value, which is what the tests in `tests/unit/test_flowspec_rfc8955_8956.py` pin.
"""

from __future__ import annotations

import importlib.util
import pathlib
from struct import pack
from typing import Any

import pytest

from exabgp.bgp.message import Action, Update
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.protocol.family import AFI, SAFI

# RFC 8955 4.2.1.1: the operator's len field encodes 1 << len octets
WIDTHS = {1: 0x00, 2: 0x10, 4: 0x20, 8: 0x30}

END_OF_LIST = 0x80
EQUAL = 0x01

COMPONENT_PROTOCOL = 0x03
COMPONENT_NEXT_HEADER = 0x03
COMPONENT_PORT = 0x04

TCP = 6


@pytest.fixture(scope='module')
def session() -> Any:
    """A negotiated session, so a well formed FlowSpec NLRI really does decode."""
    spec = importlib.util.spec_from_file_location('decode_fixtures', pathlib.Path(__file__).parent / 'test_decode.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    neighbor = module.FakeNeighbor()
    capabilities = Capabilities().new(neighbor, False)
    capabilities[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
    negotiated = Negotiated(neighbor)
    negotiated.sent(Open(Version(4), ASN(neighbor['local-as']), HoldTime(180), RouterID('10.0.0.1'), capabilities))
    negotiated.received(Open(Version(4), ASN(neighbor['peer-as']), HoldTime(180), RouterID('10.0.0.2'), capabilities))
    return negotiated


def rules(component: int, width: int, value: int) -> bytes:
    """One numeric component, matched for equality, announced in the width given."""
    operator = END_OF_LIST | WIDTHS[width] | EQUAL
    return bytes([component, operator]) + value.to_bytes(width, 'big')


def flow_update(afi: AFI, safi: SAFI, payload: bytes) -> bytes:
    """A whole UPDATE carrying one FlowSpec NLRI through MP_REACH_NLRI."""
    nlri = bytes([len(payload)]) + payload
    value = pack('!HB', afi, safi) + bytes([0]) + bytes([0]) + nlri
    attribute = bytes([0x80, int(Attribute.CODE.MP_REACH_NLRI), len(value)]) + value
    return pack('!H', 0) + pack('!H', len(attribute)) + attribute


@pytest.mark.parametrize('width', sorted(WIDTHS), ids=[f'{n}-octet' for n in sorted(WIDTHS)])
def test_a_protocol_match_of_any_legal_width_decodes(width: int, session: Any) -> None:
    """A TypeError here is the defect: it resets the session and sends no NOTIFICATION."""
    update = Update.unpack_message(
        flow_update(AFI.ipv4, SAFI.flow_ip, rules(COMPONENT_PROTOCOL, width, TCP)), Direction.IN, session
    )

    assert len(update.nlris) == 1
    assert 'protocol' in str(update.nlris[0])
    assert 'tcp' in str(update.nlris[0])


@pytest.mark.parametrize('width', sorted(WIDTHS), ids=[f'{n}-octet' for n in sorted(WIDTHS)])
def test_a_next_header_match_of_any_legal_width_decodes(width: int, session: Any) -> None:
    """The IPv6 component is a separate class with the same decoder, so it is asked separately."""
    update = Update.unpack_message(
        flow_update(AFI.ipv6, SAFI.flow_ip, rules(COMPONENT_NEXT_HEADER, width, TCP)), Direction.IN, session
    )

    assert len(update.nlris) == 1
    assert 'next-header' in str(update.nlris[0])


@pytest.mark.parametrize('width', sorted(WIDTHS), ids=[f'{n}-octet' for n in sorted(WIDTHS)])
def test_the_decoder_reads_the_whole_field_and_not_its_leading_octet(width: int, session: Any) -> None:
    """The value is big endian, so a decoder reading data[0] would answer 0, not 47.

    GRE is 47.  Announced in two, four or eight octets the significant byte is the LAST one, so
    this is what separates "reads the field" from "reads the first byte of it".
    """
    gre = 47

    update = Update.unpack_message(
        flow_update(AFI.ipv4, SAFI.flow_ip, rules(COMPONENT_PROTOCOL, width, gre)), Direction.IN, session
    )

    assert 'gre' in str(update.nlris[0]), f'a {width} octet value did not decode to protocol {gre}'


@pytest.mark.parametrize('width', sorted(WIDTHS), ids=[f'{n}-octet' for n in sorted(WIDTHS)])
def test_a_port_match_of_any_legal_width_still_decodes(width: int, session: Any) -> None:
    """The negative space: the components which already used _number must be untouched."""
    update = Update.unpack_message(
        flow_update(AFI.ipv4, SAFI.flow_ip, rules(COMPONENT_PORT, width, 179)), Direction.IN, session
    )

    assert 'port' in str(update.nlris[0])
    assert '179' in str(update.nlris[0])


def test_a_truncated_value_is_still_refused() -> None:
    """A wider decoder must not have made the decoder accept less than the operator claims."""
    operator = END_OF_LIST | WIDTHS[4] | EQUAL
    payload = bytes([COMPONENT_PROTOCOL, operator]) + bytes(2)

    nlri, _left = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, bytes([len(payload)]) + payload, Action.ANNOUNCE, None)

    assert nlri is None or 'protocol' not in str(nlri), 'four declared octets with two present was accepted'


def test_one_octet_is_what_we_still_encode() -> None:
    """RFC 8955 lets a peer choose; it does not oblige us to change what we send."""
    payload = rules(COMPONENT_PROTOCOL, 1, TCP)

    nlri, _left = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, bytes([len(payload)]) + payload, Action.ANNOUNCE, None)

    assert nlri.pack_nlri()[1:] == payload, 'the encoded width changed'


def test_a_notify_is_not_how_a_wide_value_is_answered(session: Any) -> None:
    """Refusing the wide form with a NOTIFICATION would satisfy 'no TypeError' and be wrong."""
    for width in sorted(WIDTHS):
        try:
            Update.unpack_message(
                flow_update(AFI.ipv4, SAFI.flow_ip, rules(COMPONENT_PROTOCOL, width, TCP)), Direction.IN, session
            )
        except Notify as raised:  # noqa: PERF203 - the loop body is the assertion
            pytest.fail(f'a {width} octet value was refused with Notify {raised.code}/{raised.subcode}')
