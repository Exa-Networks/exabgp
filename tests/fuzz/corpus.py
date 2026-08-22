#!/usr/bin/env python3
# encoding: utf-8

"""Hand built seeds for the decoder corpora

Random bytes and simple fill patterns never construct a valid-but-non-canonical
message, and several families cannot be reached by them at all: a flow-vpn NLRI
needs a route distinguisher in front of its rules, a VPLS NLRI needs a two byte
length which agrees with the buffer.

Those families were being swept with inputs their decoder rejected at the first
byte, so the property tests over them asserted nothing while reporting green.

Seeds are RFC-legal shapes, not fuzz. The fuzzing happens around them.
"""

from struct import pack

FILLS = (b'A', b'\x00', b'\xff', b'\x80', b'\x01\x02\x03')


def filled(length, fill):
    """A payload of the requested length made of a repeating pattern"""
    return (fill * (length // len(fill) + 1))[:length]


# one or more shapes a real speaker could send, per family
_BGPLS_LOCAL_NODE = pack('!HH', 256, 8) + pack('!HH', 512, 4) + b'\x00\x00\xff\xfd'
_BGPLS_VPN_BODY = bytes([0, 1]) + bytes([10, 0, 0, 1]) + bytes([0, 7]) + b'\x03' + b'\x00' * 8 + _BGPLS_LOCAL_NODE

NLRI_SEEDS = {
    'ipv4/unicast': [bytes([24, 10, 0, 0]), bytes([0])],
    'ipv6/unicast': [bytes([32, 0x20, 0x01, 0x0D, 0xB8])],
    'ipv4/flow': [
        bytes([3, 0x03, 0x81, 0x06]),  # protocol = tcp
        bytes([0]),  # no rule at all
        bytes([6, 0x03, 0x81, 0x06, 0x04, 0x81, 0x19]),
    ],
    'ipv6/flow': [bytes([3, 0x03, 0x81, 0x06])],
    # a flow-vpn carries an eight byte route distinguisher before its rules
    'ipv4/flow-vpn': [bytes([11]) + b'\x00' * 8 + bytes([0x03, 0x81, 0x06]), bytes([8]) + b'\x00' * 8],
    'ipv6/flow-vpn': [bytes([11]) + b'\x00' * 8 + bytes([0x03, 0x81, 0x06])],
    # RD(8) + endpoint(2) + offset(2) + size(2) + base(3) announced as one length
    'l2vpn/vpls': [b'\x00\x11' + b'\x00' * 17, b'\x00\x12' + b'\x00' * 18],
    'ipv4/rtc': [b'\x00', bytes.fromhex('60' + '0000fde8' + '0002fde800000064')],
    # A labelled VPN NLRI: mask(1) covers label(24) + rd(64) + prefix, and the
    # label MUST carry the bottom of stack bit, 0x01, or the decoder reads the
    # route distinguisher as more labels and the prefix disappears.
    'ipv4/mpls-vpn': [
        bytes([88]) + b'\x00\x01\x01' + b'\x00' * 8 + bytes([10, 0, 0]),  # 24+64+0, a VPN default route
        bytes([112]) + b'\x00\x01\x01' + b'\x00' * 8 + bytes([10, 0, 0]),  # 24+64+24, 10.0.0.0/24
    ],
    'ipv6/mpls-vpn': [
        bytes([120]) + b'\x00\x01\x01' + b'\x00' * 8 + bytes([0x20, 0x01, 0x0D, 0xB8]),  # 24+64+32
    ],
    'ipv4/nlri-mpls': [bytes([48, 0x00, 0x01, 0x01, 10, 0, 0])],
    'ipv6/nlri-mpls': [bytes([48, 0x00, 0x01, 0x01, 0x20, 0x01, 0x0D])],
    # MVPN Source Active A-D (type 5): RD(8) + srclen(1) + src(4) + grouplen(1) + group(4)
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
    # A BGP-LS VPN route: an eight byte route distinguisher, then the NLRI. It
    # lives here rather than in one test file because every corpus driven sweep
    # needs it: bgp-ls/bgp-ls-vpn DECLARES a route distinguisher in Family.size
    # and was the only such family with no seed, so the sweeps which exist to
    # prove things about route distinguishers had never seen one of the families
    # that carries one.
    'bgp-ls/bgp-ls-vpn': [
        pack('!HH', 2, len(_BGPLS_VPN_BODY)) + _BGPLS_VPN_BODY,
    ],
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


def framed(body):
    """The same body behind a one byte and a two byte length prefix

    Families do not agree on the width of their length prefix: a flow NLRI
    writes one byte, a VPLS one writes two. A corpus which emits only one width
    never frames the other family at all, so its decoder is never entered and
    the sweep reports clean over code it did not run.

    Emitting both costs nothing: the wrong framing is rejected at the first byte,
    which is what would have happened anyway.
    """
    out = []
    if len(body) < 256:
        out.append(bytes([len(body)]) + body)
    out.append(len(body).to_bytes(2, 'big') + body)
    return out


def seeds_for(family):
    """Every seed for a family, framed both ways, plus the plain fill patterns"""
    payloads = list(NLRI_SEEDS.get(family, ()))
    for length in range(0, 33):
        for fill in FILLS:
            body = filled(length, fill)
            payloads.append(body)
            payloads.extend(framed(body))
    return payloads
