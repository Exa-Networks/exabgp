"""No attribute a peer sends may leave Update.unpack_message as a raw exception.

AttributeCollection.parse catches Notify, IndexError and ValueError out of a decoder and
turns them into what RFC 7606 asks for, using the TREAT_AS_WITHDRAW and DISCARD flags on
the class.  A class which signals a malformed attribute with ValueError but declares
neither flag falls through to `raise exc`, and the exception reaches the reactor, where the
catch-all reports it as "can not decode update message" and resets the session over a route
the RFC says to withdraw.

Four classes were in that state and are reachable from the wire: ORIGINATOR_ID,
CLUSTER_LIST, PMSI_TUNNEL and AIGP.  RFC 7606 2 prefers treat-as-withdraw and reserves
attribute discard for an attribute with no effect on route selection; all four affect it,
CLUSTER_LIST most obviously, since it is the reflector loop check.

A fifth escaped past the decoders entirely.  UpdateCollection._parse_payload turned the
NEXT_HOP attribute into an address with `if len(packed) == 4 ... else IPv6(packed)`, and
NextHop.UNSET carries no address at all, so its empty bytes reached inet_ntop.  No flag can
catch that one: it is in the semantic transformation, downstream of every decoder.

This sweep is the guard.  It is deliberately not a list of the five: an attribute added
tomorrow is covered the day it is registered.
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
from exabgp.protocol.family import AFI

# every combination of the flag bits a peer chooses, including EXTENDED_LENGTH, which
# changes how the length itself is read and is where the NEXT_HOP case came from
FLAGS = [0x00, 0x40, 0x50, 0x80, 0xC0, 0xD0]
SIZES = list(range(0, 20)) + [24, 32, 64, 255]

# one real prefix, so the UPDATE is a route rather than an End-of-RIB
IPV4_PREFIX = bytes([24, 10, 0, 0])

CODES = sorted({code for code, flag in Attribute.registered_attributes})
IDS = [f'{code}-{Attribute.CODE.name(code)}' for code in CODES]


def session() -> Any:
    """The session state the decode and the transformation both read.

    aigp is enabled, or AIGP decodes to a Discard and this sweep never reaches it: the same
    trap as a corpus which cannot reach the code it claims to cover.
    """
    negotiated = Mock()
    negotiated.asn4 = False
    negotiated.addpath = Mock()
    negotiated.addpath.receive = Mock(return_value=False)
    negotiated.addpath.send = Mock(return_value=False)
    negotiated.required = Mock(return_value=False)
    negotiated.families = []
    negotiated.nexthop = []
    negotiated.msg_size = 4096
    negotiated.direction = Action.ANNOUNCE

    neighbour = Mock()
    neighbour.__getitem__ = Mock(return_value={'aigp': True})
    neighbour.session = Mock()
    neighbour.session.local_address = Mock()
    neighbour.session.local_address.afi = AFI.ipv4
    negotiated.neighbor = neighbour
    return negotiated


def update_with(flag: int, code: int, size: int) -> bytes:
    attribute = bytes([flag, code, size]) + bytes(size)
    return pack('!H', 0) + pack('!H', len(attribute)) + attribute + IPV4_PREFIX


@pytest.mark.parametrize('code', CODES, ids=IDS)
def test_no_attribute_leaves_the_parser_as_a_raw_exception(code: int) -> None:
    """Notify, or a parsed update.  Anything else reaches the reactor untyped.

    Both halves are exercised: unpack_message decodes the wire container, and parse()
    builds the semantic one, which is where the NEXT_HOP case failed.  A test which only
    called unpack_message would have reported this file clean.
    """
    escaped = []
    for flag in FLAGS:
        for size in SIZES:
            try:
                Update.unpack_message(update_with(flag, code, size), session()).parse(session())
            except Notify:
                continue
            except Exception as exc:  # noqa: BLE001 - the whole point is to catch what escapes
                escaped.append((hex(flag), size, type(exc).__name__, str(exc)[:60]))

    assert not escaped, f'attribute {code} leaked {len(escaped)} raw exception(s), first: {escaped[0]}'


@pytest.mark.parametrize('code', CODES, ids=IDS)
def test_the_sweep_reaches_the_attribute_it_names(code: int) -> None:
    """A decoder no input reaches reports no failures.

    Reaching it means the parse got far enough to answer, either with an update or with a
    Notify, for at least one of the flag and size combinations above.
    """
    answered = 0
    for flag in FLAGS:
        for size in SIZES:
            try:
                Update.unpack_message(update_with(flag, code, size), session()).parse(session())
                answered += 1
            except Notify:
                answered += 1
            except Exception:  # noqa: BLE001 - counted by the test above, not here
                continue

    assert answered, f'no input reached attribute {code}, so this pins nothing about it'


def test_a_next_hop_which_is_unset_does_not_become_an_address() -> None:
    """The case a flag cannot catch, pinned on its own.

    NextHop.UNSET is the sentinel for "this update carries no next hop".  The branch which
    turned a NEXT_HOP attribute into an address treated every length but four as sixteen,
    so the sentinel's empty bytes went to inet_ntop and came back as a ValueError from the
    semantic transformation, past every decoder and every RFC 7606 flag.
    """
    from exabgp.bgp.message.update.attribute.nexthop import NextHop

    assert len(NextHop.UNSET._packed) == 0, 'the sentinel now carries bytes, so this pins nothing'

    # flag 0x50 sets EXTENDED_LENGTH, which is how the sentinel reached the transformation
    parsed = Update.unpack_message(update_with(0x50, int(Attribute.CODE.NEXT_HOP), 1), session()).parse(session())

    assert parsed is not None
