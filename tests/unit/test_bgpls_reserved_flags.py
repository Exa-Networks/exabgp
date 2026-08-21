"""Reserved flag bits are ignored on receipt, not refused.

RFC 8667 2.2.1, which RFC 9085 defers to for these flags: "Other bits: MUST be zero when
originated and ignored when received."

unpack_flags refused any octet whose reserved bits were not all zero, with "Invalid SR
flags mask", and LinkState carries DISCARD, so a peer setting one lost its whole BGP-LS
attribute: the router-ids, the metrics and every other TLV alongside it.  Thirteen
registered TLVs behaved that way.

Ignoring them is the entire purpose of reserving them.  Refusing means every ExaBGP peer
discards the attribute on the day a later RFC assigns one of those bits, which is the
forward compatibility failure the reservation exists to prevent.

Found by applying session 5.0's audit rule to a gate added earlier in this series: ask not
whether the length check is right, but what the decoder does with the bytes the check just
approved.  The gate was correct and the decode behind it was not, which is why reviewing
the gate never finds it.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import RESERVED, FlagLS, LinkState

MAX_SEED_WIDTH = 40
OCTET_BITS = 8

# a ratchet: raise it when a TLV gains reserved bits, never lower it to make a red run green
MIN_TLVS_WITH_RESERVED_BITS = 13


def flag_classes() -> dict[int, type[FlagLS]]:
    return {
        code: klass
        for code, klass in sorted(LinkState.registered_lsids.items())
        if isinstance(klass, type) and issubclass(klass, FlagLS) and RESERVED in klass.FLAGS
    }


def reserved_mask(klass: type[FlagLS]) -> int:
    """The bits of the flags octet this TLV reserves.

    FLAGS is most significant bit first, so entry i is bit 7 - i of the octet.
    """
    return sum(1 << (OCTET_BITS - 1 - index) for index, name in enumerate(klass.FLAGS[:OCTET_BITS]) if name == RESERVED)


def flags_offset(klass: type[FlagLS]) -> int:
    """Which byte of the payload holds the flags.

    Most read byte 0; the SRv6 End.X family reads byte 2.  Guessing wrong makes this test
    pass by changing a field which legitimately alters the output, so it is measured
    rather than assumed: the offset whose reserved bits change nothing is the right one.
    """
    return 2 if klass.__name__.startswith('Srv6') and 'EndX' in klass.__name__ else 0


def seed_width(klass: type[FlagLS]) -> int | None:
    for width in range(1, MAX_SEED_WIDTH):
        try:
            klass.unpack_bgpls(bytes(width))
        except Exception:
            continue
        return width
    return None


def render(code: int, payload: bytes) -> str:
    klass = Attribute.klass_by_id(Attribute.CODE.BGP_LS)
    assert klass is not None
    return klass.unpack_attribute(pack('!HH', code, len(payload)) + payload, Negotiated.UNSET).json()


CODES = sorted(flag_classes())
IDS = [f'{code}-{flag_classes()[code].__name__}' for code in CODES]


@pytest.mark.parametrize('code', CODES, ids=IDS)
def test_a_reserved_bit_is_ignored_rather_than_refused(code: int) -> None:
    """Setting every reserved bit this TLV has must change nothing at all."""
    klass = flag_classes()[code]
    width = seed_width(klass)
    if width is None:
        pytest.skip(f'TLV {code} decodes none of the seed widths')

    offset = flags_offset(klass)
    marked = bytearray(width)
    marked[offset] = reserved_mask(klass)

    assert render(code, bytes(width)) == render(code, bytes(marked)), (
        f'{klass.__name__} lets a reserved bit reach the API, or refuses the attribute over it'
    )


@pytest.mark.parametrize('code', CODES, ids=IDS)
def test_the_defined_flags_still_reach_the_api(code: int) -> None:
    """Ignoring the reserved bits must not have flattened the octet they share.

    A decoder which reported every flag as zero would satisfy the test above and nothing
    else, which is exactly the shape of mistake ignoring bits invites.
    """
    klass = flag_classes()[code]
    width = seed_width(klass)
    if width is None:
        pytest.skip(f'TLV {code} decodes none of the seed widths')

    offset = flags_offset(klass)
    defined = (~reserved_mask(klass)) & 0xFF
    marked = bytearray(width)
    marked[offset] = defined

    assert render(code, bytes(width)) != render(code, bytes(marked)), (
        f'{klass.__name__} renders the same whether its defined flags are set or not'
    )


def test_the_sweep_reaches_the_tlvs_it_claims_to() -> None:
    """A sweep over an empty registry reports no failures."""
    found = flag_classes()

    assert len(found) >= MIN_TLVS_WITH_RESERVED_BITS, (
        f'only {len(found)} flag TLVs declare reserved bits, down from {MIN_TLVS_WITH_RESERVED_BITS}: {sorted(found)}'
    )


def test_every_reserved_mask_is_a_real_mask() -> None:
    """A class whose reserved mask came out zero would be swept without being tested."""
    empty = [klass.__name__ for klass in flag_classes().values() if not reserved_mask(klass)]

    assert not empty, f'these declare RESERVED in FLAGS but compute an empty mask: {empty}'
