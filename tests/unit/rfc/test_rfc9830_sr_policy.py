"""RFC 9830: the SR Policy NLRI, and the length byte which decides how wide the endpoint is.

The NLRI is three fixed fields with no internal framing, so everything rests on one octet.
Section 2.1 ties it to the AFI: 96 bits under AFI 1, 192 under AFI 2.  Get that wrong and
four octets of endpoint get read as sixteen, or the other way round, and the address which
reaches the API is not the address the peer sent.  The tests below feed each AFI the other
one's length byte, which is the shape that would do it.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.tunnel_encap import TunnelEncap
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.sr_policy import SRPolicyNLRI
from exabgp.protocol.family import AFI, SAFI

pytestmark = pytest.mark.timeout(10)

TUNNEL_ENCAP = int(Attribute.CODE.TUNNEL_ENCAP)
TREAT_AS_WITHDRAW = Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW
SR_POLICY_TUNNEL = 15

IPV4_BITS = 96
IPV6_BITS = 192


def nlri_bytes(length_bits: int, endpoint: bytes, distinguisher: int = 1, color: int = 2) -> bytes:
    return bytes([length_bits]) + pack('!II', distinguisher, color) + endpoint


def unpack(afi: AFI, wire: bytes) -> SRPolicyNLRI:
    decoded, remaining = SRPolicyNLRI.unpack_nlri(afi, SAFI.sr_policy, wire, Action.ANNOUNCE, False, Negotiated.UNSET)
    assert remaining == b''
    assert isinstance(decoded, SRPolicyNLRI)
    return decoded


@pytest.mark.rfc('rfc9830#2.1-afi-must-be-ipv4-or-ipv6')
def test_the_sr_policy_nlri_is_registered_for_ipv4_and_ipv6() -> None:
    assert NLRI.registered_nlri['ipv4/sr-policy'] is SRPolicyNLRI
    assert NLRI.registered_nlri['ipv6/sr-policy'] is SRPolicyNLRI


@pytest.mark.rfc('rfc9830#2.1-afi-must-be-ipv4-or-ipv6', polarity='negative')
def test_no_other_address_family_resolves_to_the_sr_policy_nlri() -> None:
    families = sorted(key for key in NLRI.registered_nlri if key.endswith('/sr-policy'))
    assert families == ['ipv4/sr-policy', 'ipv6/sr-policy']


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192')
def test_ninety_six_bits_under_afi_one_decodes_a_four_octet_endpoint() -> None:
    decoded = unpack(AFI.ipv4, nlri_bytes(IPV4_BITS, bytes([10, 0, 0, 1])))
    assert (decoded.distinguisher, decoded.color, decoded.endpoint) == (1, 2, '10.0.0.1')


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192')
def test_one_hundred_and_ninety_two_bits_under_afi_two_decodes_a_sixteen_octet_endpoint() -> None:
    endpoint = bytes.fromhex('20010db8000000000000000000000001')
    decoded = unpack(AFI.ipv6, nlri_bytes(IPV6_BITS, endpoint))
    assert decoded.endpoint == '2001:db8::1'


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_an_ipv4_length_byte_under_afi_two_is_refused_rather_than_read_as_ipv6() -> None:
    # 12 bytes of body with the AFI saying 16: the suspicion is that the endpoint property
    # would read past the end of the NLRI and into whatever followed it
    with pytest.raises(Notify) as raised:
        unpack(AFI.ipv6, nlri_bytes(IPV4_BITS, bytes([10, 0, 0, 1])))
    assert (raised.value.code, raised.value.subcode) == (3, 10)


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_an_ipv6_length_byte_under_afi_one_is_refused() -> None:
    endpoint = bytes.fromhex('20010db8000000000000000000000001')
    with pytest.raises(Notify) as raised:
        unpack(AFI.ipv4, nlri_bytes(IPV6_BITS, endpoint))
    assert (raised.value.code, raised.value.subcode) == (3, 10)


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_a_length_byte_of_zero_is_refused_and_does_not_yield_an_empty_nlri() -> None:
    with pytest.raises(Notify):
        unpack(AFI.ipv4, nlri_bytes(0, b''))


@pytest.mark.rfc('rfc9830#2.1-nlri-length-96-or-192', polarity='negative')
def test_the_right_length_byte_with_the_bytes_missing_is_refused() -> None:
    with pytest.raises(Notify) as raised:
        unpack(AFI.ipv4, bytes([IPV4_BITS]) + pack('!II', 1, 2))
    assert (raised.value.code, raised.value.subcode) == (3, 10)


@pytest.mark.rfc('rfc9830#2.4-single-sr-policy-tlv')
def test_two_sr_policy_tlvs_in_one_attribute_are_treated_as_withdraw() -> None:
    tlv = pack('!HH', SR_POLICY_TUNNEL, 8) + pack('!BB', 12, 6) + pack('!BBI', 0, 0, 100)
    value = tlv + tlv
    wire = bytes([0xC0, TUNNEL_ENCAP, len(value)]) + value
    collection = AttributeCollection().parse(wire, Negotiated.UNSET)
    assert TREAT_AS_WITHDRAW in collection
    # the route goes: neither TLV may be kept and handed on as if one had been sent
    assert TUNNEL_ENCAP not in collection


@pytest.mark.rfc('rfc9830#2.4-single-sr-policy-tlv', polarity='negative')
def test_a_second_tunnel_tlv_of_another_type_is_not_a_duplicate() -> None:
    # the rule names the SR Policy tunnel type, not tunnel TLVs in general: a route may
    # carry more than one tunnel, and 1 is a type exabgp does not decode
    sr_policy = pack('!HH', SR_POLICY_TUNNEL, 8) + pack('!BB', 12, 6) + pack('!BBI', 0, 0, 100)
    other = pack('!HH', 1, 4) + b'\x01\x02\x03\x04'
    value = sr_policy + other
    wire = bytes([0xC0, TUNNEL_ENCAP, len(value)]) + value
    collection = AttributeCollection().parse(wire, Negotiated.UNSET)
    assert TREAT_AS_WITHDRAW not in collection
    attr = collection[TUNNEL_ENCAP]
    assert isinstance(attr, TunnelEncap)
    assert len(attr.tunnel_tlvs) == 2


@pytest.mark.rfc('rfc9830#2.4-single-sr-policy-tlv', polarity='negative')
def test_one_sr_policy_tlv_in_an_attribute_is_accepted() -> None:
    value = pack('!HH', SR_POLICY_TUNNEL, 8) + pack('!BB', 12, 6) + pack('!BBI', 0, 0, 100)
    wire = bytes([0xC0, TUNNEL_ENCAP, len(value)]) + value
    collection = AttributeCollection().parse(wire, Negotiated.UNSET)
    assert TREAT_AS_WITHDRAW not in collection
    attr = collection[TUNNEL_ENCAP]
    assert isinstance(attr, TunnelEncap)
    assert len(attr.tunnel_tlvs) == 1
