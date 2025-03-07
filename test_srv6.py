#!/usr/bin/env python3
import json
import sys
import os

# ExaBGPのソースディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from exabgp.bgp.message.update.nlri.bgpls.srv6sid import SRv6SID, LocalNodeDescriptorSub
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure
from exabgp.bgp.message.update.nlri.bgpls.srv6sid import LocalNodeDescriptor, SRv6SIDDescriptor
from exabgp.protocol.ip import IPv6
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MultiTopology
from exabgp.bgp.message.update.nlri.bgpls.tlvs.servicechaining import ServiceChaining
from exabgp.bgp.message.update.nlri.bgpls.tlvs.opaquemetadata import OpaqueMetadata

# GoBGP
# ./gobgp global rib add -a ls srv6sid bgp
# identifier 0
# local-asn 65000
# local-bgp-ls-id 0
# local-bgp-router-id 192.168.255.1
# local-bgp-confederation-member 1
# sids fd00::1
# multi-topology-id 1
# service-type 1 traffic-type 1
# opaque-type 1 value vvf-param-hoge

# https://www.rfc-editor.org/rfc/rfc9514.html#name-srv6-sid-nlri
def encode_srv6_sid_nlri():
    protocol_id = 7 # https://www.iana.org/assignments/bgp-ls-parameters/bgp-ls-parameters.xhtml#protocol-ids
    identifier = 0
    local_node_descriptor = LocalNodeDescriptor([
        LocalNodeDescriptorSub(512, 65000),
        LocalNodeDescriptorSub(513, 0),
        LocalNodeDescriptorSub(516, "192.168.255.1"),
        LocalNodeDescriptorSub(517, 1)
    ])
    srv6_sid_information = [
        SRv6SIDDescriptor(sid='fd00::1')
    ]
    multi_topologies = [
        MultiTopology(
            mt_ids=[1]
        )
    ]
    service_chainings = [
        ServiceChaining(
            service_type=1,
            flags=0,
            traffic_type=1,
            reserved=0
        ),
    ]
    opaque_metadata = [
        OpaqueMetadata(
            opaque_type=1,
            flags=0,
            value='vvf-param-hoge'
        ),
    ]
    srv6_sid_nlri = SRv6SID(
        protocol_id,
        identifier,
        local_node_descriptor,
        srv6_sid_information,
        multi_topologies=multi_topologies,
        service_chainings=service_chainings,
        opaque_metadata=opaque_metadata
    )
    packed_nlri = srv6_sid_nlri._pack()
    print("Packed SRv6 SID NLRI:", packed_nlri.hex())
    return packed_nlri

def decode_srv6_sid_nlri(packed_nlri):
    try:
        unpacked_nlri = SRv6SID.unpack_nlri(packed_nlri, None)
        print("Decoded SRv6 SID NLRI:")
        unpacked_json = unpacked_nlri.json()
        cleaned_json = json.loads(unpacked_json)
        print(json.dumps(cleaned_json, indent=4, ensure_ascii=False))

        return unpacked_nlri
    except Exception as e:
        print(f"Error decoding SRv6 SID NLRI: {str(e)}")
        return None

if __name__ == "__main__":
    print("--- encode_srv6_sid_nlri ---")
    packed_nlri = encode_srv6_sid_nlri()
    print("--- decode_srv6_sid_nlri ---")
    decode_srv6_sid_nlri(packed_nlri)
