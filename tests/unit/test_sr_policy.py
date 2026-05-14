"""tests/unit/test_sr_policy.py

Unit tests for SR Policy NLRI and Tunnel Encap attribute (RFC 9830 / RFC 9012).
"""

from __future__ import annotations

import socket
import struct

from exabgp.bgp.message.update.attribute.tunnel_encap import TunnelEncap
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy import (
    BindingSIDSubTLV,
    CandidatePathNameSubTLV,
    PolicyNameSubTLV,
    PreferenceSubTLV,
    PrioritySubTLV,
    SegmentListSubTLV,
    SRPolicyTunnel,
    SRv6BindingSIDSubTLV,
)
from exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy.segment_list import (
    SegmentTypeA,
    SegmentTypeB,
    SegmentTypeC,
    SegmentTypeD,
    SegmentTypeE,
    SegmentTypeF,
    SegmentTypeG,
    SegmentTypeH,
    SegmentTypeI,
    SegmentTypeJ,
    SegmentTypeK,
    SRv6EndpointBehavior,
    WeightSubSubTLV,
)
from exabgp.bgp.message.update.nlri.sr_policy import SRPolicyNLRI
from exabgp.protocol.family import AFI, SAFI

# ============================================================= SAFI


def test_safi_sr_policy_value():
    assert int(SAFI.sr_policy) == 73


def test_safi_sr_policy_name():
    assert SAFI.sr_policy.name() == 'sr-policy'


def test_afi_implemented_safi_includes_sr_policy():
    assert 'sr-policy' in AFI.implemented_safi('ipv4')
    assert 'sr-policy' in AFI.implemented_safi('ipv6')


# ============================================================= SRPolicyNLRI


def test_sr_policy_nlri_ipv4_create():
    nlri = SRPolicyNLRI.create(AFI.ipv4, distinguisher=0, color=100, endpoint='1.2.3.4')
    assert nlri.distinguisher == 0
    assert nlri.color == 100
    assert nlri.endpoint == '1.2.3.4'
    assert nlri.afi == AFI.ipv4
    assert nlri.safi == SAFI.sr_policy


def test_sr_policy_nlri_ipv6_create():
    nlri = SRPolicyNLRI.create(AFI.ipv6, distinguisher=1, color=200, endpoint='2001:db8::1')
    assert nlri.distinguisher == 1
    assert nlri.color == 200
    assert nlri.endpoint == '2001:db8::1'
    assert nlri.afi == AFI.ipv6


def test_sr_policy_nlri_ipv4_pack_unpack():
    nlri = SRPolicyNLRI.create(AFI.ipv4, distinguisher=42, color=999, endpoint='10.0.0.1')
    packed = nlri.pack_nlri(None)
    # RFC 9830: Length(1) + Distinguisher(4) + Color(4) + Endpoint(4) = 13 bytes
    assert len(packed) == 13
    assert packed[0] == 96  # Length byte = 96 bits (12 bytes * 8)

    nlri2, remaining = SRPolicyNLRI.unpack_nlri(AFI.ipv4, SAFI.sr_policy, packed, None, None)
    assert remaining == b''
    assert isinstance(nlri2, SRPolicyNLRI)
    assert nlri2.distinguisher == 42
    assert nlri2.color == 999
    assert nlri2.endpoint == '10.0.0.1'


def test_sr_policy_nlri_ipv6_pack_unpack():
    nlri = SRPolicyNLRI.create(AFI.ipv6, distinguisher=0, color=500, endpoint='fc00::1')
    packed = nlri.pack_nlri(None)
    # RFC 9830: Length(1) + Distinguisher(4) + Color(4) + Endpoint(16) = 25 bytes
    assert len(packed) == 25
    assert packed[0] == 192  # Length byte = 192 bits (24 bytes * 8)

    nlri2, remaining = SRPolicyNLRI.unpack_nlri(AFI.ipv6, SAFI.sr_policy, packed, None, None)
    assert remaining == b''
    assert nlri2.distinguisher == 0
    assert nlri2.color == 500
    assert nlri2.endpoint == 'fc00::1'


def test_sr_policy_nlri_str():
    nlri = SRPolicyNLRI.create(AFI.ipv4, 0, 100, '1.2.3.4')
    assert 'distinguisher 0' in str(nlri)
    assert 'color 100' in str(nlri)
    assert 'endpoint 1.2.3.4' in str(nlri)


def test_sr_policy_nlri_eq():
    n1 = SRPolicyNLRI.create(AFI.ipv4, 0, 100, '1.2.3.4')
    n2 = SRPolicyNLRI.create(AFI.ipv4, 0, 100, '1.2.3.4')
    n3 = SRPolicyNLRI.create(AFI.ipv4, 0, 200, '1.2.3.4')
    assert n1 == n2
    assert n1 != n3


# ============================================================= Preference


def test_preference_subtlv_pack_unpack():
    tlv = PreferenceSubTLV(preference=100)
    packed = tlv.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + preference(4) = 8 bytes
    assert len(packed) == 8
    assert packed[0] == 12  # SUBTYPE
    assert packed[1] == 6  # length must be 6 per RFC 9830

    tlv2 = PreferenceSubTLV.unpack(packed[2:])  # skip type(1) + length(1) header
    assert tlv2.preference == 100


def test_preference_subtlv_json():
    tlv = PreferenceSubTLV(preference=200)
    assert '"preference": 200' in tlv.json()


# ============================================================= Priority


def test_priority_subtlv_pack_unpack():
    tlv = PrioritySubTLV(priority=10)
    packed = tlv.pack()
    assert len(packed) == 4  # type(1) + length(1) + priority(1) + reserved(1)
    assert packed[0] == 15

    tlv2 = PrioritySubTLV.unpack(packed[2:])
    assert tlv2.priority == 10


# ============================================================= Policy Name


def test_policy_name_subtlv_pack_unpack():
    tlv = PolicyNameSubTLV(name='test-policy')
    packed = tlv.pack()
    # type(1) + length(2) + reserved(1) + name_bytes
    assert packed[0] == 130  # Type 130 = Policy Name

    tlv2 = PolicyNameSubTLV.unpack(packed[3:])
    assert tlv2.name == 'test-policy'


# ============================================================= Candidate Path Name


def test_candidate_path_name_subtlv_pack_unpack():
    tlv = CandidatePathNameSubTLV(name='primary')
    packed = tlv.pack()
    assert packed[0] == 129  # Type 129 = Candidate Path Name

    tlv2 = CandidatePathNameSubTLV.unpack(packed[3:])
    assert tlv2.name == 'primary'


# ============================================================= Binding SID


def test_binding_sid_mpls_pack_unpack():
    tlv = BindingSIDSubTLV(label=24000)
    packed = tlv.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + label_entry(4) = 8 bytes
    assert len(packed) == 8
    assert packed[0] == 13

    tlv2 = BindingSIDSubTLV.unpack(packed[2:])
    assert tlv2.label == 24000


def test_binding_sid_null_pack_unpack():
    tlv = BindingSIDSubTLV(label=None)
    packed = tlv.pack()
    # type(1) + length(1) + flags(1) + reserved(1) = 4 bytes
    assert len(packed) == 4

    tlv2 = BindingSIDSubTLV.unpack(packed[2:])
    assert tlv2.label is None


# ============================================================= SRv6 Binding SID


def test_srv6_binding_sid_pack_unpack():
    tlv = SRv6BindingSIDSubTLV(sid='fc00::1')
    packed = tlv.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + sid(16) = 20 bytes
    assert len(packed) == 20
    assert packed[0] == 20

    tlv2 = SRv6BindingSIDSubTLV.unpack(packed[2:])
    assert tlv2.sid == 'fc00::1'


# ============================================================= Segment List


def test_weight_subsubtlv_pack_unpack():
    w = WeightSubSubTLV(weight=5)
    packed = w.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + weight(4) = 8 bytes
    assert len(packed) == 8
    assert packed[0] == 9
    assert packed[1] == 6  # length must be 6 per RFC 9830

    w2 = WeightSubSubTLV.unpack(packed[2:])
    assert w2.weight == 5


def test_segment_type_a_pack_unpack():
    seg = SegmentTypeA(label=16001)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + label_entry(4) = 8 bytes
    assert len(packed) == 8
    assert packed[0] == 1

    seg2 = SegmentTypeA.unpack(packed[2:])
    assert seg2.label == 16001


def test_segment_type_b_pack_unpack():
    seg = SegmentTypeB(sid='fc00::2')
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + sid(16) = 20 bytes
    assert len(packed) == 20
    assert packed[0] == 13

    seg2 = SegmentTypeB.unpack(packed[2:])
    assert seg2.sid == 'fc00::2'
    assert seg2.endpoint_behavior is None


def test_segment_type_b_with_endpoint_behavior():
    eb = SRv6EndpointBehavior(endpoint_behavior=0x0041, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    seg = SegmentTypeB(sid='fc00::3', endpoint_behavior=eb)
    packed = seg.pack()

    seg2 = SegmentTypeB.unpack(packed[2:])
    assert seg2.sid == 'fc00::3'
    assert seg2.endpoint_behavior is not None
    assert seg2.endpoint_behavior.endpoint_behavior == 0x0041
    assert seg2.endpoint_behavior.lb_length == 32
    assert seg2.endpoint_behavior.fun_length == 16


def test_segment_list_pack_unpack():
    weight = WeightSubSubTLV(weight=1)
    segments = [
        SegmentTypeA(label=16001),
        SegmentTypeA(label=16002),
    ]
    tlv = SegmentListSubTLV(weight=weight, segments=segments)
    packed = tlv.pack()
    assert packed[0] == 128

    # header is type(1) + length(2)
    tlv2 = SegmentListSubTLV.unpack(packed[3:])
    assert tlv2.weight.weight == 1
    assert len(tlv2.segments) == 2
    assert isinstance(tlv2.segments[0], SegmentTypeA)
    assert tlv2.segments[0].label == 16001
    assert tlv2.segments[1].label == 16002


def test_segment_list_mixed_segments():
    weight = WeightSubSubTLV(weight=2)
    segments = [SegmentTypeA(label=16003), SegmentTypeB(sid='fc00::5')]
    tlv = SegmentListSubTLV(weight=weight, segments=segments)
    packed = tlv.pack()

    tlv2 = SegmentListSubTLV.unpack(packed[3:])
    assert tlv2.weight.weight == 2
    assert len(tlv2.segments) == 2
    assert isinstance(tlv2.segments[0], SegmentTypeA)
    assert isinstance(tlv2.segments[1], SegmentTypeB)
    assert tlv2.segments[0].label == 16003
    assert tlv2.segments[1].sid == 'fc00::5'


# ============================================================= SRPolicyTunnel


def test_sr_policy_tunnel_pack_unpack():
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(100),
            PrioritySubTLV(10),
            PolicyNameSubTLV('my-policy'),
            SegmentListSubTLV(
                weight=WeightSubSubTLV(1),
                segments=[SegmentTypeA(16001), SegmentTypeA(16002)],
            ),
        ]
    )
    packed_value = tunnel.pack_value()
    tunnel2 = SRPolicyTunnel.unpack(packed_value)

    subtlv_types = [type(t) for t in tunnel2.subtlvs]
    assert PreferenceSubTLV in subtlv_types
    assert PrioritySubTLV in subtlv_types
    assert PolicyNameSubTLV in subtlv_types
    assert SegmentListSubTLV in subtlv_types

    seg_list = next(t for t in tunnel2.subtlvs if isinstance(t, SegmentListSubTLV))
    assert seg_list.weight.weight == 1
    assert len(seg_list.segments) == 2


def test_sr_policy_tunnel_multiple_segment_lists():
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(100),
            SegmentListSubTLV(WeightSubSubTLV(1), [SegmentTypeA(16001)]),
            SegmentListSubTLV(WeightSubSubTLV(2), [SegmentTypeA(16002), SegmentTypeA(16003)]),
        ]
    )
    packed_value = tunnel.pack_value()
    tunnel2 = SRPolicyTunnel.unpack(packed_value)

    seg_lists = [t for t in tunnel2.subtlvs if isinstance(t, SegmentListSubTLV)]
    assert len(seg_lists) == 2
    assert seg_lists[0].weight.weight == 1
    assert seg_lists[1].weight.weight == 2
    assert len(seg_lists[1].segments) == 2


# ============================================================= TunnelEncap


def test_tunnel_encap_attribute_pack_unpack():
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(100),
            SegmentListSubTLV(WeightSubSubTLV(1), [SegmentTypeA(16001)]),
        ]
    )
    attr = TunnelEncap(tunnel_tlvs=[tunnel])
    packed = attr.pack_attribute(None)

    # packed includes the BGP attribute header (flags + type + length)
    # strip it to get the raw value for unpack_attribute
    # Attribute._attribute() adds: flags(1) + type(1) + length(1 or 2)
    # The value starts after the header
    # Read past flags(1) + type(1) + length bytes
    raw_value = _strip_attr_header(packed)
    attr2 = TunnelEncap.unpack_attribute(raw_value, None)

    assert len(attr2.tunnel_tlvs) == 1
    assert isinstance(attr2.tunnel_tlvs[0], SRPolicyTunnel)
    sr = attr2.tunnel_tlvs[0]
    prefs = [t for t in sr.subtlvs if isinstance(t, PreferenceSubTLV)]
    assert prefs[0].preference == 100


def _strip_attr_header(data: bytes) -> bytes:
    """Strip BGP attribute header (flags + type + length) from packed attribute."""
    flags = data[0]
    # bit 4 (0x10) = extended length
    if flags & 0x10:
        # flags(1) + type(1) + length(2) = 4 bytes header
        return data[4:]
    else:
        # flags(1) + type(1) + length(1) = 3 bytes header
        return data[3:]


def test_tunnel_encap_json():
    tunnel = SRPolicyTunnel(subtlvs=[PreferenceSubTLV(50)])
    attr = TunnelEncap(tunnel_tlvs=[tunnel])
    j = attr.json()
    assert 'sr-policy' in j
    assert '"preference": 50' in j


# ============================================================= Segment Type C


def test_segment_type_c_no_sid():
    seg = SegmentTypeC(ipv4_node='10.0.0.1', algorithm=0)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + algorithm(1) + ipv4(4) = 8 bytes
    assert len(packed) == 8
    assert packed[0] == 3  # SUBTYPE

    seg2 = SegmentTypeC.unpack(packed[2:])
    assert seg2.ipv4_node == '10.0.0.1'
    assert seg2.algorithm == 0
    assert seg2.sid is None


def test_segment_type_c_with_sid():
    seg = SegmentTypeC(ipv4_node='10.0.0.2', algorithm=1, sid=16001)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + algorithm(1) + ipv4(4) + sid(4) = 12 bytes
    assert len(packed) == 12

    seg2 = SegmentTypeC.unpack(packed[2:])
    assert seg2.ipv4_node == '10.0.0.2'
    assert seg2.algorithm == 1
    assert seg2.sid == 16001


def test_segment_type_c_json():
    seg = SegmentTypeC(ipv4_node='10.0.0.3', algorithm=0)
    j = seg.json()
    assert '"type": "C"' in j
    assert '10.0.0.3' in j
    assert '"algorithm": 0' in j


def test_segment_type_c_json_with_sid():
    seg = SegmentTypeC(ipv4_node='10.0.0.4', algorithm=1, sid=16002)
    j = seg.json()
    assert '"sid": 16002' in j


# ============================================================= Segment Type D


def test_segment_type_d_no_sid():
    seg = SegmentTypeD(ipv6_node='fc00::1', algorithm=0)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + algorithm(1) + ipv6(16) = 20 bytes
    assert len(packed) == 20
    assert packed[0] == 4

    seg2 = SegmentTypeD.unpack(packed[2:])
    assert seg2.ipv6_node == 'fc00::1'
    assert seg2.algorithm == 0
    assert seg2.sid is None


def test_segment_type_d_with_sid():
    seg = SegmentTypeD(ipv6_node='fc00::2', algorithm=128, sid=16003)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + algorithm(1) + ipv6(16) + sid(4) = 24 bytes
    assert len(packed) == 24

    seg2 = SegmentTypeD.unpack(packed[2:])
    assert seg2.ipv6_node == 'fc00::2'
    assert seg2.algorithm == 128
    assert seg2.sid == 16003


def test_segment_type_d_json():
    seg = SegmentTypeD(ipv6_node='fc00::3', algorithm=0)
    j = seg.json()
    assert '"type": "D"' in j
    assert 'fc00::3' in j


# ============================================================= Segment Type E


def test_segment_type_e_no_sid():
    seg = SegmentTypeE(local_if_id=1, ipv4_node='10.0.0.1')
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + if_id(4) + ipv4(4) = 12 bytes
    assert len(packed) == 12
    assert packed[0] == 5

    seg2 = SegmentTypeE.unpack(packed[2:])
    assert seg2.local_if_id == 1
    assert seg2.ipv4_node == '10.0.0.1'
    assert seg2.sid is None


def test_segment_type_e_with_sid():
    seg = SegmentTypeE(local_if_id=2, ipv4_node='10.0.0.2', sid=16004)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + if_id(4) + ipv4(4) + sid(4) = 16 bytes
    assert len(packed) == 16

    seg2 = SegmentTypeE.unpack(packed[2:])
    assert seg2.local_if_id == 2
    assert seg2.ipv4_node == '10.0.0.2'
    assert seg2.sid == 16004


def test_segment_type_e_json():
    seg = SegmentTypeE(local_if_id=3, ipv4_node='10.0.0.3')
    j = seg.json()
    assert '"type": "E"' in j
    assert '"local_if_id": 3' in j
    assert '10.0.0.3' in j


# ============================================================= Segment Type F


def test_segment_type_f_no_sid():
    seg = SegmentTypeF(local_ipv4='192.168.1.1', remote_ipv4='192.168.1.2')
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + local(4) + remote(4) = 12 bytes
    assert len(packed) == 12
    assert packed[0] == 6

    seg2 = SegmentTypeF.unpack(packed[2:])
    assert seg2.local_ipv4 == '192.168.1.1'
    assert seg2.remote_ipv4 == '192.168.1.2'
    assert seg2.sid is None


def test_segment_type_f_with_sid():
    seg = SegmentTypeF(local_ipv4='192.168.2.1', remote_ipv4='192.168.2.2', sid=16005)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + local(4) + remote(4) + sid(4) = 16 bytes
    assert len(packed) == 16

    seg2 = SegmentTypeF.unpack(packed[2:])
    assert seg2.local_ipv4 == '192.168.2.1'
    assert seg2.remote_ipv4 == '192.168.2.2'
    assert seg2.sid == 16005


def test_segment_type_f_json():
    seg = SegmentTypeF(local_ipv4='192.168.3.1', remote_ipv4='192.168.3.2')
    j = seg.json()
    assert '"type": "F"' in j
    assert '192.168.3.1' in j
    assert '192.168.3.2' in j


# ============================================================= Segment Type G


def test_segment_type_g_no_sid():
    seg = SegmentTypeG(local_if_id=1, local_ipv6='fc00::1', remote_if_id=2, remote_ipv6='fc00::2')
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + local_if(4) + local_ipv6(16) + remote_if(4) + remote_ipv6(16) = 44 bytes
    assert len(packed) == 44
    assert packed[0] == 7

    seg2 = SegmentTypeG.unpack(packed[2:])
    assert seg2.local_if_id == 1
    assert seg2.local_ipv6 == 'fc00::1'
    assert seg2.remote_if_id == 2
    assert seg2.remote_ipv6 == 'fc00::2'
    assert seg2.sid is None


def test_segment_type_g_with_sid():
    seg = SegmentTypeG(local_if_id=3, local_ipv6='fc00::3', remote_if_id=4, remote_ipv6='fc00::4', sid=16006)
    packed = seg.pack()
    # + sid(4) = 48 bytes
    assert len(packed) == 48

    seg2 = SegmentTypeG.unpack(packed[2:])
    assert seg2.local_if_id == 3
    assert seg2.remote_if_id == 4
    assert seg2.sid == 16006


def test_segment_type_g_json():
    seg = SegmentTypeG(local_if_id=5, local_ipv6='fc00::5', remote_if_id=6, remote_ipv6='fc00::6')
    j = seg.json()
    assert '"type": "G"' in j
    assert '"local_if_id": 5' in j
    assert 'fc00::5' in j


# ============================================================= Segment Type H


def test_segment_type_h_no_sid():
    seg = SegmentTypeH(local_ipv6='fc00::1', remote_ipv6='fc00::2')
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + reserved(1) + local_ipv6(16) + remote_ipv6(16) = 36 bytes
    assert len(packed) == 36
    assert packed[0] == 8

    seg2 = SegmentTypeH.unpack(packed[2:])
    assert seg2.local_ipv6 == 'fc00::1'
    assert seg2.remote_ipv6 == 'fc00::2'
    assert seg2.sid is None


def test_segment_type_h_with_sid():
    seg = SegmentTypeH(local_ipv6='fc00::3', remote_ipv6='fc00::4', sid=16007)
    packed = seg.pack()
    # + sid(4) = 40 bytes
    assert len(packed) == 40

    seg2 = SegmentTypeH.unpack(packed[2:])
    assert seg2.local_ipv6 == 'fc00::3'
    assert seg2.remote_ipv6 == 'fc00::4'
    assert seg2.sid == 16007


def test_segment_type_h_json():
    seg = SegmentTypeH(local_ipv6='fc00::5', remote_ipv6='fc00::6')
    j = seg.json()
    assert '"type": "H"' in j
    assert 'fc00::5' in j
    assert 'fc00::6' in j


# ============================================================= Segment Type I


def test_segment_type_i_no_sid():
    seg = SegmentTypeI(ipv6_node='fc00::1', algorithm=0)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + algorithm(1) + ipv6(16) = 20 bytes
    assert len(packed) == 20
    assert packed[0] == 14

    seg2 = SegmentTypeI.unpack(packed[2:])
    assert seg2.ipv6_node == 'fc00::1'
    assert seg2.algorithm == 0
    assert seg2.sid is None
    assert seg2.endpoint_behavior is None


def test_segment_type_i_with_sid():
    seg = SegmentTypeI(ipv6_node='fc00::2', algorithm=1, sid='fc00::100')
    packed = seg.pack()
    # + sid(16) = 36 bytes
    assert len(packed) == 36

    seg2 = SegmentTypeI.unpack(packed[2:])
    assert seg2.ipv6_node == 'fc00::2'
    assert seg2.sid == 'fc00::100'
    assert seg2.endpoint_behavior is None


def test_segment_type_i_with_sid_and_eb():
    eb = SRv6EndpointBehavior(endpoint_behavior=65, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    seg = SegmentTypeI(ipv6_node='fc00::3', algorithm=0, sid='fc00::200', endpoint_behavior=eb)
    packed = seg.pack()
    # + sid(16) + eb(8) = 44 bytes
    assert len(packed) == 44

    seg2 = SegmentTypeI.unpack(packed[2:])
    assert seg2.ipv6_node == 'fc00::3'
    assert seg2.sid == 'fc00::200'
    assert seg2.endpoint_behavior is not None
    assert seg2.endpoint_behavior.endpoint_behavior == 65
    assert seg2.endpoint_behavior.lb_length == 32
    assert seg2.endpoint_behavior.fun_length == 16


def test_segment_type_i_json():
    seg = SegmentTypeI(ipv6_node='fc00::4', algorithm=0)
    j = seg.json()
    assert '"type": "I"' in j
    assert 'fc00::4' in j
    assert '"algorithm": 0' in j


# ============================================================= Segment Type J


def test_segment_type_j_no_sid():
    seg = SegmentTypeJ(local_if_id=1, local_ipv6='fc00::1', remote_if_id=2, remote_ipv6='fc00::2', algorithm=0)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + alg(1) + local_if(4) + local_ipv6(16) + remote_if(4) + remote_ipv6(16) = 44 bytes
    assert len(packed) == 44
    assert packed[0] == 15

    seg2 = SegmentTypeJ.unpack(packed[2:])
    assert seg2.local_if_id == 1
    assert seg2.local_ipv6 == 'fc00::1'
    assert seg2.remote_if_id == 2
    assert seg2.remote_ipv6 == 'fc00::2'
    assert seg2.algorithm == 0
    assert seg2.sid is None


def test_segment_type_j_with_sid():
    seg = SegmentTypeJ(
        local_if_id=3, local_ipv6='fc00::3', remote_if_id=4, remote_ipv6='fc00::4', algorithm=1, sid='fc00::300'
    )
    packed = seg.pack()
    # + sid(16) = 60 bytes
    assert len(packed) == 60

    seg2 = SegmentTypeJ.unpack(packed[2:])
    assert seg2.sid == 'fc00::300'
    assert seg2.endpoint_behavior is None


def test_segment_type_j_with_sid_and_eb():
    eb = SRv6EndpointBehavior(endpoint_behavior=65, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    seg = SegmentTypeJ(
        local_if_id=5,
        local_ipv6='fc00::5',
        remote_if_id=6,
        remote_ipv6='fc00::6',
        algorithm=0,
        sid='fc00::400',
        endpoint_behavior=eb,
    )
    packed = seg.pack()
    # + sid(16) + eb(8) = 68 bytes
    assert len(packed) == 68

    seg2 = SegmentTypeJ.unpack(packed[2:])
    assert seg2.endpoint_behavior is not None
    assert seg2.endpoint_behavior.endpoint_behavior == 65


def test_segment_type_j_json():
    seg = SegmentTypeJ(local_if_id=7, local_ipv6='fc00::7', remote_if_id=8, remote_ipv6='fc00::8', algorithm=0)
    j = seg.json()
    assert '"type": "J"' in j
    assert '"local_if_id": 7' in j
    assert '"algorithm": 0' in j


# ============================================================= Segment Type K


def test_segment_type_k_no_sid():
    seg = SegmentTypeK(local_ipv6='fc00::1', remote_ipv6='fc00::2', algorithm=0)
    packed = seg.pack()
    # type(1) + length(1) + flags(1) + algorithm(1) + local_ipv6(16) + remote_ipv6(16) = 36 bytes
    assert len(packed) == 36
    assert packed[0] == 16

    seg2 = SegmentTypeK.unpack(packed[2:])
    assert seg2.local_ipv6 == 'fc00::1'
    assert seg2.remote_ipv6 == 'fc00::2'
    assert seg2.algorithm == 0
    assert seg2.sid is None
    assert seg2.endpoint_behavior is None


def test_segment_type_k_with_sid():
    seg = SegmentTypeK(local_ipv6='fc00::3', remote_ipv6='fc00::4', algorithm=1, sid='fc00::500')
    packed = seg.pack()
    # + sid(16) = 52 bytes
    assert len(packed) == 52

    seg2 = SegmentTypeK.unpack(packed[2:])
    assert seg2.local_ipv6 == 'fc00::3'
    assert seg2.remote_ipv6 == 'fc00::4'
    assert seg2.sid == 'fc00::500'
    assert seg2.endpoint_behavior is None


def test_segment_type_k_with_sid_and_eb():
    eb = SRv6EndpointBehavior(endpoint_behavior=65, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    seg = SegmentTypeK(local_ipv6='fc00::5', remote_ipv6='fc00::6', algorithm=0, sid='fc00::600', endpoint_behavior=eb)
    packed = seg.pack()
    # + sid(16) + eb(8) = 60 bytes
    assert len(packed) == 60

    seg2 = SegmentTypeK.unpack(packed[2:])
    assert seg2.local_ipv6 == 'fc00::5'
    assert seg2.remote_ipv6 == 'fc00::6'
    assert seg2.sid == 'fc00::600'
    assert seg2.endpoint_behavior is not None
    assert seg2.endpoint_behavior.endpoint_behavior == 65
    assert seg2.endpoint_behavior.lb_length == 32
    assert seg2.endpoint_behavior.fun_length == 16


def test_segment_type_k_json():
    seg = SegmentTypeK(local_ipv6='fc00::7', remote_ipv6='fc00::8', algorithm=0)
    j = seg.json()
    assert '"type": "K"' in j
    assert 'fc00::7' in j
    assert '"algorithm": 0' in j


# ============================================================= Segment Types C-K in SegmentList


def test_segment_list_with_type_c_and_d():
    weight = WeightSubSubTLV(weight=1)
    segments = [
        SegmentTypeC(ipv4_node='10.0.0.1', algorithm=0, sid=16001),
        SegmentTypeD(ipv6_node='fc00::1', algorithm=0),
    ]
    tlv = SegmentListSubTLV(weight=weight, segments=segments)
    packed = tlv.pack()

    tlv2 = SegmentListSubTLV.unpack(packed[3:])
    assert tlv2.weight.weight == 1
    assert len(tlv2.segments) == 2
    assert isinstance(tlv2.segments[0], SegmentTypeC)
    assert isinstance(tlv2.segments[1], SegmentTypeD)
    assert tlv2.segments[0].ipv4_node == '10.0.0.1'
    assert tlv2.segments[0].sid == 16001
    assert tlv2.segments[1].ipv6_node == 'fc00::1'


def test_segment_list_with_type_e_and_f():
    weight = WeightSubSubTLV(weight=2)
    segments = [
        SegmentTypeE(local_if_id=1, ipv4_node='10.0.0.1', sid=16002),
        SegmentTypeF(local_ipv4='192.168.1.1', remote_ipv4='192.168.1.2'),
    ]
    tlv = SegmentListSubTLV(weight=weight, segments=segments)
    packed = tlv.pack()

    tlv2 = SegmentListSubTLV.unpack(packed[3:])
    assert len(tlv2.segments) == 2
    assert isinstance(tlv2.segments[0], SegmentTypeE)
    assert isinstance(tlv2.segments[1], SegmentTypeF)
    assert tlv2.segments[0].local_if_id == 1
    assert tlv2.segments[0].sid == 16002
    assert tlv2.segments[1].local_ipv4 == '192.168.1.1'


def test_segment_list_with_type_g_and_h():
    weight = WeightSubSubTLV(weight=3)
    segments = [
        SegmentTypeG(local_if_id=1, local_ipv6='fc00::1', remote_if_id=2, remote_ipv6='fc00::2', sid=16003),
        SegmentTypeH(local_ipv6='fc00::3', remote_ipv6='fc00::4'),
    ]
    tlv = SegmentListSubTLV(weight=weight, segments=segments)
    packed = tlv.pack()

    tlv2 = SegmentListSubTLV.unpack(packed[3:])
    assert len(tlv2.segments) == 2
    assert isinstance(tlv2.segments[0], SegmentTypeG)
    assert isinstance(tlv2.segments[1], SegmentTypeH)
    assert tlv2.segments[0].sid == 16003


def test_segment_list_with_type_i_j_k():
    eb = SRv6EndpointBehavior(endpoint_behavior=65, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    weight = WeightSubSubTLV(weight=4)
    segments = [
        SegmentTypeI(ipv6_node='fc00::1', algorithm=0, sid='fc00::100', endpoint_behavior=eb),
        SegmentTypeJ(
            local_if_id=1, local_ipv6='fc00::2', remote_if_id=2, remote_ipv6='fc00::3', algorithm=0, sid='fc00::200'
        ),
        SegmentTypeK(local_ipv6='fc00::4', remote_ipv6='fc00::5', algorithm=0),
    ]
    tlv = SegmentListSubTLV(weight=weight, segments=segments)
    packed = tlv.pack()

    tlv2 = SegmentListSubTLV.unpack(packed[3:])
    assert len(tlv2.segments) == 3
    assert isinstance(tlv2.segments[0], SegmentTypeI)
    assert isinstance(tlv2.segments[1], SegmentTypeJ)
    assert isinstance(tlv2.segments[2], SegmentTypeK)
    assert tlv2.segments[0].sid == 'fc00::100'
    assert tlv2.segments[0].endpoint_behavior is not None
    assert tlv2.segments[0].endpoint_behavior.endpoint_behavior == 65
    assert tlv2.segments[1].sid == 'fc00::200'
    assert tlv2.segments[2].sid is None


# ============================================================= RFC 9012 Compliance


def test_rfc9012_subtlv_type_lt_128_uses_1byte_length():
    """Verify sub-TLVs with type < 128 use 1-octet length field per RFC 9012."""
    # Test all SR-Policy sub-TLVs with type < 128
    test_cases = [
        (PreferenceSubTLV(preference=100), 12, 6),  # type, expected_value_len (RFC 9830: Flags:1 + Reserved:1 + Pref:4)
        (BindingSIDSubTLV(label=24000), 13, 6),
        (PrioritySubTLV(priority=5), 15, 2),
        (SRv6BindingSIDSubTLV(sid='fc00::1'), 20, 18),
    ]

    for subtlv, expected_type, expected_value_len in test_cases:
        packed = subtlv.pack()
        assert packed[0] == expected_type, f'Type mismatch for {type(subtlv).__name__}'
        assert packed[0] < 128, f'{type(subtlv).__name__} type should be < 128'

        # For type < 128: header is type(1) + length(1) = 2 bytes
        length_field = packed[1]
        assert length_field == expected_value_len, (
            f'{type(subtlv).__name__}: length field should be {expected_value_len}, got {length_field}'
        )
        assert len(packed) == 2 + expected_value_len, (
            f'{type(subtlv).__name__}: total length should be {2 + expected_value_len}, got {len(packed)}'
        )


def test_rfc9012_subtlv_type_ge_128_uses_2byte_length():
    """Verify sub-TLVs with type >= 128 use 2-octet length field per RFC 9012."""
    # Test all SR-Policy sub-TLVs with type >= 128
    test_cases = [
        (
            SegmentListSubTLV(weight=WeightSubSubTLV(weight=1), segments=[SegmentTypeA(label=16001)]),
            128,
            17,
        ),  # Reserved(1) + Weight sub-sub-TLV(8) + Segment Type A(8) = 17
        (CandidatePathNameSubTLV(name='cp'), 129, 3),  # Type 129, reserved(1) + 'cp'(2)
        (PolicyNameSubTLV(name='test'), 130, 5),  # Type 130, reserved(1) + 'test'(4)
    ]

    for subtlv, expected_type, expected_value_len in test_cases:
        packed = subtlv.pack()
        assert packed[0] == expected_type, f'Type mismatch for {type(subtlv).__name__}'
        assert packed[0] >= 128, f'{type(subtlv).__name__} type should be >= 128'

        # For type >= 128: header is type(1) + length(2) = 3 bytes
        length_field = int.from_bytes(packed[1:3], 'big')
        assert length_field == expected_value_len, (
            f'{type(subtlv).__name__}: length field should be {expected_value_len}, got {length_field}'
        )
        assert len(packed) == 3 + expected_value_len, (
            f'{type(subtlv).__name__}: total length should be {3 + expected_value_len}, got {len(packed)}'
        )


def test_rfc9012_subsubtlv_encoding():
    """Verify segment list sub-sub-TLVs (all type < 128) use 1-octet length."""
    # All segment list sub-sub-TLVs have type < 128
    test_cases = [
        (WeightSubSubTLV(weight=1), 9, 6),  # RFC 9830: Flags(1) + Reserved(1) + Weight(4)
        (SegmentTypeA(label=16001), 1, 6),
        (SegmentTypeB(sid='fc00::1'), 13, 18),
    ]

    for subtlv, expected_type, expected_value_len in test_cases:
        packed = subtlv.pack()
        assert packed[0] == expected_type
        assert packed[0] < 128

        # All sub-sub-TLVs use 1-byte length
        length_field = packed[1]
        assert length_field == expected_value_len
        assert len(packed) == 2 + expected_value_len


def test_rfc9012_round_trip_type_lt_128():
    """Test pack/unpack round-trip for sub-TLVs with type < 128."""
    from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV

    original = PreferenceSubTLV(preference=100)
    packed = original.pack()

    # Verify encoding per RFC 9830
    assert packed[0] == 12  # type
    assert packed[1] == 6  # 1-byte length: Flags(1) + Reserved(1) + Preference(4) = 6

    # Unpack and verify
    unpacked_list = SubTLV.unpack_subtlvs(packed)
    assert len(unpacked_list) == 1
    unpacked = unpacked_list[0]
    assert isinstance(unpacked, PreferenceSubTLV)
    assert unpacked.preference == 100


def test_rfc9012_round_trip_type_ge_128():
    """Test pack/unpack round-trip for sub-TLVs with type >= 128."""
    from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV

    original = PolicyNameSubTLV(name='test-policy')
    packed = original.pack()

    # Verify encoding
    assert packed[0] == 130  # Type 130 = Policy Name
    length = int.from_bytes(packed[1:3], 'big')
    assert length == 12  # reserved(1) + 'test-policy'(11)

    # Unpack and verify
    unpacked_list = SubTLV.unpack_subtlvs(packed)
    assert len(unpacked_list) == 1
    unpacked = unpacked_list[0]
    assert isinstance(unpacked, PolicyNameSubTLV)
    assert unpacked.name == 'test-policy'


def test_rfc9012_mixed_subtlv_types():
    """Test unpacking multiple sub-TLVs with mixed type ranges."""
    from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import SubTLV

    # Create wire format with both type < 128 and type >= 128
    pref = PreferenceSubTLV(preference=100)  # type 12 < 128
    seg_list = SegmentListSubTLV(  # type 128 >= 128
        weight=WeightSubSubTLV(weight=1), segments=[SegmentTypeA(label=16001)]
    )
    policy = PolicyNameSubTLV(name='test')  # type 129 >= 128

    # Pack all together
    wire_data = pref.pack() + seg_list.pack() + policy.pack()

    # Unpack and verify all three
    unpacked = SubTLV.unpack_subtlvs(wire_data)
    assert len(unpacked) == 3

    assert isinstance(unpacked[0], PreferenceSubTLV)
    assert unpacked[0].preference == 100

    assert isinstance(unpacked[1], SegmentListSubTLV)
    assert unpacked[1].weight.weight == 1

    assert isinstance(unpacked[2], PolicyNameSubTLV)
    assert unpacked[2].name == 'test'


def test_rfc9012_sr_policy_tunnel_round_trip():
    """Test complete SR-Policy tunnel encode/decode with RFC 9012 compliance."""
    original = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(preference=100),
            BindingSIDSubTLV(label=24000),
            SegmentListSubTLV(
                weight=WeightSubSubTLV(weight=1), segments=[SegmentTypeA(label=16001), SegmentTypeA(label=16002)]
            ),
            PolicyNameSubTLV(name='my-policy'),
        ]
    )

    # Pack to wire format
    wire_data = original.pack_value()

    # Unpack from wire format
    decoded = SRPolicyTunnel.unpack(wire_data)

    # Verify all sub-TLVs decoded correctly
    assert len(decoded.subtlvs) == 4

    assert isinstance(decoded.subtlvs[0], PreferenceSubTLV)
    assert decoded.subtlvs[0].preference == 100

    assert isinstance(decoded.subtlvs[1], BindingSIDSubTLV)
    assert decoded.subtlvs[1].label == 24000

    assert isinstance(decoded.subtlvs[2], SegmentListSubTLV)
    assert decoded.subtlvs[2].weight.weight == 1
    assert len(decoded.subtlvs[2].segments) == 2
    assert decoded.subtlvs[2].segments[0].label == 16001
    assert decoded.subtlvs[2].segments[1].label == 16002

    assert isinstance(decoded.subtlvs[3], PolicyNameSubTLV)
    assert decoded.subtlvs[3].name == 'my-policy'

    # Verify re-encoding produces identical wire format
    reencoded = decoded.pack_value()
    assert wire_data == reencoded


# ============================================================= __str__ methods


def test_str_preference_subtlv():
    assert str(PreferenceSubTLV(100)) == 'preference 100'


def test_str_priority_subtlv():
    assert str(PrioritySubTLV(10)) == 'priority 10'


def test_str_binding_sid_mpls():
    assert str(BindingSIDSubTLV(label=24000)) == 'binding-sid mpls 24000'


def test_str_binding_sid_null():
    assert str(BindingSIDSubTLV(label=None)) == 'binding-sid null'


def test_str_srv6_binding_sid():
    assert str(SRv6BindingSIDSubTLV(sid='fc00::1')) == 'srv6-binding-sid fc00::1'


def test_str_policy_name_subtlv():
    assert str(PolicyNameSubTLV(name='my-policy')) == 'policy-name "my-policy"'


def test_str_candidate_path_name_subtlv():
    assert str(CandidatePathNameSubTLV(name='cp-primary')) == 'candidate-path-name "cp-primary"'


def test_str_segment_list_with_type_a():
    tlv = SegmentListSubTLV(WeightSubSubTLV(1), [SegmentTypeA(16001)])
    s = str(tlv)
    assert 'segment-list' in s
    assert 'weight 1' in s
    assert '16001' in s


# ============================================================= Encode: verify exact bytes produced


def test_pack_exact_bytes_preference():
    # type(1)=0x0c + length(1)=6 + flags(1)=0 + reserved(1)=0 + preference(4)=100
    assert PreferenceSubTLV(preference=100).pack() == b'\x0c\x06\x00\x00\x00\x00\x00\x64'


def test_pack_exact_bytes_priority():
    # type(1)=0x0f + length(1)=2 + priority(1)=10 + reserved(1)=0
    assert PrioritySubTLV(priority=10).pack() == b'\x0f\x02\x0a\x00'


def test_pack_exact_bytes_binding_sid():
    # type(1)=0x0d + length(1)=6 + flags(1)=0x10 + reserved(1)=0
    # label_entry = (24000 << 12) | 0x100 = 0x05DC0100
    assert BindingSIDSubTLV(label=24000).pack() == b'\x0d\x06\x10\x00\x05\xdc\x01\x00'


def test_pack_exact_bytes_weight():
    # type(1)=9 + length(1)=6 + flags(1)=0 + reserved(1)=0 + weight(4)=1
    assert WeightSubSubTLV(weight=1).pack() == b'\x09\x06\x00\x00\x00\x00\x00\x01'


def test_pack_exact_bytes_segment_type_a_with_s_bit():
    # type(1)=1 + length(1)=6 + flags(1)=0 + reserved(1)=0
    # label_entry = (16001 << 12) | 0x100 = 0x03E81100 → bytes: 03 e8 11 00
    assert SegmentTypeA(label=16001).pack(is_last=True) == b'\x01\x06\x00\x00\x03\xe8\x11\x00'


def test_pack_exact_bytes_segment_type_a_without_s_bit():
    # label_entry = (16001 << 12) = 0x03E81000 → bytes: 03 e8 10 00
    assert SegmentTypeA(label=16001).pack(is_last=False) == b'\x01\x06\x00\x00\x03\xe8\x10\x00'


# ============================================================= Decode: from hardcoded bytes


def test_decode_from_bytes_preference():
    """Decode PreferenceSubTLV from known wire bytes, independent of pack()."""
    # Flags(1)=0, Reserved(1)=0, Preference(4)=100
    wire_value = b'\x00\x00\x00\x00\x00\x64'
    tlv = PreferenceSubTLV.unpack(wire_value)
    assert tlv.preference == 100
    assert tlv.flags == 0


def test_decode_from_bytes_priority():
    # priority(1)=10, reserved(1)=0
    tlv = PrioritySubTLV.unpack(b'\x0a\x00')
    assert tlv.priority == 10


def test_decode_from_bytes_binding_sid_with_label():
    # flags=0x10 (B-flag set), reserved=0, label_entry=(24000<<12)|0x100=0x05DC0100
    wire_value = b'\x10\x00\x05\xdc\x01\x00'
    tlv = BindingSIDSubTLV.unpack(wire_value)
    assert tlv.label == 24000


def test_decode_from_bytes_binding_sid_null():
    # flags=0, reserved=0, no label entry (only 2 bytes)
    tlv = BindingSIDSubTLV.unpack(b'\x00\x00')
    assert tlv.label is None


def test_decode_from_bytes_srv6_binding_sid():
    sid_bytes = socket.inet_pton(socket.AF_INET6, 'fc00::1')
    wire_value = b'\x00\x00' + sid_bytes  # flags=0, reserved=0, SID
    tlv = SRv6BindingSIDSubTLV.unpack(wire_value)
    assert tlv.sid == 'fc00::1'
    assert tlv.endpoint_behavior is None


def test_decode_from_bytes_policy_name():
    # flags(1)=0, name='low-latency'
    wire_value = b'\x00' + b'low-latency'
    tlv = PolicyNameSubTLV.unpack(wire_value)
    assert tlv.name == 'low-latency'
    assert tlv.flags == 0


def test_decode_from_bytes_candidate_path_name():
    wire_value = b'\x00' + b'primary'
    tlv = CandidatePathNameSubTLV.unpack(wire_value)
    assert tlv.name == 'primary'


def test_decode_from_bytes_weight():
    # flags(1)=0, reserved(1)=0, weight(4)=5
    wire_value = b'\x00\x00\x00\x00\x00\x05'
    w = WeightSubSubTLV.unpack(wire_value)
    assert w.weight == 5


def test_decode_from_bytes_segment_type_a():
    # flags=0, reserved=0, label_entry=(16001<<12)|0x100=0x03E81100
    wire_value = b'\x00\x00\x03\xe8\x11\x00'
    seg = SegmentTypeA.unpack(wire_value)
    assert seg.label == 16001
    assert seg.s is True
    assert seg.tc == 0
    assert seg.ttl == 0


def test_decode_from_bytes_segment_type_a_no_s_bit():
    # label_entry = (16001 << 12) = 0x03E81000 → no S-bit
    wire_value = b'\x00\x00\x03\xe8\x10\x00'
    seg = SegmentTypeA.unpack(wire_value)
    assert seg.label == 16001
    assert seg.s is False


def test_decode_from_bytes_segment_type_b_no_eb():
    sid_bytes = socket.inet_pton(socket.AF_INET6, 'fc00::2')
    # flags=0 (B-flag NOT set), reserved=0, SID — no endpoint behavior
    wire_value = b'\x00\x00' + sid_bytes
    seg = SegmentTypeB.unpack(wire_value)
    assert seg.sid == 'fc00::2'
    assert seg.endpoint_behavior is None


def test_decode_from_bytes_segment_type_b_with_eb():
    sid_bytes = socket.inet_pton(socket.AF_INET6, 'fc00::3')
    # flags=0x10 (B-flag set), reserved=0, SID, endpoint_behavior
    # endpoint_behavior: behavior(2)=65, reserved(2)=0, lb(1)=32, ln(1)=0, fun(1)=16, arg(1)=0
    eb_bytes = struct.pack('!HHBBBB', 65, 0, 32, 0, 16, 0)
    wire_value = b'\x10\x00' + sid_bytes + eb_bytes
    seg = SegmentTypeB.unpack(wire_value)
    assert seg.sid == 'fc00::3'
    assert seg.endpoint_behavior is not None
    assert seg.endpoint_behavior.endpoint_behavior == 65
    assert seg.endpoint_behavior.lb_length == 32
    assert seg.endpoint_behavior.fun_length == 16


def test_decode_from_bytes_segment_list():
    """Decode SegmentListSubTLV from hardcoded wire bytes."""
    # Value (passed to unpack): reserved(1) + WeightSubSubTLV(8) + SegmentTypeA(8)
    wire_value = (
        b'\x00'  # reserved
        b'\x09\x06\x00\x00\x00\x00\x00\x01'  # WeightSubSubTLV(weight=1)
        b'\x01\x06\x00\x00\x03\xe8\x11\x00'  # SegmentTypeA(label=16001, s=True)
    )
    tlv = SegmentListSubTLV.unpack(wire_value)
    assert tlv.weight.weight == 1
    assert len(tlv.segments) == 1
    assert isinstance(tlv.segments[0], SegmentTypeA)
    assert tlv.segments[0].label == 16001
    assert tlv.segments[0].s is True


def test_decode_from_bytes_segment_list_multiple_segments():
    """Decode SegmentListSubTLV with two segments from hardcoded bytes."""
    # label_entry for 16001 without s-bit: 0x03E81000
    # label_entry for 16002 with s-bit:    0x03E82100
    #   16002 = 0x3E82; (0x3E82 << 12) = 0x03E82000; | 0x100 = 0x03E82100
    wire_value = (
        b'\x00'  # reserved
        b'\x09\x06\x00\x00\x00\x00\x00\x02'  # WeightSubSubTLV(weight=2)
        b'\x01\x06\x00\x00\x03\xe8\x10\x00'  # SegmentTypeA(label=16001, s=False)
        b'\x01\x06\x00\x00\x03\xe8\x21\x00'  # SegmentTypeA(label=16002, s=True)
    )
    tlv = SegmentListSubTLV.unpack(wire_value)
    assert tlv.weight.weight == 2
    assert len(tlv.segments) == 2
    assert tlv.segments[0].label == 16001
    assert tlv.segments[0].s is False
    assert tlv.segments[1].label == 16002
    assert tlv.segments[1].s is True


# ============================================================= Combined: all sub-TLVs in one tunnel


def test_tunnel_with_all_subtlvs():
    """All supported sub-TLVs in a single SRPolicyTunnel, with two segment lists."""
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(preference=100),
            PrioritySubTLV(priority=10),
            BindingSIDSubTLV(label=24000),
            CandidatePathNameSubTLV(name='cp-primary'),
            PolicyNameSubTLV(name='low-latency'),
            # Primary path (higher weight)
            SegmentListSubTLV(
                weight=WeightSubSubTLV(weight=10),
                segments=[SegmentTypeA(label=16001), SegmentTypeA(label=16002)],
            ),
            # Backup path (lower weight)
            SegmentListSubTLV(
                weight=WeightSubSubTLV(weight=5),
                segments=[SegmentTypeA(label=17001), SegmentTypeA(label=17002)],
            ),
        ]
    )
    wire = tunnel.pack_value()
    decoded = SRPolicyTunnel.unpack(wire)

    types = {type(t) for t in decoded.subtlvs}
    assert PreferenceSubTLV in types
    assert PrioritySubTLV in types
    assert BindingSIDSubTLV in types
    assert CandidatePathNameSubTLV in types
    assert PolicyNameSubTLV in types

    pref = next(t for t in decoded.subtlvs if isinstance(t, PreferenceSubTLV))
    assert pref.preference == 100

    pri = next(t for t in decoded.subtlvs if isinstance(t, PrioritySubTLV))
    assert pri.priority == 10

    bsid = next(t for t in decoded.subtlvs if isinstance(t, BindingSIDSubTLV))
    assert bsid.label == 24000

    cpn = next(t for t in decoded.subtlvs if isinstance(t, CandidatePathNameSubTLV))
    assert cpn.name == 'cp-primary'

    pn = next(t for t in decoded.subtlvs if isinstance(t, PolicyNameSubTLV))
    assert pn.name == 'low-latency'

    seg_lists = [t for t in decoded.subtlvs if isinstance(t, SegmentListSubTLV)]
    assert len(seg_lists) == 2
    assert seg_lists[0].weight.weight == 10
    assert seg_lists[1].weight.weight == 5
    assert len(seg_lists[0].segments) == 2
    assert len(seg_lists[1].segments) == 2


def test_tunnel_with_srv6_binding_sid_and_srv6_segments():
    """SRPolicyTunnel with SRv6 binding SID and SRv6 segment types."""
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(preference=200),
            SRv6BindingSIDSubTLV(sid='fc00::1'),
            PolicyNameSubTLV(name='srv6-path'),
            SegmentListSubTLV(
                weight=WeightSubSubTLV(weight=1),
                segments=[SegmentTypeB(sid='fc00::100'), SegmentTypeB(sid='fc00::200')],
            ),
        ]
    )
    wire = tunnel.pack_value()
    decoded = SRPolicyTunnel.unpack(wire)

    srv6bsid = next(t for t in decoded.subtlvs if isinstance(t, SRv6BindingSIDSubTLV))
    assert srv6bsid.sid == 'fc00::1'

    seg_list = next(t for t in decoded.subtlvs if isinstance(t, SegmentListSubTLV))
    assert len(seg_list.segments) == 2
    assert isinstance(seg_list.segments[0], SegmentTypeB)
    assert seg_list.segments[0].sid == 'fc00::100'
    assert isinstance(seg_list.segments[1], SegmentTypeB)
    assert seg_list.segments[1].sid == 'fc00::200'


# ============================================================= Multiple segment lists with different types


def test_tunnel_multiple_segment_lists_different_types():
    """ECMP: three segment lists, each with a different mix of segment types."""
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(preference=100),
            # List 1 (weight 2): MPLS — Type C + Type A
            SegmentListSubTLV(
                weight=WeightSubSubTLV(weight=2),
                segments=[
                    SegmentTypeC(ipv4_node='10.0.0.1', algorithm=0, sid=16001),
                    SegmentTypeA(label=16002),
                ],
            ),
            # List 2 (weight 1): MPLS adjacency — Type F
            SegmentListSubTLV(
                weight=WeightSubSubTLV(weight=1),
                segments=[
                    SegmentTypeF(local_ipv4='192.168.1.1', remote_ipv4='192.168.1.2', sid=16003),
                ],
            ),
            # List 3 (weight 1): SRv6 — Type B + Type I
            SegmentListSubTLV(
                weight=WeightSubSubTLV(weight=1),
                segments=[
                    SegmentTypeB(sid='fc00::1'),
                    SegmentTypeI(ipv6_node='fc00::2', algorithm=0, sid='fc00::100'),
                ],
            ),
        ]
    )
    wire = tunnel.pack_value()
    decoded = SRPolicyTunnel.unpack(wire)

    seg_lists = [t for t in decoded.subtlvs if isinstance(t, SegmentListSubTLV)]
    assert len(seg_lists) == 3

    # List 1: C + A
    assert seg_lists[0].weight.weight == 2
    assert isinstance(seg_lists[0].segments[0], SegmentTypeC)
    assert seg_lists[0].segments[0].ipv4_node == '10.0.0.1'
    assert seg_lists[0].segments[0].sid == 16001
    assert isinstance(seg_lists[0].segments[1], SegmentTypeA)
    assert seg_lists[0].segments[1].label == 16002

    # List 2: F
    assert seg_lists[1].weight.weight == 1
    assert isinstance(seg_lists[1].segments[0], SegmentTypeF)
    assert seg_lists[1].segments[0].local_ipv4 == '192.168.1.1'
    assert seg_lists[1].segments[0].sid == 16003

    # List 3: B + I
    assert seg_lists[2].weight.weight == 1
    assert isinstance(seg_lists[2].segments[0], SegmentTypeB)
    assert seg_lists[2].segments[0].sid == 'fc00::1'
    assert isinstance(seg_lists[2].segments[1], SegmentTypeI)
    assert seg_lists[2].segments[1].ipv6_node == 'fc00::2'
    assert seg_lists[2].segments[1].sid == 'fc00::100'


# ============================================================= All segment types in one list


def test_segment_list_all_mpls_types_combined():
    """Segment list with all MPLS-based types (A, C, D, E, F, G, H) in one list."""
    segments = [
        SegmentTypeA(label=16000),
        SegmentTypeC(ipv4_node='10.0.0.1', algorithm=0, sid=16001),
        SegmentTypeD(ipv6_node='fc00::1', algorithm=0, sid=16002),
        SegmentTypeE(local_if_id=1, ipv4_node='10.0.0.2', sid=16003),
        SegmentTypeF(local_ipv4='192.168.1.1', remote_ipv4='192.168.1.2', sid=16004),
        SegmentTypeG(local_if_id=1, local_ipv6='fc00::2', remote_if_id=2, remote_ipv6='fc00::3', sid=16005),
        SegmentTypeH(local_ipv6='fc00::4', remote_ipv6='fc00::5', sid=16006),
    ]
    tlv = SegmentListSubTLV(weight=WeightSubSubTLV(weight=1), segments=segments)
    wire = tlv.pack()
    decoded = SegmentListSubTLV.unpack(wire[3:])  # skip 3-byte type(1)+length(2) header

    assert len(decoded.segments) == 7
    assert isinstance(decoded.segments[0], SegmentTypeA)
    assert decoded.segments[0].label == 16000
    assert isinstance(decoded.segments[1], SegmentTypeC)
    assert decoded.segments[1].ipv4_node == '10.0.0.1'
    assert decoded.segments[1].sid == 16001
    assert isinstance(decoded.segments[2], SegmentTypeD)
    assert decoded.segments[2].ipv6_node == 'fc00::1'
    assert decoded.segments[2].sid == 16002
    assert isinstance(decoded.segments[3], SegmentTypeE)
    assert decoded.segments[3].local_if_id == 1
    assert decoded.segments[3].sid == 16003
    assert isinstance(decoded.segments[4], SegmentTypeF)
    assert decoded.segments[4].local_ipv4 == '192.168.1.1'
    assert decoded.segments[4].sid == 16004
    assert isinstance(decoded.segments[5], SegmentTypeG)
    assert decoded.segments[5].local_if_id == 1
    assert decoded.segments[5].sid == 16005
    assert isinstance(decoded.segments[6], SegmentTypeH)
    assert decoded.segments[6].local_ipv6 == 'fc00::4'
    assert decoded.segments[6].sid == 16006


def test_segment_list_all_srv6_types_combined():
    """Segment list with all SRv6-based types (B, I, J, K) in one list, all with endpoint behavior."""
    eb = SRv6EndpointBehavior(endpoint_behavior=65, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    segments = [
        SegmentTypeB(sid='fc00::1', endpoint_behavior=eb),
        SegmentTypeI(ipv6_node='fc00::2', algorithm=0, sid='fc00::100', endpoint_behavior=eb),
        SegmentTypeJ(
            local_if_id=1,
            local_ipv6='fc00::3',
            remote_if_id=2,
            remote_ipv6='fc00::4',
            algorithm=0,
            sid='fc00::200',
            endpoint_behavior=eb,
        ),
        SegmentTypeK(local_ipv6='fc00::5', remote_ipv6='fc00::6', algorithm=0, sid='fc00::300', endpoint_behavior=eb),
    ]
    tlv = SegmentListSubTLV(weight=WeightSubSubTLV(weight=1), segments=segments)
    wire = tlv.pack()
    decoded = SegmentListSubTLV.unpack(wire[3:])

    assert len(decoded.segments) == 4
    assert isinstance(decoded.segments[0], SegmentTypeB)
    assert decoded.segments[0].sid == 'fc00::1'
    assert decoded.segments[0].endpoint_behavior is not None
    assert decoded.segments[0].endpoint_behavior.endpoint_behavior == 65

    assert isinstance(decoded.segments[1], SegmentTypeI)
    assert decoded.segments[1].ipv6_node == 'fc00::2'
    assert decoded.segments[1].sid == 'fc00::100'
    assert decoded.segments[1].endpoint_behavior.lb_length == 32

    assert isinstance(decoded.segments[2], SegmentTypeJ)
    assert decoded.segments[2].local_if_id == 1
    assert decoded.segments[2].sid == 'fc00::200'
    assert decoded.segments[2].endpoint_behavior.fun_length == 16

    assert isinstance(decoded.segments[3], SegmentTypeK)
    assert decoded.segments[3].local_ipv6 == 'fc00::5'
    assert decoded.segments[3].sid == 'fc00::300'
    assert decoded.segments[3].endpoint_behavior.arg_length == 0


# ============================================================= json() coverage for full tunnel


def test_json_tunnel_all_subtlvs():
    """json() output contains keys for every sub-TLV type in the tunnel."""
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(preference=100),
            PrioritySubTLV(priority=10),
            BindingSIDSubTLV(label=24000),
            PolicyNameSubTLV(name='test-policy'),
            CandidatePathNameSubTLV(name='cp-1'),
            SegmentListSubTLV(WeightSubSubTLV(1), [SegmentTypeA(16001)]),
            SegmentListSubTLV(WeightSubSubTLV(2), [SegmentTypeB(sid='fc00::1')]),
        ]
    )
    j = tunnel.json()
    assert '"preference": 100' in j
    assert '"priority": 10' in j
    assert '"binding-sid"' in j
    assert '"policy-name": "test-policy"' in j
    assert '"candidate-path-name": "cp-1"' in j
    assert '"segment-lists"' in j
    # Both lists should appear
    assert '"weight": 1' in j
    assert '"weight": 2' in j


def test_json_tunnel_srv6_binding_sid():
    tunnel = SRPolicyTunnel(
        subtlvs=[
            PreferenceSubTLV(preference=200),
            SRv6BindingSIDSubTLV(sid='fc00::1'),
            SegmentListSubTLV(WeightSubSubTLV(1), [SegmentTypeB(sid='fc00::10')]),
        ]
    )
    j = tunnel.json()
    assert '"srv6-binding-sid": "fc00::1"' in j
    assert '"type": "B"' in j


def test_json_segment_list_with_type_c_to_k():
    """json() for a segment list containing types C through K."""
    eb = SRv6EndpointBehavior(endpoint_behavior=65, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    tlv = SegmentListSubTLV(
        weight=WeightSubSubTLV(weight=3),
        segments=[
            SegmentTypeC(ipv4_node='10.0.0.1', algorithm=0, sid=16001),
            SegmentTypeI(ipv6_node='fc00::1', algorithm=0, sid='fc00::100', endpoint_behavior=eb),
            SegmentTypeK(local_ipv6='fc00::2', remote_ipv6='fc00::3', algorithm=0),
        ],
    )
    j = tlv.json()
    assert '"weight": 3' in j
    assert '"type": "C"' in j
    assert '"type": "I"' in j
    assert '"type": "K"' in j
    assert '10.0.0.1' in j
    assert 'fc00::100' in j


# ============================================================= JSON validity


def test_srv6_binding_sid_json_is_key_value_fragment():
    """json() must return a key-value fragment, not a standalone JSON object.

    Regression test: the old implementation returned {"srv6-binding-sid": "..."}
    (with surrounding braces) which produced invalid JSON when embedded inside
    SRPolicyTunnel.json().
    """
    import json as _json

    tlv = SRv6BindingSIDSubTLV(sid='fc00::1')
    fragment = tlv.json()
    assert not fragment.startswith('{'), 'json() must not wrap result in { }'
    assert fragment == '"srv6-binding-sid": "fc00::1"'
    # Embedding in an object must produce valid JSON
    assert _json.loads('{' + fragment + '}') == {'srv6-binding-sid': 'fc00::1'}


def test_tunnel_encap_json_is_valid_json():
    """TunnelEncap.json() must produce parseable JSON for all sub-TLV combinations."""
    import json as _json

    eb = SRv6EndpointBehavior(endpoint_behavior=65, lb_length=32, ln_length=0, fun_length=16, arg_length=0)
    tunnel = TunnelEncap(
        tunnel_tlvs=[
            SRPolicyTunnel(
                subtlvs=[
                    PreferenceSubTLV(preference=100),
                    SRv6BindingSIDSubTLV(sid='fc00::1', endpoint_behavior=eb),
                    SegmentListSubTLV(WeightSubSubTLV(1), [SegmentTypeB(sid='fc00::1', endpoint_behavior=eb)]),
                    PolicyNameSubTLV(name='test'),
                    CandidatePathNameSubTLV(name='primary'),
                ]
            )
        ]
    )
    parsed = _json.loads(tunnel.json())
    sr = parsed['sr-policy']
    assert sr['preference'] == 100
    assert isinstance(sr['srv6-binding-sid'], dict)
    assert sr['srv6-binding-sid']['sid'] == 'fc00::1'
    assert len(sr['segment-lists']) == 1
    assert sr['policy-name'] == 'test'
    assert sr['candidate-path-name'] == 'primary'


def test_tunnel_encap_in_attribute_collection_json():
    """TunnelEncap must appear as 'tunnel-encap' key (not attribute-0x17-0xC0) in JSON."""
    import json as _json

    from exabgp.bgp.message.update.attribute.collection import AttributeCollection

    tunnel = TunnelEncap(tunnel_tlvs=[SRPolicyTunnel(subtlvs=[PreferenceSubTLV(preference=200)])])
    coll = AttributeCollection()
    coll.add(tunnel)
    json_str = '{' + coll.json() + '}'
    parsed = _json.loads(json_str)
    assert 'tunnel-encap' in parsed, 'Expected "tunnel-encap" key, got: ' + str(list(parsed.keys()))
    assert 'attribute-0x17-0xC0' not in parsed
