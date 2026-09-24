"""Every registered decoder must answer malformed peer input with Notify, and nothing else.

`Notify` is the one exception the session knows how to handle: the reactor turns it into a
NOTIFICATION, tells the peer which error it made, and the daemon carries on. Anything else
reaching the reactor from a decode path is a traceback, and a traceback caused by bytes a
peer chose is a peer choosing when exabgp stops.

So this is not a test of any one decoder. It is a floor under all of them at once: it
walks the NLRI registry and the attribute type space, feeds each entry a set of buffers
designed to fall off the end of something, and asserts on the type of what comes back.

The payloads are short and adversarial rather than random. Fuzzing with random bytes
mostly produces input rejected by the first length check; the interesting shapes are the
ones which pass it. So the set includes an empty buffer, a buffer of one byte where two
are read, all-zeros (a zero length field, which is where a decode loop fails to advance),
all-ones (a length field claiming far more than is present), and a prefix length of 0x80,
which is 128 and larger than any address family here.

Those buffers all fall at the first length check, which is the whole of the decoder for a
family with a flat NLRI and only the front door for a family framed as type + length +
payload.  So a second set is built: outer frames whose own length octet is honest, sized
so the frame is accepted, carrying an inner length field which is not.  That is the half
of MVPN and EVPN the buffers above never reach.

The attribute sweep covers type codes 0 to 44, which is every one IANA has assigned that
this tree could meet, against ten flag bytes. Those include the RFC 4271 4.3 unused low
bits and the combinations which conflict with what each attribute registers, because the
flag-conflict path and the length path reach different code.

This is a floor, not a proof. It says nothing about whether the Notify carries the right
subcode; the ledgers under qa/rfc/ are where that is checked, requirement by requirement.
"""

from __future__ import annotations

import random
from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action, Message
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI

# buffers which fall off the end of something a decoder is about to read
MALFORMED: tuple[bytes, ...] = (
    b'',
    b'\x00',
    b'\xff',
    b'\xff\xff',
    b'\x00\x00\x00\x00',
    b'\x00' * 8,
    b'\xff' * 8,
    b'\xff\xfe\xfd\xfc\xfb\xfa\xf9\xf8',
    b'\x20' + b'\xff' * 3,
    b'\x80' + b'\x00' * 20,
    b'\xff' * 40,
    b'\x01\x00',
    b'\x01\xff',
    b'\x00\xff' * 4,
)

# length octets which are not a legal address length but which divide by eight into one,
# followed by the two which are legal, so a frame that should decode is in the set too
INNER_LENGTHS: tuple[int, ...] = (0x21, 0x27, 0x81, 0x87, 0xFF, 0x20, 0x80)

# the type codes of a family framed as type + length + payload: MVPN route types run 1 to
# 7 and EVPN route types 1 to 5, and the unassigned ones above them must fall through
INNER_TYPE_CODES: tuple[int, ...] = tuple(range(1, 13))

# payload sizes a fixed-shape route type accepts, so the outer frame gets past the first
# length check instead of being refused before any inner field is read
INNER_PAYLOAD_SIZES: tuple[int, ...] = (18, 22, 34, 42, 46)

# where an inner length octet sits: after a route distinguisher, and after a route
# distinguisher and a four octet AS number
INNER_LENGTH_OFFSETS: tuple[int, ...] = (8, 12)


def well_framed_frames() -> tuple[bytes, ...]:
    """Outer frames whose own length is honest and whose inner length field is not.

    Every payload in MALFORMED is refused by the first length check of any decoder which
    has one, so none of them ever reaches the second.  A family framed as type + length +
    payload reads its inner length fields only once that outer frame has been accepted,
    which means the whole of that decoder is unreachable from the set above: not one of
    those buffers enters an MVPN route type at all.

    This is the shape which made the difference.  RFC 6514's Multicast Source Length is
    32 for IPv4 and 128 for IPv6, and a decoder which divided the octet by eight before
    comparing it read 0x81 as sixteen octets, walked the cursor sixteen octets into an
    eighteen octet payload and raised IndexError out of a buffer whose size was never in
    doubt.  The frame is honest; the field inside it is the lie.
    """
    frames: list[bytes] = []
    for code in INNER_TYPE_CODES:
        for size in INNER_PAYLOAD_SIZES:
            for offset in INNER_LENGTH_OFFSETS:
                for length in INNER_LENGTHS:
                    payload = bytearray(size)
                    payload[offset] = length
                    frames.append(bytes([code, size]) + bytes(payload))
    return tuple(frames)


MALFORMED += well_framed_frames()

# OPTIONAL 0x80, TRANSITIVE 0x40, PARTIAL 0x20, EXTENDED_LENGTH 0x10, and the four
# RFC 4271 4.3 unused bits.  0x41 and 0xFF are here because a flag which conflicts with
# what the attribute registered takes a different path than a flag which does not.
ATTRIBUTE_FLAGS: tuple[int, ...] = (0x00, 0x40, 0x80, 0xC0, 0xE0, 0x50, 0x90, 0xD0, 0x41, 0xFF)

# bodies short enough to truncate a fixed-width field, long enough to overrun a loop
ATTRIBUTE_BODIES: tuple[bytes, ...] = (
    b'',
    b'\x00',
    b'\xff',
    b'\x00\x00',
    b'\xff' * 3,
    b'\x00' * 4,
    b'\xff' * 6,
    b'\x02\x00',
    b'\x02\x01\xff\xff',
    b'\xff' * 12,
    b'\x00' * 16,
    b'\xff' * 24,
)

# every attribute type code IANA has assigned which this tree could be sent
LAST_ATTRIBUTE_CODE = 44

FAMILIES: list[tuple[AFI, SAFI]] = sorted(NLRI.registered_families, key=str)

# The sweep below parametrises from the NLRI registry, so it is only as wide as whatever
# has been imported by the time it is collected. A half filled registry does not fail, it
# quietly tests less, which is the one way a floor like this can stop being a floor. The
# registry_floor test at the bottom is what stops that happening silently.
MIN_FAMILIES = 24
FAMILY_IDS: list[str] = ['{}/{}'.format(afi, safi) for afi, safi in FAMILIES]


def session() -> Any:
    """A negotiated session which agreed nothing, which is what a decoder starts from."""
    negotiated = Mock()
    negotiated.asn4 = False
    negotiated.families = []
    negotiated.nexthop = []
    return negotiated


@pytest.mark.parametrize('afi,safi', FAMILIES, ids=FAMILY_IDS)
@pytest.mark.parametrize('addpath', (False, True), ids=('no-addpath', 'addpath'))
def test_an_nlri_decoder_raises_notify_and_not_something_else(afi: AFI, safi: SAFI, addpath: bool) -> None:
    """A family which answers with IndexError or struct.error hands the peer a traceback."""
    klass = NLRI.registered_nlri.get('{}/{}'.format(afi, safi))
    if klass is None:
        pytest.skip('family is registered but has no decoder')

    wrong: list[str] = []
    for payload in MALFORMED:
        try:
            klass.unpack_nlri(afi, safi, payload, Action.ANNOUNCE, addpath, session())
        except Notify:
            continue
        except Exception as exc:
            wrong.append(f'{payload.hex() or "<empty>"} raised {type(exc).__name__}: {exc}')

    assert not wrong, f'{afi}/{safi} answered malformed input with something other than Notify:\n  ' + '\n  '.join(
        wrong
    )


def attribute_wire(flag: int, code: int, body: bytes) -> bytes:
    """One attribute on the wire, with the length field the flag says it has."""
    if flag & Attribute.Flag.EXTENDED_LENGTH:
        return bytes([flag, code]) + pack('!H', len(body)) + body
    return bytes([flag, code, len(body)]) + body


@pytest.mark.parametrize('code', range(LAST_ATTRIBUTE_CODE + 1))
def test_an_attribute_decoder_raises_notify_and_not_something_else(code: int) -> None:
    """Attribute parsing is the path RFC 7606 is about, so it must never raise blind."""
    negotiated = Negotiated.make_negotiated(Neighbor.EMPTY, Direction.IN)
    name = Attribute.CODE.names.get(code, f'unassigned({code})')

    wrong: list[str] = []
    for flag in ATTRIBUTE_FLAGS:
        for body in ATTRIBUTE_BODIES:
            wire = attribute_wire(flag, code, body)
            try:
                AttributeCollection.unpack(wire, negotiated)
            except Notify:
                continue
            except Exception as exc:
                wrong.append(f'flag 0x{flag:02X} body {body.hex() or "<empty>"} raised {type(exc).__name__}: {exc}')

    assert not wrong, f'attribute {code} ({name}) answered malformed input with something other than Notify:\n  ' + (
        '\n  '.join(wrong)
    )


def random_bodies(count: int) -> list[bytes]:
    """Whole message bodies, seeded so a failure can be reproduced from the report.

    The message layer is where the outer length fields live: an UPDATE body says how many
    bytes of withdrawn routes and how many of path attributes it holds, and both are read
    before anything checks them against what actually arrived. Random bytes are the right
    shape here, unlike at the decoder level, because a random pair of sixteen bit lengths
    in front of a short buffer is exactly the malformed UPDATE this needs to survive.
    """
    generator = random.Random(20260924)
    return [bytes(generator.randrange(256) for _ in range(generator.randrange(0, 80))) for _ in range(count)]


MESSAGE_BODIES: tuple[bytes, ...] = (
    b'',
    b'\x00',
    b'\xff\xff',
    b'\x00' * 4,
    b'\xff' * 10,
    b'\x00\x04\x01\x02\x03\x04',
    b'\xff\xff' + b'\x00' * 8,
    b'\x00\x00\x00\x0c' + b'\xff' * 12,
    *random_bodies(400),
)

# 1 to 5 are OPEN, UPDATE, NOTIFICATION, KEEPALIVE and ROUTE-REFRESH; 6, 7 and 255 are
# unassigned, and an unassigned type has to be refused rather than dispatched
MESSAGE_TYPES: tuple[int, ...] = (1, 2, 3, 4, 5, 6, 7, 255)

# a decode which has not finished in this long is not slow, it is not going to finish
DECODE_SECONDS = 5


@pytest.mark.timeout(DECODE_SECONDS * len(MESSAGE_TYPES))
@pytest.mark.parametrize('message_type', MESSAGE_TYPES)
def test_a_message_decoder_raises_notify_and_not_something_else(message_type: int) -> None:
    """The outer length fields are read before anything has checked them.

    This is the layer the reactor hands bytes straight to, so it is the one where the
    difference between Notify and any other exception is the difference between a
    NOTIFICATION and a dead daemon.
    """
    negotiated = Negotiated.make_negotiated(Neighbor.EMPTY, Direction.IN)

    wrong: list[str] = []
    for body in MESSAGE_BODIES:
        try:
            Message.unpack(message_type, body, negotiated)
        except Notify:
            continue
        except Exception as exc:
            wrong.append(f'{body.hex() or "<empty>"} raised {type(exc).__name__}: {exc}')

    assert not wrong, f'message type {message_type} answered malformed input with something else:\n  ' + '\n  '.join(
        wrong[:10]
    )


@pytest.mark.registry_floor
def test_the_sweep_reaches_every_family_it_claims_to() -> None:
    """A sweep over a half filled registry passes by testing nothing.

    Both parametrised sweeps above take their cases from `NLRI.registered_families`,
    which is populated by import side effect. If a future refactor stops importing one of
    the family packages, this file keeps passing and silently covers less: no assertion
    fails, the count just drops. That is the failure mode `qa/bin/check_sweep_floors`
    exists to catch, and this is the assertion it asks for.

    The number is a floor rather than an equality so that adding a family does not fail
    it. Lower it only with a reason, because every step down is coverage leaving.
    """
    assert len(FAMILIES) >= MIN_FAMILIES, (
        f'the NLRI registry offered {len(FAMILIES)} families, down from {MIN_FAMILIES}, '
        f'so this file is sweeping less than it did: {FAMILY_IDS}'
    )


@pytest.mark.registry_floor
def test_the_attribute_sweep_covers_the_codes_it_claims_to() -> None:
    """The attribute sweep is bounded by a constant rather than a registry.

    It walks 0 to LAST_ATTRIBUTE_CODE whether or not a decoder is registered for each,
    which is deliberate: an unassigned code must be refused as surely as an assigned one.
    So the thing that can rot here is the constant falling behind IANA, not a registry
    emptying, and what this pins is that every code a decoder exists for is inside the
    range being swept.
    """
    registered = sorted({code for code, _ in Attribute.registered_attributes})

    missed = [code for code in registered if code > LAST_ATTRIBUTE_CODE]

    assert not missed, (
        f'attributes {missed} have decoders but sit above LAST_ATTRIBUTE_CODE '
        f'({LAST_ATTRIBUTE_CODE}), so the sweep never feeds them anything malformed'
    )
