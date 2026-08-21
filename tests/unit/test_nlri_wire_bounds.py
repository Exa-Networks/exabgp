"""Length checks for the NLRI decoders, found by the property tests in tests/fuzz.

Every decoder registered in NLRI.registered_nlri has to answer malformed wire
data with a Notify, which closes the session, instead of a raw Python exception,
which kills the process. The cases below are the falsifying examples Hypothesis
produced in tests/fuzz/test_nlri_decoder_properties.py.
"""

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
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
