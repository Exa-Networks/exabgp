"""Hand built seeds for the NLRI decoders, one RFC legal shape per family.

Random bytes and simple fill patterns never construct a valid-but-non-canonical NLRI, and
several families cannot be reached by them at all: a flow-vpn NLRI needs a route
distinguisher in front of its rules, a VPLS NLRI needs a two byte length which agrees with
its buffer, an SR Policy NLRI needs a length byte of exactly 96 or 192.

Those families were being swept with inputs their decoder rejected at the first byte, so
the property tests over them asserted nothing while reporting green.  Counted on the gate
profile over every decode the drawn tests in `test_nlri_decoder_properties.py` perform,
with `framed()` already in place:

    flow-vpn v4   0 / 400      sr-policy v4  0 / 400      vpls          0 / 400
    flow-vpn v6   0 / 400      sr-policy v6  0 / 400      mpls-vpn v4   3 / 400
    flow v6       3 / 400      flow v4       7 / 400      mpls-vpn v6  12 / 402

Five decoded nothing at all.  Drawing the length field with its payload, which is what
`framed()` does, closed the gap for MUP and EVPN and does nothing for these: their first
byte is not a length, or the length has to take one of two values, or the body behind it
has to be structured.  Only a hand written shape reaches them.

Seeds are RFC legal shapes, not fuzz.  The fuzzing happens around them: `seeds_for` frames
every fill pattern both ways as well, because a corpus which emits one length width never
frames the family which uses the other.

Ported from the 5.0 branch, where the same hole was found, and extended with the families
this tree adds: multicast and sr-policy.
"""

from __future__ import annotations

from struct import pack

FILLS = (b'A', b'\x00', b'\xff', b'\x80', b'\x01\x02\x03')

# A BGP-LS link NLRI body: an eight byte route distinguisher for the VPN SAFI, then the
# protocol id, the identifier, and one local node descriptor TLV carrying an AS number.
_BGPLS_LOCAL_NODE = pack('!HH', 256, 8) + pack('!HH', 512, 4) + b'\x00\x00\xff\xfd'
_BGPLS_VPN_BODY = bytes([0, 1]) + bytes([10, 0, 0, 1]) + bytes([0, 7]) + b'\x03' + b'\x00' * 8 + _BGPLS_LOCAL_NODE

NLRI_SEEDS: dict[str, list[bytes]] = {
    'ipv4/unicast': [bytes([24, 10, 0, 0]), bytes([0])],
    'ipv6/unicast': [bytes([32, 0x20, 0x01, 0x0D, 0xB8])],
    # multicast shares the INET decoder with unicast, and is swept separately because the
    # registry files it under its own key and a future split would go unnoticed otherwise
    'ipv4/multicast': [bytes([24, 0xE0, 0x00, 0x00]), bytes([0])],
    'ipv6/multicast': [bytes([32, 0xFF, 0x0E, 0x00, 0x00])],
    'ipv4/flow': [
        bytes([3, 0x03, 0x81, 0x06]),  # protocol = tcp
        bytes([6, 0x03, 0x81, 0x06, 0x04, 0x81, 0x19]),  # protocol = tcp, port = 25
    ],
    # RFC 8956 section 3.8.1, Example 1: a destination at offset 0, a source at offset 64
    # and an upper layer protocol.  A type 1 or type 2 component is sized from its length
    # minus its offset, so a fill pattern never builds one a real speaker could send.
    'ipv6/flow': [
        bytes([3, 0x03, 0x81, 0x06]),
        bytes([18, 0x01, 0x20, 0x00, 0x20, 0x01, 0x0D, 0xB8])
        + bytes([0x02, 0x68, 0x40, 0x12, 0x34, 0x56, 0x78, 0x9A])
        + bytes([0x03, 0x81, 0x06]),
    ],
    # a flow-vpn carries an eight byte route distinguisher before its rules
    'ipv4/flow-vpn': [bytes([11]) + b'\x00' * 8 + bytes([0x03, 0x81, 0x06])],
    'ipv6/flow-vpn': [bytes([11]) + b'\x00' * 8 + bytes([0x03, 0x81, 0x06])],
    # RFC 4761: RD(8) + endpoint(2) + offset(2) + size(2) + base(3) behind a two byte
    # length.  The second seed announces one byte more than the decoder reads, which a
    # sender is entitled to do and which the decoder accepts.
    'l2vpn/vpls': [b'\x00\x11' + b'\x00' * 17, b'\x00\x12' + b'\x00' * 18],
    'ipv4/rtc': [b'\x00', bytes.fromhex('60' + '0000fde8' + '0002fde800000064')],
    # A labelled VPN NLRI: mask(1) covers label(24) + rd(64) + prefix, and the label MUST
    # carry the bottom of stack bit, 0x01, or the decoder reads the route distinguisher as
    # more labels and the prefix disappears.
    'ipv4/mpls-vpn': [
        bytes([88]) + b'\x00\x01\x01' + b'\x00' * 8 + bytes([10, 0, 0]),  # 24+64+0, a VPN default route
        bytes([112]) + b'\x00\x01\x01' + b'\x00' * 8 + bytes([10, 0, 0]),  # 24+64+24, 10.0.0.0/24
    ],
    'ipv6/mpls-vpn': [
        bytes([120]) + b'\x00\x01\x01' + b'\x00' * 8 + bytes([0x20, 0x01, 0x0D, 0xB8]),  # 24+64+32
    ],
    'ipv4/nlri-mpls': [bytes([48, 0x00, 0x01, 0x01, 10, 0, 0])],
    'ipv6/nlri-mpls': [bytes([48, 0x00, 0x01, 0x01, 0x20, 0x01, 0x0D])],
    # MVPN Source Active A-D (type 5): RD(8) + srclen(1) + src(4) + grouplen(1) + group(4),
    # and a generic route the decoder keeps as raw bytes
    'ipv4/mcast-vpn': [
        bytes([5, 18]) + b'\x00' * 8 + bytes([32]) + b'\x0a\x00\x00\x01' + bytes([32]) + b'\xe0\x00\x00\x01',
        bytes([1, 4]) + b'\x00\x01\x02\x03',
    ],
    'ipv6/mcast-vpn': [
        bytes([5, 18]) + b'\x00' * 8 + bytes([32]) + b'\x0a\x00\x00\x01' + bytes([32]) + b'\xe0\x00\x00\x01',
        bytes([1, 4]) + b'\x00\x01\x02\x03',
    ],
    # MUP Direct Segment Discovery (arch 1, type 2): arch(1) + type(2) + length(1) + data
    'ipv4/mup': [bytes([1]) + (2).to_bytes(2, 'big') + bytes([12]) + b'\x00' * 12],
    'ipv6/mup': [bytes([1]) + (2).to_bytes(2, 'big') + bytes([12]) + b'\x00' * 12],
    'l2vpn/evpn': [bytes([1, 25]) + b'\x00' * 25],
    # RFC 9830 section 3: the length byte counts BITS, 96 for IPv4 and 192 for IPv6, and
    # the decoder refuses anything else.  A fill pattern never writes either value in
    # front of a body of the matching size, so neither family was ever decoded.
    'ipv4/sr-policy': [bytes([96]) + pack('!II', 1, 100) + bytes([10, 0, 0, 1])],
    'ipv6/sr-policy': [bytes([192]) + pack('!II', 1, 100) + bytes.fromhex('20010db8' + '00' * 12)],
    # RFC 7752 section 3.2: a BGP-LS VPN route is type(2) + length(2), then an eight byte
    # route distinguisher, then the NLRI.  bgp-ls-vpn DECLARES a route distinguisher in
    # Family.size and was the only such family with no seed, so the sweeps which exist to
    # prove things about route distinguishers had never seen one of the families that
    # carries one.
    'bgp-ls/bgp-ls-vpn': [pack('!HH', 2, len(_BGPLS_VPN_BODY)) + _BGPLS_VPN_BODY],
    'bgp-ls/bgp-ls': [
        bytes.fromhex('00010025')
        + bytes([3])
        + b'\x00' * 8
        + bytes.fromhex('01000018')
        + b'\x02\x00\x00\x04\x00\x00\xff\xfd'
        + b'\x02\x01\x00\x04\x00\x00\x00\x00'
        + b'\x02\x03\x00\x04\x0a\x71\x3f\xf0'
    ],
}

# Shapes the 5.0 corpus carries as seeds and this tree refuses on purpose, kept here so
# they are swept as NEGATIVE coverage rather than dropped.  A flow NLRI with no component
# matches every packet, which is not something a peer may install here, so the decoder
# answers with NLRI.INVALID and the route is treated as a withdraw.  Without these the
# next person to relax that check would see nothing go red.
REFUSED_SEEDS: dict[str, list[bytes]] = {
    'ipv4/flow': [bytes([0])],
    'ipv6/flow': [bytes([0])],
    'ipv4/flow-vpn': [bytes([8]) + b'\x00' * 8],
    'ipv6/flow-vpn': [bytes([8]) + b'\x00' * 8],
}

# Enough to cover every fixed field of every family above, and short enough that the
# product with FILLS and the two framings stays a few hundred inputs per family.
MAX_FILL_LENGTH_BYTES = 32


def filled(length_bytes: int, fill: bytes) -> bytes:
    """A payload of the requested length made of a repeating pattern."""
    return (fill * (length_bytes // len(fill) + 1))[:length_bytes]


def framed(body: bytes) -> list[bytes]:
    """The same body behind a one byte and a two byte length prefix.

    Families do not agree on the width of their length prefix: a flow NLRI writes one byte,
    a VPLS one writes two.  A corpus which emits only one width never frames the other
    family at all, so its decoder is never entered and the sweep reports clean over code it
    did not run.

    Emitting both costs nothing: the wrong framing is rejected at the first byte, which is
    what would have happened anyway.
    """
    out = []
    if len(body) < 256:
        out.append(bytes([len(body)]) + body)
    out.append(len(body).to_bytes(2, 'big') + body)
    return out


def seeds_for(family: str) -> list[bytes]:
    """Every seed for a family, framed both ways, plus the plain fill patterns."""
    payloads = list(NLRI_SEEDS.get(family, ()))
    payloads.extend(REFUSED_SEEDS.get(family, ()))
    for length_bytes in range(0, MAX_FILL_LENGTH_BYTES + 1):
        for fill in FILLS:
            body = filled(length_bytes, fill)
            payloads.append(body)
            payloads.extend(framed(body))
    return payloads
