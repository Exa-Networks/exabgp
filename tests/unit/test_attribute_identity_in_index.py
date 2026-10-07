"""Two attributes which differ on the wire are not the same attribute.

AttributeCollection.index() is the identity of a set of attributes: the RIB keys on it, and
two routes whose attributes give the same index are taken to carry the same attributes. It
is built from the text of each attribute, so an attribute whose str() leaves part of its
value out makes two different values one. A changed SR Policy, the same policy with
another SID flag or endpoint behaviour, was never re-sent because it compared equal to
the one already announced. TunnelEncap's own equality was built from str() too.
"""

from __future__ import annotations

from struct import pack

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.tunnel_encap import TunnelEncap
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy import SegmentListSubTLV, SRPolicyTunnel
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.segment_list import (
    SegmentTypeB,
    SRv6EndpointBehavior,
    WeightSubSubTLV,
)
from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import GenericTunnelTLV

SID = 'fc00::1'


def sr_policy(segment: SegmentTypeB) -> TunnelEncap:
    return TunnelEncap([SRPolicyTunnel([SegmentListSubTLV(WeightSubSubTLV(1), [segment])])])


def index(*attributes: Attribute) -> bytes:
    collection = AttributeCollection()
    for attribute in attributes:
        collection.add(attribute)
    return collection.index()


def test_sr_policies_differing_in_a_segment_flag_are_different() -> None:
    plain = sr_policy(SegmentTypeB(SID))
    verified = sr_policy(SegmentTypeB(SID, flags=0x80))
    assert plain != verified
    assert index(plain) != index(verified)


def test_sr_policies_differing_in_an_endpoint_behavior_are_different() -> None:
    one = sr_policy(SegmentTypeB(SID, endpoint_behavior=SRv6EndpointBehavior(1, 32, 16, 16, 0)))
    two = sr_policy(SegmentTypeB(SID, endpoint_behavior=SRv6EndpointBehavior(2, 32, 16, 16, 0)))
    assert one != two
    assert index(one) != index(two)


def test_the_same_sr_policy_is_the_same() -> None:
    assert sr_policy(SegmentTypeB(SID, flags=0x80)) == sr_policy(SegmentTypeB(SID, flags=0x80))
    assert index(sr_policy(SegmentTypeB(SID))) == index(sr_policy(SegmentTypeB(SID)))


def test_unknown_tunnel_types_with_different_values_are_different() -> None:
    one = TunnelEncap([GenericTunnelTLV(1, b'\x01')])
    two = TunnelEncap([GenericTunnelTLV(1, b'\x02')])
    assert one != two
    assert index(one) != index(two)


LABEL_INDEX = bytes([1]) + pack('!H', 7) + bytes(3) + pack('!I', 100)
UNKNOWN_SR_TLV = bytes([42]) + pack('!H', 2) + b'\xab\xcd'


def prefix_sid(value: bytes) -> PrefixSid:
    return PrefixSid.unpack_attribute(value, Negotiated.UNSET)


def test_a_prefix_sid_names_every_tlv_it_carries() -> None:
    alone = prefix_sid(LABEL_INDEX)
    more = prefix_sid(LABEL_INDEX + UNKNOWN_SR_TLV)
    assert str(alone) != str(more), 'a TLV beside the label index was left out of the text'
    assert index(alone) != index(more)


def test_prefix_sids_with_different_unknown_tlvs_are_different() -> None:
    one = prefix_sid(LABEL_INDEX + bytes([42]) + pack('!H', 1) + b'\x01')
    two = prefix_sid(LABEL_INDEX + bytes([42]) + pack('!H', 1) + b'\x02')
    assert index(one) != index(two)
