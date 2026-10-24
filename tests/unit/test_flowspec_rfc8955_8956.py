"""The FlowSpec decode faults backported from 6.0, RFC 8955 and RFC 8956.

Each test here failed against this branch before the fix that follows it, and each
describes a filter exabgp reported to its API which was not the filter the peer sent.
The worst of them turn a rule matching nothing, or a rule a peer could not express, into
a rule matching everything.

5.0 has no qa/rfc ledger, so the RFC sentence each test holds to is quoted in the test.
"""

from __future__ import annotations

from socket import AF_INET6, inet_pton
from struct import pack

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.nlri.flow import Flow, Flow6Source
from exabgp.protocol.family import AFI, SAFI

# RFC 8956 section 3.8.1, Example 1, copied out of Table 1 of the document: from
# ::1234:5678:9a00:0/64-104 to 2001:db8::/32, upper layer protocol tcp.
EXAMPLE_ONE_DESTINATION = bytes([0x01, 0x20, 0x00, 0x20, 0x01, 0x0D, 0xB8])
EXAMPLE_ONE_SOURCE = bytes([0x02, 0x68, 0x40, 0x12, 0x34, 0x56, 0x78, 0x9A])
EXAMPLE_ONE_PROTOCOL = bytes([0x03, 0x81, 0x06])


def decoded(components, afi=AFI.ipv6):
    """The real decoder, given the components of one NLRI and asked for its length."""
    payload = bytes([len(components)]) + components
    flow, over = Flow.unpack_nlri(afi, SAFI.flow_ip, payload, Action.ANNOUNCE, False)
    assert over == b'', 'the whole NLRI should have been consumed'
    return flow


def prefix_component(component_id, length, offset, pattern):
    """A type 1 or type 2 component written the way RFC 8956 section 3.1 lays it out."""
    return bytes([component_id, length, offset]) + pattern


# ==================================================== RFC 8955 section 4.2, the value


def test_an_nlri_with_no_component_is_not_a_filter_on_every_packet():
    """RFC 8955 section 4.2 encodes the value as <[component]+>, one component or more.

    A filter is the intersection of its components, so a filter with none of them
    matches every packet. A zero length NLRI reached the API as the bare string `flow`,
    and a controller acting on it rate limited or discarded all traffic on the box.
    Section 10 defers to RFC 7606, so this is a treat-as-withdraw.
    """
    assert decoded(b'', AFI.ipv4) is None


def test_a_component_type_present_twice_is_malformed():
    """RFC 8955 section 4.2: "a given component type MAY (exactly once) be present".

    This is worse than the reordering the branch already caught. A packet matches the
    intersection of every component, so two type 3 components can never both hold, yet
    the second one's operations were appended to the first one's list with its AND bit
    clear: `protocol tcp AND protocol udp`, which matches nothing, was reported as
    `protocol [ =tcp =udp ]`, which matches both.
    """
    both = bytes([0x03, 0x81, 0x06]) + bytes([0x03, 0x81, 0x11])

    assert decoded(both, AFI.ipv4) is None


def test_a_repeated_prefix_component_is_still_accepted():
    """The one relaxation, and the reason the rule above is not written `what == previous`.

    `Flow.add` has taken a repeated destination or source prefix from the configuration
    for years because some vendors send it. What exabgp is willing to encode it has to be
    able to read back.
    """
    twice = bytes([0x01, 0x18, 0x0A, 0x00, 0x00]) + bytes([0x01, 0x18, 0x0A, 0x00, 0x01])

    flow = decoded(twice, AFI.ipv4)

    assert flow is not None
    assert str(flow) == 'flow destination-ipv4 [ 10.0.0.0/24 10.0.1.0/24 ]'


# ==================================================== RFC 8955 section 4.2.1, operators


def test_the_reserved_bit_of_a_numeric_operator_is_ignored():
    """RFC 8955 section 4.2.1.1 lays the octet out as | e | a | len | 0 | lt | gt | eq |.

    Bit 0x08 is reserved and "MUST be set to 0 on NLRI encoding and MUST be ignored
    during decoding". Kept, `NumericString` could not find 0x09 in its table and a match
    on TCP reached the API as `protocol 09tcp`.
    """
    flow = decoded(bytes([0x03, 0x89, 0x06]), AFI.ipv4)

    assert flow is not None
    assert str(flow) == 'flow protocol =tcp'


def test_the_reserved_bits_of_a_bitmask_operator_are_ignored():
    """RFC 8955 section 4.2.1.2 lays it out as | e | a | len | 0 | 0 | not | m |.

    Two reserved bits, 0x0C, one more than the numeric operator reserves, which is why
    the mask has to come from the component's own flavour rather than from
    `CommonOperator`.
    """
    flow = decoded(bytes([0x09, 0x8D, 0x02]), AFI.ipv4)

    assert flow is not None
    assert str(flow) == 'flow tcp-flags =syn'


def test_the_and_bit_of_the_first_operator_is_ignored():
    """RFC 8955 section 4.2.1.1: "In the first operator octet of a sequence, the AND bit
    MUST be treated as always unset."

    Kept, it rendered as `&=tcp`: an AND against a pair which does not exist.
    """
    flow = decoded(bytes([0x03, 0xC1, 0x06]), AFI.ipv4)

    assert flow is not None
    assert str(flow) == 'flow protocol =tcp'


def test_an_and_bit_on_a_later_operator_is_kept():
    """The other side of the change: only the first octet of a sequence is cleared."""
    flow = decoded(bytes([0x03, 0x41, 0x06, 0xC1, 0x11]), AFI.ipv4)

    assert flow is not None
    assert str(flow) == 'flow protocol [ =tcp&=udp ]'


# ==================================================== the fragment bitmask, per family


def test_the_ipv6_fragment_bitmask_has_no_dont_fragment_bit():
    """RFC 8956 section 3.6 lays the bitmask out as | 0 0 0 0 | LF FF IsF 0 |.

    RFC 8955 figure 4 gives that low bit to DF, but IPv6 has no Don't Fragment header
    field, so for AFI 2 the position is reserved. One class served both families, so an
    IPv6 bitmask of 0x01 was published as a match on a field IPv6 does not have.
    """
    flow = decoded(bytes([0x0C, 0x80, 0x01]), AFI.ipv6)

    assert flow is not None
    assert 'dont-fragment' not in str(flow)


def test_the_ipv6_fragment_bitmask_keeps_the_three_bits_ipv6_defines():
    """LF, FF and IsF are real for IPv6 and must survive the mask."""
    flow = decoded(bytes([0x0C, 0x80, 0x0E]), AFI.ipv6)

    assert flow is not None
    assert str(flow) == 'flow fragment is-fragment+first-fragment+last-fragment'


def test_the_ipv4_fragment_bitmask_drops_its_reserved_bits():
    """RFC 8955 section 4.2.2.12: the high nibble is reserved and ignored on decoding.

    Kept, a bitmask of 0xF5 was rendered
    `dont-fragment+first-fragment+unknown fragment type 245`.
    """
    flow = decoded(bytes([0x0C, 0x80, 0xF5]), AFI.ipv4)

    assert flow is not None
    assert str(flow) == 'flow fragment dont-fragment+first-fragment'


# ==================================================== RFC 8956 section 3.1, the offset


def test_the_rfcs_own_first_example_decodes():
    """Section 3.8.1, copied byte for byte out of Table 1.

    "The encoded pattern contains enough octets for the bits used in matching (length
    minus offset bits)". The source component says length 104, offset 64, so the pattern
    is the 40 bits between them: five octets, `12 34 56 78 9a`. exabgp read thirteen,
    which is ceil(104 / 8), ate the type 3 component behind it and ran out of NLRI. Every
    IPv6 flow specification with a non-zero offset was unreadable, and since
    `IPrefix6.pack` wrote the pattern back the same way, the ones exabgp sent were
    unreadable to everyone else.
    """
    flow = decoded(EXAMPLE_ONE_DESTINATION + EXAMPLE_ONE_SOURCE + EXAMPLE_ONE_PROTOCOL)

    assert flow is not None
    assert str(flow) == ('flow destination-ipv6 2001:db8::/32/0 source-ipv6 ::1234:5678:9a00:0/104/64 next-header =tcp')


def test_a_prefix_with_an_offset_is_encoded_with_length_minus_offset_bits():
    """The encoder half of the same fault, against the RFC's own Table 1."""
    raw = inet_pton(AF_INET6, '::1234:5678:9a00:0')

    packed = bytes(Flow6Source(raw, 104, 64).pack())

    assert packed == EXAMPLE_ONE_SOURCE


def test_a_prefix_with_no_offset_still_decodes():
    """The case which always worked, so the two tests above are about the offset alone."""
    flow = decoded(EXAMPLE_ONE_DESTINATION)

    assert flow is not None
    assert str(flow) == 'flow destination-ipv6 2001:db8::/32/0'


@pytest.mark.parametrize('length', [33, 34, 47, 65, 128])
def test_a_prefix_with_no_offset_round_trips(length):
    """What the branch already encoded for offset zero has to keep its bytes.

    Every capture under qa/ carries offset zero, so this is the guard that routing pack
    through the shared helper did not move the wire for the only case they cover.
    """
    raw = inet_pton(AF_INET6, '2001:db8::')
    trimmed = (int.from_bytes(raw, 'big') >> (128 - length) << (128 - length)).to_bytes(16, 'big')

    packed = bytes(Flow6Source(trimmed, length, 0).pack())

    assert packed == bytes([0x02, length, 0x00]) + trimmed[: (length + 7) // 8]


def test_padding_set_by_a_peer_is_ignored_on_decoding():
    """RFC 8956 section 3.1: the padding bits "MUST be ignored on decoding".

    Two components describing the same match have to render alike and hash to the same
    RIB index. They did not: the padding reached the CIDR.
    """
    clean = decoded(prefix_component(1, 33, 0, bytes([0x20, 0x01, 0x0D, 0xB8, 0x80])))
    padded = decoded(prefix_component(1, 33, 0, bytes([0x20, 0x01, 0x0D, 0xB8, 0xFF])))

    assert clean is not None and padded is not None
    assert str(padded) == str(clean)


def test_a_length_of_zero_with_an_offset_of_zero_matches_every_address():
    """Section 3.1: "If length = 0 and offset = 0, this component matches every address"."""
    flow = decoded(prefix_component(1, 0, 0, b''))

    assert flow is not None
    assert str(flow) == 'flow destination-ipv6 ::/0/0'


@pytest.mark.parametrize(('length', 'offset'), [(32, 64), (64, 64), (129, 0), (0, 8)])
def test_a_length_outside_the_range_rfc_8956_allows_is_malformed(length, offset):
    """Section 3.1: "length MUST be in the range offset < length < 129".

    The offset half was never compared to anything, so a match on bits 64 through 32,
    which do not exist, was accepted from any peer and rendered 2001:db8::/32/64.
    """
    pattern = bytes(max(0, (length - offset + 7) // 8))

    assert decoded(prefix_component(1, length, offset, pattern)) is None


def test_a_prefix_whose_pattern_is_short_is_malformed():
    """A length and offset which ask for more pattern than the NLRI holds."""
    assert decoded(prefix_component(1, 104, 64, bytes([0x12, 0x34]))) is None


# ==================================================== the components stay readable


def test_the_ipv6_capture_under_qa_decoding_still_decodes():
    """qa/decoding/bgp-flow-1's NLRI, which every change above has to leave alone.

    It is the only IPv6 FlowSpec capture on the branch, it carries a destination, a
    source, a next-header and three fragment bits, and no runner collects it under
    pytest, so it is asserted here.
    """
    nlri = bytes.fromhex('0180002A0229B8192500000000000000002E69024000BEEFF00E000000000381060C000400028008')

    flow = decoded(nlri)

    assert flow is not None
    assert str(flow) == (
        'flow destination-ipv6 2a02:29b8:1925::2e69/128/0 source-ipv6 beef:f00e::/64/0'
        ' next-header =tcp fragment [ first-fragment is-fragment last-fragment ]'
    )


@pytest.mark.parametrize(
    ('nlri', 'rendered'),
    [
        ('0901048109', 'flow tcp-flags [ =rst =fin+push ]'),
        ('09001000804201C240', 'flow tcp-flags [ ack cwr&!fin&!ece ]'),
        ('090090C241', 'flow tcp-flags [ ack+cwr&!fin+ece ]'),
    ],
)
def test_the_ipv4_captures_under_qa_decoding_still_decode(nlri, rendered):
    """qa/decoding/bgp-flow-2 through 4, for the same reason."""
    flow = decoded(bytes.fromhex(nlri), AFI.ipv4)

    assert flow is not None
    assert str(flow) == rendered


def test_the_ipv6_flow_of_conf_flow_msg_still_encodes_the_same_bytes():
    """The offset-zero half of qa/encoding/conf-flow.msg's IPv6 flow, unchanged.

    The source prefix of that capture carries offset 120 and 16 pattern octets, which is
    what `_pattern_size_bytes` now refuses to write: that line of the capture has to be
    re-baselined and is reported rather than changed here. The destination, at offset
    zero, must not move, and this holds it.
    """
    raw = inet_pton(AF_INET6, '2a02:b80:15::7aca:39ff:feae:a87a')

    packed = bytes(Flow6Source(raw, 128, 0).pack())

    assert packed == bytes([0x02, 0x80, 0x00]) + raw
    assert bytes(Flow6Source(inet_pton(AF_INET6, '::1'), 128, 120).pack()) == bytes([0x02, 0x80, 0x78, 0x01])


def test_the_extended_length_form_the_first_wave_fixed_still_reads():
    """FLOW_LENGTH_EXTENDED_SHIFT, guarded here because an empty-rules raise sits in the
    same decoder and a wrong length reaches it as an empty payload."""
    components = b''.join(bytes([0x01, 0x18, 0x0A, octet, 0x00]) for octet in range(60))
    wire = pack('!H', len(components) | 0xF000) + components

    flow, over = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, wire, Action.ANNOUNCE, False)

    assert flow is not None
    assert over == b''
    assert len(flow.rules[0x01]) == 60
