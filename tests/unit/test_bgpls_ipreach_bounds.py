"""The BGP-LS IP Reachability sub-TLV trusted its own length and let ValueError escape.

IpReach.unpack_ipreachability read the prefix length byte and then ignored it, taking the
byte count from whatever the TLV claimed to carry (`octet = len(data[1:])`).  Nothing
bounded that against the address family, so:

  * an IPv6 sub-TLV carrying more than 16 prefix bytes built a string of nine or more
    hextet groups.  The padding term `['0'] * (8 - len(prefix_parts))` goes negative, which
    Python quietly treats as an empty list rather than an error, and ip_address() then
    raised ValueError out of the decoder.  PREFIXv6.unpack_bgpls_nlri calls check() with no
    try/except, so that reached the reactor's catch-all and reset the session *without* the
    NOTIFICATION the peer is owed.  A ~36 byte NLRI triggers it.
  * an IPv4 sub-TLV carrying more than 4 bytes produced a malformed address which no check
    rejected: "1.1.1.1.1/32" went into the JSON API output as though it were a prefix.
  * a prefix length was never range checked, so 255 was reported as a /255.

RFC 7752 section 3.2.3.2 gives the relationship: the prefix field carries the most
significant octets of the prefix, one octet per eight bits of prefix length.  The FIXME in
the decoder documents a Cisco IOS XR bug which sends one octet *fewer* than that, so the
check has to be an upper bound rather than an equality, or it breaks a peer which is known
to be out there.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.prefixv6 import PREFIXv6
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach
from exabgp.protocol.family import AFI, SAFI

PROTOCOL_ID_IPV4 = 3
PROTOCOL_ID_IPV6 = 4

IPV4_MAX_PREFIX_BITS = 32
IPV6_MAX_PREFIX_BITS = 128
IPV4_ADDRESS_SIZE_BYTES = 4
IPV6_ADDRESS_SIZE_BYTES = 16

TLV_IP_REACHABILITY = 265
# An identifier of 8 bytes and a protocol id of 1, per RFC 7752 section 3.2.
BGPLS_ISIS_L1 = 1


def reachability(plength: int, present_length_bytes: int) -> bytes:
    """An IP Reachability sub-TLV value: the prefix length byte, then prefix octets."""
    return bytes([plength]) + bytes([1] * present_length_bytes)


def prefixv6_nlri(plength: int, present_length_bytes: int) -> bytes:
    """A complete PREFIXv6 NLRI carrying one IP Reachability TLV, header included."""
    value = reachability(plength, present_length_bytes)
    payload = bytes([BGPLS_ISIS_L1]) + bytes(8) + pack('!HH', TLV_IP_REACHABILITY, len(value)) + value
    return pack('!HH', PREFIXv6.CODE, len(payload)) + payload


# More prefix octets than any IPv6 address has.  17 is the first, 18 the one which decodes
# to an even number of hextets and so gets past the odd byte padding.
IPV6_OVERSIZED_BYTES = [17, 18, 20, 32]


@pytest.mark.parametrize('present_length_bytes', IPV6_OVERSIZED_BYTES, ids=[str(n) for n in IPV6_OVERSIZED_BYTES])
def test_an_oversized_ipv6_reachability_tlv_notifies(present_length_bytes: int) -> None:
    """The peer is told what was wrong, rather than the session dropping silently."""
    with pytest.raises(Notify):
        IpReach.unpack_ipreachability(reachability(IPV6_MAX_PREFIX_BITS, present_length_bytes), PROTOCOL_ID_IPV6)


def decode_nlri(nlri: bytes) -> object:
    """The boundary the reactor reaches: BGPLS.unpack_nlri, which is what calls check().

    PREFIXv6.unpack_bgpls_nlri on its own parses nothing, the descriptors are lazy, so
    testing against it would pass while the raise still escaped from a property access
    several layers downstream.
    """
    decoded, _left = BGPLS.unpack_nlri(AFI.bgpls, SAFI.bgp_ls, nlri, Action.ANNOUNCE, None, None)
    return decoded


@pytest.mark.parametrize('present_length_bytes', IPV6_OVERSIZED_BYTES, ids=[str(n) for n in IPV6_OVERSIZED_BYTES])
def test_an_oversized_ipv6_reachability_tlv_notifies_through_the_nlri(present_length_bytes: int) -> None:
    """The path the reactor actually takes.

    A ValueError here is the defect, not an untidiness: it bypasses the `except Notify`
    branch in the peer loop, so the session is reset with no NOTIFICATION sent.
    """
    with pytest.raises(Notify):
        decode_nlri(prefixv6_nlri(IPV6_MAX_PREFIX_BITS, present_length_bytes))


def test_an_oversized_ipv4_reachability_tlv_notifies() -> None:
    """The IPv4 branch has the same missing bound and does not crash, it lies.

    Five octets produced "1.1.1.1.1/32" in the JSON API output, which is not a prefix, and
    nothing downstream was in a position to notice.
    """
    with pytest.raises(Notify):
        IpReach.unpack_ipreachability(reachability(IPV4_MAX_PREFIX_BITS, IPV4_ADDRESS_SIZE_BYTES + 1), PROTOCOL_ID_IPV4)


@pytest.mark.parametrize('plength', [129, 200, 255])
def test_an_out_of_range_ipv6_prefix_length_notifies(plength: int) -> None:
    """A /255 was reported verbatim in the API output for want of a range check."""
    with pytest.raises(Notify):
        IpReach.unpack_ipreachability(reachability(plength, IPV6_ADDRESS_SIZE_BYTES), PROTOCOL_ID_IPV6)


@pytest.mark.parametrize('plength', [33, 64, 255])
def test_an_out_of_range_ipv4_prefix_length_notifies(plength: int) -> None:
    with pytest.raises(Notify):
        IpReach.unpack_ipreachability(reachability(plength, IPV4_ADDRESS_SIZE_BYTES), PROTOCOL_ID_IPV4)


def test_more_octets_than_the_prefix_length_calls_for_is_deliberately_accepted() -> None:
    """The bound is the address family size, not the prefix length, and that is a choice.

    RFC 7752 section 3.2.3.2 says one octet per eight bits of prefix length, so a /8 with
    four octets is more than the RFC calls for.  Refusing it would be the stricter reading,
    but the FIXME in the decoder records an IOS XR bug in exactly that relationship, and a
    check built on it would refuse prefixes from a router which is deployed.  The address
    family size is the bound which does not depend on the field the router gets wrong.

    This is pinned so the leniency reads as intended rather than as an oversight.
    """
    decoded = IpReach.unpack_ipreachability(reachability(8, IPV4_ADDRESS_SIZE_BYTES), PROTOCOL_ID_IPV4)

    assert decoded.plength == 8
    assert decoded.prefix == '1.1.1.1'


def test_an_empty_reachability_tlv_still_notifies() -> None:
    """The pre-existing check for a missing prefix length byte must survive the new ones."""
    with pytest.raises(Notify):
        IpReach.unpack_ipreachability(b'', PROTOCOL_ID_IPV6)


# --- the negative space: what has to keep working -------------------------------------


@pytest.mark.parametrize(
    'plength,present_length_bytes,expected',
    [
        (128, 16, '101:101:101:101:101:101:101:101'),
        (64, 8, '101:101:101:101::'),
        (32, 4, '101:101::'),
        (0, 0, '::'),
    ],
)
def test_a_well_formed_ipv6_reachability_tlv_still_decodes(
    plength: int, present_length_bytes: int, expected: str
) -> None:
    decoded = IpReach.unpack_ipreachability(reachability(plength, present_length_bytes), PROTOCOL_ID_IPV6)

    assert decoded.prefix == expected
    assert decoded.plength == plength


@pytest.mark.parametrize(
    'plength,present_length_bytes,expected',
    [
        (32, 4, '1.1.1.1'),
        (24, 3, '1.1.1.0'),
        (8, 1, '1.0.0.0'),
    ],
)
def test_a_well_formed_ipv4_reachability_tlv_still_decodes(
    plength: int, present_length_bytes: int, expected: str
) -> None:
    decoded = IpReach.unpack_ipreachability(reachability(plength, present_length_bytes), PROTOCOL_ID_IPV4)

    assert decoded.prefix == expected
    assert decoded.plength == plength


def test_the_cisco_xr_short_prefix_field_is_still_accepted() -> None:
    """The FIXME in the decoder documents an IOS XR bug: one octet fewer than the RFC says.

    An equality check against the prefix length would be more correct on paper and would
    drop every prefix from a real deployed router, so the check is an upper bound.
    """
    decoded = IpReach.unpack_ipreachability(reachability(IPV4_MAX_PREFIX_BITS, 3), PROTOCOL_ID_IPV4)

    assert decoded.prefix == '1.1.1.0'
    assert decoded.plength == IPV4_MAX_PREFIX_BITS


def test_a_well_formed_prefixv6_nlri_still_decodes() -> None:
    """The negative space at the boundary the reactor uses."""
    decoded = decode_nlri(prefixv6_nlri(IPV6_MAX_PREFIX_BITS, IPV6_ADDRESS_SIZE_BYTES))

    assert isinstance(decoded, PREFIXv6)
    assert decoded.prefix is not None
    assert decoded.prefix.plength == IPV6_MAX_PREFIX_BITS
