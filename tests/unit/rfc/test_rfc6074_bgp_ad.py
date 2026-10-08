"""RFC 6074 section 7: BGP-AD and VPLS-BGP share AFI 25 / SAFI 65, told apart by NLRI length.

The ledger these tests are joined to is qa/rfc/rfc6074.toml.

exabgp decodes the seventeen octet VPLS NLRI of RFC 4761.  A twelve octet BGP-AD NLRI
arriving on the same family is not one, and must not take the session with it: it is
framed by its own two octet length, so it is stepped over and what follows is read.
"""

from __future__ import annotations

from struct import pack
from typing import Any

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import NLRIDiscard, Notify
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.protocol.family import AFI, SAFI

from rfc.community_wire import session

NEXT_HOP = bytes([10, 0, 0, 1])
ROUTE_DISTINGUISHER = pack('!HHL', 0, 65000, 1)

# RFC 6074 3.2.2: Length (2), Route Distinguisher (8), PE_addr (4)
BGP_AD = pack('!H', 12) + ROUTE_DISTINGUISHER + NEXT_HOP
# RFC 4761 3.2.2: Length (2), RD (8), VE ID (2), Block Offset (2), Block Size (2), Label Base (3)
VPLS_BGP = pack('!H', 17) + ROUTE_DISTINGUISHER + pack('!HHH', 3, 1, 8) + bytes([0x04, 0x00, 0x11])


def l2vpn_session() -> Any:
    negotiated = session()
    negotiated.families = [(AFI.l2vpn, SAFI.vpls)]
    return negotiated


def mp_reach(nlris: bytes) -> MPRNLRI:
    value = pack('!HB', int(AFI.l2vpn), int(SAFI.vpls)) + bytes([len(NEXT_HOP)]) + NEXT_HOP + b'\x00' + nlris
    reach = MPRNLRI.unpack_attribute(value, l2vpn_session())
    assert isinstance(reach, MPRNLRI)
    return reach


def mp_unreach(nlris: bytes) -> MPURNLRI:
    unreach = MPURNLRI.unpack_attribute(pack('!HB', int(AFI.l2vpn), int(SAFI.vpls)) + nlris, l2vpn_session())
    assert isinstance(unreach, MPURNLRI)
    return unreach


@pytest.mark.rfc('rfc6074#7-length-demultiplexer')
def test_a_bgp_ad_nlri_is_stepped_over_and_the_vpls_nlri_after_it_decoded() -> None:
    announced = [routed.nlri for routed in mp_reach(BGP_AD + VPLS_BGP).iter_routed()]
    assert [bytes(nlri.pack_nlri(session())) for nlri in announced] == [VPLS_BGP]


@pytest.mark.rfc('rfc6074#7-length-demultiplexer')
def test_a_bgp_ad_withdrawal_is_stepped_over_too() -> None:
    withdrawn = list(mp_unreach(VPLS_BGP + BGP_AD))
    assert [bytes(nlri.pack_nlri(session())) for nlri in withdrawn] == [VPLS_BGP]


@pytest.mark.rfc('rfc6074#7-length-demultiplexer')
def test_the_decoder_says_how_far_to_skip_a_bgp_ad_nlri() -> None:
    with pytest.raises(NLRIDiscard) as caught:
        VPLS.unpack_nlri(AFI.l2vpn, SAFI.vpls, BGP_AD + VPLS_BGP, Action.ANNOUNCE, False, session())
    assert caught.value.skip == len(BGP_AD)
    assert 'BGP-AD' in caught.value.detail


@pytest.mark.rfc('rfc6074#7-length-demultiplexer', polarity='negative')
def test_a_short_nlri_running_past_the_attribute_still_resets_the_session() -> None:
    # the length is all that frames it, and here it promises more than there is
    with pytest.raises(Notify) as caught:
        list(mp_reach(BGP_AD[:-1]).iter_routed())
    assert not isinstance(caught.value, NLRIDiscard)


@pytest.mark.rfc('rfc7606#5.3-mp-attribute-nlri-lengths', polarity='negative')
@pytest.mark.parametrize('length', [0, 1, 4, 11, 13, 16])
def test_a_length_neither_bgp_ad_nor_vpls_is_an_incorrect_attribute(length: int) -> None:
    """Only twelve octets are a BGP-AD NLRI: any other length below the seventeen of RFC 4761
    is "inconsistent with the given AFI/SAFI", which RFC 7606 5.3 makes the MP_REACH_NLRI
    incorrect, not an NLRI to step over."""
    short = pack('!H', length) + bytes(length)
    with pytest.raises(Notify) as caught:
        list(mp_reach(short + VPLS_BGP).iter_routed())
    assert not isinstance(caught.value, NLRIDiscard)
    assert (caught.value.code, caught.value.subcode) == (3, 10)


@pytest.mark.rfc('rfc7606#5.3-mp-attribute-nlri-lengths', polarity='negative')
def test_a_withdrawal_of_a_length_neither_bgp_ad_nor_vpls_is_an_incorrect_attribute() -> None:
    with pytest.raises(Notify) as caught:
        list(mp_unreach(VPLS_BGP + pack('!H', 16) + bytes(16)))
    assert not isinstance(caught.value, NLRIDiscard)
