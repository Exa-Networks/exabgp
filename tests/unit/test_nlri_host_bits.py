"""The bits of a received prefix past its length are irrelevant, so they must not count.

RFC 4271 4.3 and RFC 4760 5 describe the Prefix field the same way: the prefix, then
"enough trailing bits to make the end of the field fall on an octet boundary.  Note that
the value of trailing bits is irrelevant."  The decoders kept them, so a peer announcing
10.0.1.0/23 (the low bit of the third octet set) and withdrawing 10.0.0.0/23 left the
route in place: two RIB keys, two strings, two unequal objects for the same route.

The sentence has no RFC 2119 keyword, so it is not on the ledger.

The last test is about the same key from the other side: a labelled route's __eq__ is its
index(), which leaves the label out, and its __hash__ was the wire bytes, label included.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

LABEL = bytes([0, 0, 0x11])
RD = bytes(8)

# (afi, safi, the length octet's bits ahead of the prefix, the octets ahead of the prefix)
FAMILIES = [
    (AFI.ipv4, SAFI.unicast, 0, b''),
    (AFI.ipv4, SAFI.nlri_mpls, 24, LABEL),
    (AFI.ipv4, SAFI.mpls_vpn, 24 + 64, LABEL + RD),
]


def decode(afi: AFI, safi: SAFI, data: bytes) -> NLRI:
    nlri, rest = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert rest == b''
    return nlri


@pytest.mark.parametrize('afi,safi,extra_bits,extra', FAMILIES)
def test_a_host_bit_past_the_mask_does_not_make_another_route(
    afi: AFI, safi: SAFI, extra_bits: int, extra: bytes
) -> None:
    clean = decode(afi, safi, bytes([extra_bits + 23]) + extra + bytes([10, 0, 0]))
    dirty = decode(afi, safi, bytes([extra_bits + 23]) + extra + bytes([10, 0, 1]))
    assert '10.0.0.0/23' in str(dirty)
    assert dirty.index() == clean.index()
    assert dirty == clean
    assert hash(dirty) == hash(clean)


@pytest.mark.parametrize('afi,safi,extra_bits,extra', FAMILIES)
def test_a_host_bit_past_the_mask_is_not_sent_back(afi: AFI, safi: SAFI, extra_bits: int, extra: bytes) -> None:
    dirty = decode(afi, safi, bytes([extra_bits + 23]) + extra + bytes([10, 0, 1]))
    assert bytes(dirty.pack_nlri(Negotiated.UNSET))[-1] == 0


def test_an_ipv6_prefix_of_one_bit_keeps_only_that_bit() -> None:
    assert str(decode(AFI.ipv6, SAFI.unicast, bytes([1, 0xFF]))) == '8000::/1'


@pytest.mark.parametrize('afi,safi,extra_bits,extra', FAMILIES[1:])
def test_equal_labelled_routes_hash_alike_whatever_their_label(
    afi: AFI, safi: SAFI, extra_bits: int, extra: bytes
) -> None:
    """Not host bits: __eq__ is index(), which leaves the label out, and __hash__ was _packed."""
    other_label = bytes([0, 0, 0x21]) + extra[3:]
    first = decode(afi, safi, bytes([extra_bits + 24]) + extra + bytes([10, 0, 0]))
    second = decode(afi, safi, bytes([extra_bits + 24]) + other_label + bytes([10, 0, 0]))
    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1
