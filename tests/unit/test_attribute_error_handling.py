"""No attribute a peer sends may leave the attribute parser as a raw exception.

`Attributes.parse` catches `Notify` and `IndexError` out of a decoder and turns them into
what RFC 7606 asks for, using the `TREAT_AS_WITHDRAW` and `DISCARD` tuples on the class.
Anything else walks out of `Attributes.unpack`, out of `Update.unpack_message`, and reaches
the reactor's catch-all, which reports it as "can not decode update message" and drops the
adjacency over a route the RFC says to withdraw.

This is the sweep which found the length overrun pinned in
`tests/unit/test_attribute_length_overrun.py`: `NextHop.unpack` answered `NoNextHop` for an
empty buffer, which is not an attribute, and `Attributes.add` read `.ID` off it.  No RFC 7606
flag can catch that one, because it is not raised by a decoder.

It is deliberately not a list of the attributes which were broken.  An attribute registered
tomorrow is covered the day it is registered, which is the only version of this test worth
having: the four classes main found in this state were found by a sweep, not by review.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes

# every combination of the flag bits a peer chooses, including EXTENDED_LENGTH, which
# changes how the length itself is read and is where the NoNextHop case came from
FLAGS = [0x00, 0x40, 0x50, 0x80, 0xC0, 0xD0]
SIZES = list(range(0, 20)) + [24, 32, 64, 255]

# one real prefix, so the UPDATE is a route rather than an End-of-RIB
IPV4_PREFIX = bytes([24, 10, 0, 0])

CODES = sorted({code for code, _flag in Attribute.registered_attributes})
IDS = [f'{code}-{Attribute.CODE.names.get(code, "unset")}' for code in CODES]

# a ratchet: raise it as attributes are registered, never lower it
MIN_ATTRIBUTE_CODES = 21


@pytest.fixture(autouse=True)
def _logger() -> Any:
    """The parser logs every attribute it sees, and the logger is not set up under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


@pytest.fixture(autouse=True)
def _no_parse_cache() -> Any:
    """Attributes memoises the last parse on the class, so one test would feed the next."""
    Attributes.cached = None
    Attributes.previous = ''
    yield
    Attributes.cached = None
    Attributes.previous = ''


def session() -> Any:
    """The session state the decoders read.

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
    neighbour = Mock()
    neighbour.__getitem__ = Mock(return_value={'aigp': True})
    negotiated.neighbor = neighbour
    return negotiated


def update_with(flag: int, code: int, size: int) -> bytes:
    attribute = bytes([flag, code, size]) + bytes(size)
    return pack('!H', 0) + pack('!H', len(attribute)) + attribute + IPV4_PREFIX


@pytest.mark.parametrize('code', CODES, ids=IDS)
def test_no_attribute_leaves_the_parser_as_a_raw_exception(code: int) -> None:
    """A Notify, or a parsed update.  Anything else reaches the reactor untyped."""
    escaped = []
    for flag in FLAGS:
        for size in SIZES:
            try:
                Update.unpack_message(update_with(flag, code, size), Direction.IN, session())
            except Notify:
                continue
            except Exception as exc:  # noqa: BLE001 - the whole point is to catch what escapes
                escaped.append((hex(flag), size, type(exc).__name__, str(exc)[:60]))

    assert not escaped, f'attribute {code} leaked {len(escaped)} raw exception(s), first: {escaped[0]}'


@pytest.mark.parametrize('code', CODES, ids=IDS)
@pytest.mark.registry_floor
def test_the_sweep_reaches_the_attribute_it_names(code: int) -> None:
    """A decoder no input reaches reports no failures.

    Reaching it means the parse got far enough to answer, either with an update or with a
    Notify, for at least one of the flag and size combinations above.
    """
    answered = 0
    for flag in FLAGS:
        for size in SIZES:
            try:
                Update.unpack_message(update_with(flag, code, size), Direction.IN, session())
                answered += 1
            except Notify:
                answered += 1
            except Exception:  # noqa: BLE001 - counted by the test above, not here
                continue

    assert answered, f'no input reached attribute {code}, so this pins nothing about it'


@pytest.mark.registry_floor
def test_the_registry_this_file_parametrises_from_is_whole() -> None:
    """A parametrised sweep does not fail on a thin registry, it shrinks.

    Both tests here are per attribute code, and the codes come from the registry, so a
    registry holding three of them runs three parameters and reports success.  A summary
    line reads the same at 42 tests as at 6.
    """
    assert (
        len(CODES) >= MIN_ATTRIBUTE_CODES
    ), f'only {len(CODES)} attribute codes are registered, so this file sweeps a fraction of them'
