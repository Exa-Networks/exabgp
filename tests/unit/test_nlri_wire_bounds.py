"""Length checks for the NLRI decoders, found by the property tests in tests/fuzz.

Every decoder registered in NLRI.registered_nlri has to answer malformed wire
data with a Notify, which closes the session, instead of a raw Python exception,
which kills the process. The cases below are the falsifying examples Hypothesis
produced in tests/fuzz/test_nlri_decoder_properties.py.
"""

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI


def decode(afi: AFI, safi: SAFI, data: bytes) -> NLRI:
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    return nlri


# ============================================================================
# INET: mask and payload bounds
# ============================================================================


@pytest.mark.parametrize('safi', [SAFI.unicast, SAFI.multicast])
def test_inet_without_data_raises_notify(safi: SAFI) -> None:
    """The mask byte was read before checking there was one (IndexError)."""
    for afi in (AFI.ipv4, AFI.ipv6):
        with pytest.raises(Notify):
            decode(afi, safi, b'')


@pytest.mark.parametrize('mask', [33, 64, 129, 255])
def test_inet_ipv4_mask_larger_than_the_family_raises_notify(mask: int) -> None:
    """A mask over /32 made CIDR pad with a negative count (ValueError)."""
    with pytest.raises(Notify):
        decode(AFI.ipv4, SAFI.unicast, bytes([mask]) + bytes(32))


@pytest.mark.parametrize('mask', [129, 200, 255])
def test_inet_ipv6_mask_larger_than_the_family_raises_notify(mask: int) -> None:
    with pytest.raises(Notify):
        decode(AFI.ipv6, SAFI.unicast, bytes([mask]) + bytes(32))


def test_inet_truncated_path_information_raises_notify(mask: int = 24) -> None:
    """add-path used to raise ValueError when the path-id was truncated."""
    with pytest.raises(Notify):
        NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, b'\x00\x00\x01', Action.ANNOUNCE, True, None)


@pytest.mark.parametrize('safi', [SAFI.nlri_mpls, SAFI.mpls_vpn])
def test_inet_truncated_label_stack_raises_notify(safi: SAFI) -> None:
    """The label stack was unpacked from fewer than three bytes (struct.error)."""
    with pytest.raises(Notify):
        decode(AFI.ipv4, safi, bytes([0x99, 0x00, 0x00]))


def test_inet_truncated_route_distinguisher_raises_notify() -> None:
    """RouteDistinguisher rejected a short slice with a ValueError."""
    with pytest.raises(Notify):
        decode(AFI.ipv4, SAFI.mpls_vpn, bytes([0x58, 0x00, 0x00, 0x11, 0x00]))


def test_inet_valid_prefix_still_decodes() -> None:
    nlri = decode(AFI.ipv4, SAFI.unicast, bytes([24, 10, 0, 0]))
    assert str(nlri) == '10.0.0.0/24'
    assert decode(AFI.ipv4, SAFI.unicast, bytes([0])) is not None
    assert str(decode(AFI.ipv6, SAFI.unicast, bytes([32, 0x20, 0x01, 0x0D, 0xB8]))) == '2001:db8::/32'


# ============================================================================
# RTC: length bounds and JSON
# ============================================================================


def test_rtc_without_data_raises_notify() -> None:
    """The length byte was read before checking there was one (IndexError)."""
    with pytest.raises(Notify):
        decode(AFI.ipv4, SAFI.rtc, b'')


@pytest.mark.parametrize('length', [0, 1, 16])
def test_vpls_shorter_than_it_reads_raises_notify(length: int) -> None:
    """Every VPLS accessor reads a fixed offset, so those bytes have to be there.

    A longer NLRI is not refused: the decoder has always read it correctly, and a sender
    may carry a field we do not know about yet.
    """
    with pytest.raises(Notify):
        decode(AFI.l2vpn, SAFI.vpls, bytes([0, length]) + bytes(length))


@pytest.mark.parametrize('announced', [17, 18, 24, 40])
def test_vpls_repacks_into_something_it_decodes_again(announced: int) -> None:
    """A longer VPLS NLRI is accepted, and only the first seventeen bytes are kept.

    The two byte prefix was copied from the wire while the payload behind it was truncated,
    so pack_nlri emitted nineteen bytes behind a header announcing more and the decoder
    refused its own output. Found by the seeded corpus in tests/fuzz/corpus.py.
    """
    payload = (
        bytes(8) + (1).to_bytes(2, 'big') + (2).to_bytes(2, 'big') + (8).to_bytes(2, 'big') + bytes([0, 0x10, 0x00])
    )
    wire = announced.to_bytes(2, 'big') + payload + bytes(announced - 17)
    nlri = decode(AFI.l2vpn, SAFI.vpls, wire)
    packed = bytes(nlri.pack_nlri(Negotiated.UNSET))
    again = decode(AFI.l2vpn, SAFI.vpls, packed)
    assert packed == (17).to_bytes(2, 'big') + payload
    assert again.index() == nlri.index()


def test_vpls_announcing_more_than_it_reads_has_one_index() -> None:
    """Two NLRI which differ only in a length the decoder ignores are one route.

    index() is the packed bytes, and the RIB keys withdrawals on it, so leaving the peer's
    length in there made a withdraw framed with a different length miss its announcement.
    """
    payload = (
        bytes(8) + (1).to_bytes(2, 'big') + (2).to_bytes(2, 'big') + (8).to_bytes(2, 'big') + bytes([0, 0x10, 0x00])
    )
    short = decode(AFI.l2vpn, SAFI.vpls, (17).to_bytes(2, 'big') + payload)
    long = decode(AFI.l2vpn, SAFI.vpls, (18).to_bytes(2, 'big') + payload + bytes(1))
    assert short.index() == long.index()


def test_vpls_with_the_right_length_still_decodes() -> None:
    payload = (
        bytes(8) + (1).to_bytes(2, 'big') + (2).to_bytes(2, 'big') + (8).to_bytes(2, 'big') + bytes([0, 0x10, 0x00])
    )
    nlri = decode(AFI.l2vpn, SAFI.vpls, (17).to_bytes(2, 'big') + payload)
    assert nlri.endpoint == 1
    assert nlri.offset == 2
    assert nlri.block_size == 8


# ============================================================================
# BGP-LS VPN: the announced length covers the route distinguisher
# ============================================================================


@pytest.mark.parametrize('length', [0, 1, 7])
def test_bgpls_vpn_length_below_a_route_distinguisher_raises_notify(length: int) -> None:
    """The route distinguisher size was subtracted from the announced length
    without checking, and packing the negative result raised struct.error."""
    for code in (1, 2, 3, 4):
        with pytest.raises(Notify):
            decode(AFI.bgpls, SAFI.bgp_ls_vpn, code.to_bytes(2, 'big') + length.to_bytes(2, 'big') + bytes(16))


@pytest.mark.parametrize('size_bytes', [4, 5, 8, 11])
def test_bgpls_vpn_generic_shorter_than_a_route_distinguisher_survives_a_round_trip(size_bytes: int) -> None:
    """A generic BGP-LS VPN NLRI must decode back into what it just packed.

    The buffer was required to hold twelve bytes before the header was even read, because
    a registered code slices its route distinguisher out of bytes four to twelve.  An
    unregistered code never reaches that slice: it keeps the whole announced wire and is
    stored as a generic, which for an announced length under eight is shorter than twelve
    bytes.  So the decoder produced an NLRI it then refused to read back, and refused a
    short generic sitting at the end of an NLRI stream, which the peer had framed
    correctly as far as its own length field said.

    Found by tests/fuzz/test_nlri_decoder_properties.py::test_decoding_is_idempotent with
    twelve zero bytes, where code and length both decode to zero.
    """
    payload_size_bytes = size_bytes - 4
    wire = (0).to_bytes(2, 'big') + payload_size_bytes.to_bytes(2, 'big') + bytes(payload_size_bytes)

    nlri = decode(AFI.bgpls, SAFI.bgp_ls_vpn, wire)
    packed = bytes(nlri.pack_nlri(Negotiated.UNSET))

    assert packed == wire, 'a generic must pack back the bytes it was given'

    again = decode(AFI.bgpls, SAFI.bgp_ls_vpn, packed)

    assert again.index() == nlri.index(), 'the decoder refuses what it just packed'


@pytest.mark.parametrize('code', [1, 2])
def test_bgpls_vpn_registered_code_packs_back_its_route_distinguisher(code: int) -> None:
    """A registered BGP-LS VPN NLRI must re-emit the route distinguisher it arrived with.

    RFC 7752 section 3.2 puts the route distinguisher between the header and the
    descriptors, and counts it in the announced length.  unpack_nlri slices it out so the
    descriptor parsers see the payload alone, and stored only that: pack_nlri then handed
    back a wire with no route distinguisher in it and a length eight bytes short.  So a
    route learnt in one VPN was re-announced as belonging to no VPN at all, and this same
    decoder refused to read back what it had just packed.

    Found by building the (type, length) pair by construction rather than drawing it:
    tests/fuzz/test_nlri_decoder_properties.py reached a registered VPN code with an
    agreeing length in a handful of examples out of four hundred.
    """
    distinguisher = bytes.fromhex('0001c0000202fde8')
    # protocol id, the 64 bit identifier, then an empty Local Node Descriptors TLV: the
    # smallest descriptor block the node and link decoders both accept.
    descriptors = bytes([3]) + bytes(8) + (256).to_bytes(2, 'big') + (0).to_bytes(2, 'big')
    announced = len(distinguisher) + len(descriptors)
    wire = code.to_bytes(2, 'big') + announced.to_bytes(2, 'big') + distinguisher + descriptors

    nlri = decode(AFI.bgpls, SAFI.bgp_ls_vpn, wire)
    packed = bytes(nlri.pack_nlri(Negotiated.UNSET))

    assert packed == wire, 'a VPN NLRI must pack back the bytes it was given'

    again = decode(AFI.bgpls, SAFI.bgp_ls_vpn, packed)

    assert again.index() == nlri.index(), 'the decoder refuses what it just packed'


def test_bgpls_vpn_generic_consumes_only_what_it_announces() -> None:
    """The bytes past the announced length belong to the next NLRI, not to this one."""
    wire = bytes(4) + b'\xde\xad\xbe\xef'

    nlri, left = NLRI.unpack_nlri(AFI.bgpls, SAFI.bgp_ls_vpn, wire, Action.ANNOUNCE, None, None)

    assert bytes(left) == b'\xde\xad\xbe\xef', 'a zero length NLRI consumed more than its header'
    assert bytes(nlri.pack_nlri(Negotiated.UNSET)) == bytes(4)


# ============================================================================
# Flow: a component announces the size of its value
# ============================================================================


def test_flow_component_value_cut_short_is_rejected() -> None:
    """A numeric component announcing more bytes than are left reached the value
    decoder with an empty string, which raised TypeError out of ord()."""
    # a two byte component: 0x03 is the protocol, whose operator byte announces no value
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.flow_ip, b'\x02\x03\x00', Action.ANNOUNCE, None, None)
    assert nlri is NLRI.INVALID


def test_flow_component_with_its_value_still_decodes() -> None:
    # component 3 (protocol) with a one byte value, end of list set
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.flow_ip, b'\x03\x03\x81\x06', Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID
    assert 'protocol' in nlri.json()


@pytest.mark.parametrize('length_bits, width', [(0x10, 2), (0x20, 4), (0x30, 8)])
def test_flow_component_value_wider_than_it_encodes_still_decodes(length_bits: int, width: int) -> None:
    """The operator byte announces the width, and RFC 8955 4.2.1.1 allows all four.

    This used to assert the NLRI was rejected, because the value decoder was ord() and was
    handed more than one byte. Refusing the width was the wrong half of that fix: it made
    a protocol match sent in four bytes disappear as an INVALID NLRI, silently. The
    decoders read whatever width arrives now, so the route survives.
    """
    components = bytes([0x03, 0x80 | length_bits | 0x01]) + bytes(width - 1) + bytes([0x06])
    data = bytes([len(components)]) + components
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.flow_ip, data, Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID
    assert 'protocol' in nlri.json()


def test_flow_port_accepts_the_two_byte_value_it_holds() -> None:
    # component 4 (any port), operator announces a two byte value, end of list set
    components = bytes([0x04, 0x91, 0x1F, 0x90])
    data = bytes([len(components)]) + components
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.flow_ip, data, Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID
    assert '8080' in nlri.json()
