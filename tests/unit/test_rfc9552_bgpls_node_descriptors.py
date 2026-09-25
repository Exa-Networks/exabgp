#!/usr/bin/env python3
# encoding: utf-8

"""RFC 9552 on what a BGP-LS decoder may and may not refuse.

Two obligations which look opposed and are not.

8.2.2: "A Link-State NLRI MUST NOT be considered malformed or invalid based on
the inclusion/exclusion of TLVs or contents of the TLV fields", and 5.1:
"Unknown and unsupported types MUST be preserved and propagated within both the
NLRI and the BGP-LS Attribute."  So an unregistered Protocol-ID, and an
unregistered Node Descriptor sub-TLV code, are carried.

5.2.1: "At most, there MUST be one instance of each sub-TLV type present in any
Node Descriptor.  The sub-TLVs within a Node Descriptor MUST be arranged in
ascending order by sub-TLV type."  So a repeat, and a descent, are refused.

They coexist because the arity and order checks read the sub-TLV TYPE CODE and
compare it to the previous type code, and to nothing else: never a value, never
a table of registered codes.  Order and arity are not contents.  The last class
below is the test of exactly that seam, an unregistered code held to the order
while still being accepted.
"""

from struct import pack

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.protocol.family import AFI, SAFI

NODE, LINK, PREFIXV4, PREFIXV6, SRV6SID = 1, 2, 3, 4, 6

TLV_LOCAL_NODE, TLV_REMOTE_NODE = 256, 257
TLV_IP_REACHABILITY = 265

SUB_TLV_AS, SUB_TLV_BGPLS_ID, SUB_TLV_OSPF_AREA, SUB_TLV_IGP_ROUTER = 512, 513, 514, 515
# RFC 9086 assigned 516, BGP Router Identifier, after this decoder was written
SUB_TLV_BGP_ROUTER_ID = 516

# an IS-IS Level 2 Protocol-ID, so a 515 sub-TLV has a shape the decoder knows
ISIS_L2 = 2
# IANA has assigned these three since RFC 7752 listed six codes
SEGMENT_ROUTING, BGP, RSVP_TE = 9, 7, 8


def sub_tlv(code: int, payload: bytes) -> bytes:
    return pack('!HH', code, len(payload)) + payload


AS_SUB_TLV = sub_tlv(SUB_TLV_AS, b'\x00\x00\xff\xfd')
BGPLS_ID_SUB_TLV = sub_tlv(SUB_TLV_BGPLS_ID, b'\x00\x00\x00\x01')
UNKNOWN_SUB_TLV = sub_tlv(SUB_TLV_BGP_ROUTER_ID, b'\xc0\x00\x02\x01')

IP_REACHABILITY_V4 = pack('!HH', TLV_IP_REACHABILITY, 2) + bytes([24, 192])
IP_REACHABILITY_V6 = pack('!HH', TLV_IP_REACHABILITY, 3) + bytes([32, 0x20, 0x01])


def tlv(code: int, payload: bytes) -> bytes:
    return pack('!HH', code, len(payload)) + payload


def nlri(nlri_type: int, proto_id: int, *tlvs: bytes) -> bytes:
    body = bytes([proto_id]) + b'\x00' * 8 + b''.join(tlvs)
    return pack('!HH', nlri_type, len(body)) + body


def with_descriptors(nlri_type: int, proto_id: int, *descriptors: bytes) -> bytes:
    """One NLRI of each of the five types, carrying the sub-TLVs given."""
    local = tlv(TLV_LOCAL_NODE, b''.join(descriptors))
    if nlri_type == LINK:
        return nlri(nlri_type, proto_id, local, tlv(TLV_REMOTE_NODE, AS_SUB_TLV))
    if nlri_type == PREFIXV4:
        return nlri(nlri_type, proto_id, local, IP_REACHABILITY_V4)
    if nlri_type == PREFIXV6:
        return nlri(nlri_type, proto_id, local, IP_REACHABILITY_V6)
    return nlri(nlri_type, proto_id, local)


ALL_TYPES = [NODE, LINK, PREFIXV4, PREFIXV6, SRV6SID]


def decode(wire: bytes):
    decoded, left = BGPLS.unpack_nlri(AFI.bgpls, SAFI.bgp_ls, wire, Action.ANNOUNCE, False)
    assert left == b''
    return decoded


class TestAnUnregisteredProtocolIdIsCarried:
    """RFC 9552 8.2.2: the Protocol-ID is the contents of a field."""

    @pytest.mark.parametrize('nlri_type', ALL_TYPES)
    @pytest.mark.parametrize('proto_id', [BGP, RSVP_TE, SEGMENT_ROUTING, 99, 255])
    def test_a_protocol_id_this_build_does_not_name(self, nlri_type, proto_id) -> None:
        decoded = decode(with_descriptors(nlri_type, proto_id, AS_SUB_TLV))
        assert decoded is not None
        assert decoded.json()

    @pytest.mark.parametrize('nlri_type', ALL_TYPES)
    def test_a_protocol_id_it_does_name_still_works(self, nlri_type) -> None:
        assert decode(with_descriptors(nlri_type, ISIS_L2, AS_SUB_TLV)) is not None


class TestAnUnregisteredNodeDescriptorSubTlvIsCarried:
    """RFC 9552 5.1: unknown types are preserved and propagated, not refused."""

    @pytest.mark.parametrize('nlri_type', ALL_TYPES)
    def test_bgp_router_identifier_does_not_end_the_session(self, nlri_type) -> None:
        decoded = decode(with_descriptors(nlri_type, ISIS_L2, UNKNOWN_SUB_TLV))
        assert decoded is not None
        assert decoded.json()

    def test_the_bytes_survive_byte_for_byte(self) -> None:
        from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor

        descriptor, left = NodeDescriptor.unpack(UNKNOWN_SUB_TLV, ISIS_L2)
        assert left == b''
        assert bytes(descriptor.pack()) == UNKNOWN_SUB_TLV

    def test_two_unknown_codes_do_not_collide_in_the_render(self) -> None:
        second = sub_tlv(517, b'\xde\xad')
        decoded = decode(with_descriptors(NODE, ISIS_L2, UNKNOWN_SUB_TLV, second))
        rendered = decoded.json()
        assert '516' in rendered and '517' in rendered

    def test_an_igp_router_id_under_an_unknown_protocol_is_carried(self) -> None:
        # 515's shape is defined by the Protocol-ID, so without it there is
        # nothing to read it as but bytes
        router_id = sub_tlv(SUB_TLV_IGP_ROUTER, b'\x01\x02\x03\x04\x05\x06')
        assert decode(with_descriptors(NODE, SEGMENT_ROUTING, router_id)) is not None


class TestNodeDescriptorArityAndOrder:
    """RFC 9552 5.2.1, and 8.2.2 which lists both as syntactic validation."""

    @pytest.mark.parametrize('nlri_type', ALL_TYPES)
    def test_one_sub_tlv_type_twice_is_refused(self, nlri_type) -> None:
        with pytest.raises(Notify):
            decode(with_descriptors(nlri_type, ISIS_L2, AS_SUB_TLV, AS_SUB_TLV))

    @pytest.mark.parametrize('nlri_type', ALL_TYPES)
    def test_descending_order_is_refused(self, nlri_type) -> None:
        with pytest.raises(Notify):
            decode(with_descriptors(nlri_type, ISIS_L2, BGPLS_ID_SUB_TLV, AS_SUB_TLV))

    @pytest.mark.parametrize('nlri_type', ALL_TYPES)
    def test_ascending_order_is_accepted(self, nlri_type) -> None:
        wire = with_descriptors(nlri_type, ISIS_L2, AS_SUB_TLV, BGPLS_ID_SUB_TLV)
        assert decode(wire) is not None

    def test_a_remote_node_descriptor_is_held_to_the_same_rules(self) -> None:
        local = tlv(TLV_LOCAL_NODE, AS_SUB_TLV)
        remote = tlv(TLV_REMOTE_NODE, BGPLS_ID_SUB_TLV + AS_SUB_TLV)
        with pytest.raises(Notify):
            decode(nlri(LINK, ISIS_L2, local, remote))

    def test_the_two_descriptors_do_not_share_an_order(self) -> None:
        # a Remote Node Descriptor starting again at 512 after a Local one
        # reached 513 is two descriptors, not one out of order
        local = tlv(TLV_LOCAL_NODE, AS_SUB_TLV + BGPLS_ID_SUB_TLV)
        remote = tlv(TLV_REMOTE_NODE, AS_SUB_TLV)
        assert decode(nlri(LINK, ISIS_L2, local, remote)) is not None


class TestTheSeamBetweenTheTwoObligations:
    """The order check reads a type code, so it never becomes a whitelist."""

    def test_an_unregistered_code_in_its_place_is_accepted(self) -> None:
        wire = with_descriptors(NODE, ISIS_L2, AS_SUB_TLV, BGPLS_ID_SUB_TLV, UNKNOWN_SUB_TLV)
        assert decode(wire) is not None

    def test_an_unregistered_code_out_of_place_is_refused(self) -> None:
        wire = with_descriptors(NODE, ISIS_L2, UNKNOWN_SUB_TLV, AS_SUB_TLV)
        with pytest.raises(Notify):
            decode(wire)

    def test_an_unregistered_code_twice_is_refused(self) -> None:
        wire = with_descriptors(NODE, ISIS_L2, UNKNOWN_SUB_TLV, UNKNOWN_SUB_TLV)
        with pytest.raises(Notify):
            decode(wire)
