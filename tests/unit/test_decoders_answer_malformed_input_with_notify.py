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

The attribute sweep covers type codes 0 to 44, which is every one IANA has assigned that
this tree could meet, against ten flag bytes. Those include the RFC 4271 4.3 unused low
bits and the combinations which conflict with what each attribute registers, because the
flag-conflict path and the length path reach different code.

This is a floor, not a proof. It says nothing about whether the Notify carries the right
subcode; the ledgers under qa/rfc/ are where that is checked, requirement by requirement.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
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
