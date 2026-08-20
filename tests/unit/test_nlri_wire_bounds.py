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


@pytest.mark.parametrize('length', [1, 8, 31])
def test_rtc_length_below_an_origin_raises_notify(length: int) -> None:
    """A short RT length raised a bare Exception, which no caller expects."""
    with pytest.raises(Notify):
        decode(AFI.ipv4, SAFI.rtc, bytes([length]) + bytes(12))


@pytest.mark.parametrize('size', [1, 5, 12])
def test_rtc_truncated_route_target_raises_notify(size: int) -> None:
    """A route target cut short indexed past the payload (IndexError)."""
    with pytest.raises(Notify):
        decode(AFI.ipv4, SAFI.rtc, bytes([96]) + bytes(size - 1))


def test_rtc_wildcard_and_route_target_have_a_json_representation() -> None:
    """RTC had no json(), so any received RTC route broke the API output."""
    wildcard = decode(AFI.ipv4, SAFI.rtc, bytes([0]))
    assert wildcard.json() == '{ "origin": 0, "route-target": null }'

    route = decode(AFI.ipv4, SAFI.rtc, bytes([96]) + (65000).to_bytes(4, 'big') + b'\x00\x02\xfd\xe8\x00\x00\x00\x01')
    assert route.json() == '{ "origin": 65000, "route-target": "target:65000:1" }'


# ============================================================================
# MPLS: the label stack does not always end with the bottom of stack bit
# ============================================================================


def test_mpls_vpn_withdraw_label_keeps_the_route_distinguisher() -> None:
    """RFC 3107 withdraws use label 0x800000, which does not set the bottom of
    stack bit. The accessors scanned for that bit and swallowed the rd and the
    prefix, so a withdrawn VPN route raised ValueError on rd and on json."""
    # mask 112 = 24 bits of label + 64 bits of rd + 24 bits of prefix
    data = bytes([112, 0x80, 0x00, 0x00]) + bytes(8) + bytes([10, 0, 0])
    nlri, leftover = NLRI.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, data, Action.WITHDRAW, None, None)

    assert bytes(leftover) == b''
    assert str(nlri.rd) == ' rd 0:0'
    assert nlri.cidr.prefix() == '10.0.0.0/24'
    assert '"nlri": "10.0.0.0/24"' in nlri.json()


def test_mpls_label_stack_without_bottom_of_stack_keeps_the_prefix() -> None:
    """Same problem without a route distinguisher."""
    # mask 48 = 24 bits of label + 24 bits of prefix
    data = bytes([48, 0x80, 0x00, 0x00, 10, 0, 0])
    nlri, leftover = NLRI.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, data, Action.WITHDRAW, None, None)

    assert bytes(leftover) == b''
    assert nlri.cidr.prefix() == '10.0.0.0/24'


# ============================================================================
# VPLS: the payload has one valid size
# ============================================================================


@pytest.mark.parametrize('length', [0, 1, 16, 18, 255])
def test_vpls_with_the_wrong_length_raises_notify(length: int) -> None:
    """Any length was accepted as long as the payload matched it, and the
    accessors then unpacked the endpoint from bytes which were not there."""
    with pytest.raises(Notify):
        decode(AFI.l2vpn, SAFI.vpls, length.to_bytes(2, 'big') + bytes(length))


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
