#!/usr/bin/env python3

import sys
import os

# ExaBGPのソースディレクトリをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from exabgp.bgp.message.update.nlri.bgpls.srv6sid import SRv6SID
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure
from exabgp.bgp.message.update.nlri.bgpls.srv6sid import LocalNodeDescriptor, SRv6SIDDescriptor
from exabgp.protocol.ip import IPv6
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MultiTopology
from exabgp.bgp.message.update.nlri.bgpls.tlvs.servicechaining import ServiceChaining
from exabgp.bgp.message.update.nlri.bgpls.tlvs.opaquemetadata import OpaqueMetadata

# https://www.rfc-editor.org/rfc/rfc9514.html#name-srv6-sid-nlri
def encode_srv6_sid_nlri():
    protocol_id = 5 # https://www.iana.org/assignments/bgp-ls-parameters/bgp-ls-parameters.xhtml#protocol-ids
    identifier = 0x0000000000000001
    local_node_descriptor = LocalNodeDescriptor(
        as_number=65000,
        bgp_ls_identifier=1,
        ospf_area_id=0,
        router_id='127.0.0.1'
    )
    srv6_sid_information = [
        SRv6SIDDescriptor(sid='2001:db8:85a3::8a2e:370:7335'),
        SRv6SIDDescriptor(sid='2001:db8:85a3::8a2e:370:7336')
    ]
    multi_topologies = [
        MultiTopology(
            mt_ids=[1, 2, 3]
        ),
        MultiTopology(
            mt_ids=[4, 5]
        )
    ]
    service_chainings = [
        ServiceChaining(
            service_type=1,
            flags=0,
            traffic_type=0,
            reserved=0
        ),
        ServiceChaining(
            service_type=2,
            flags=0,
            traffic_type=0,
            reserved=0
        )
    ]
    opaque_metadata = [
        OpaqueMetadata(
            length=8,
            opaque_type=1,
            flags=0,
            value='first'
        ),
        OpaqueMetadata(
            length=9,
            opaque_type=2,
            flags=0,
            value='second'
        )
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

        print(f"Protocol ID: {unpacked_nlri.protocol_id}")
        print(f"Identifier: {unpacked_nlri.identifier}")
        print("Local Node Descriptor:")
        print(f"  AS Number: {unpacked_nlri.local_node_descriptor.as_number}")
        print(f"  BGP-LS Identifier: {unpacked_nlri.local_node_descriptor.bgp_ls_identifier}")
        print(f"  OSPF Area ID: {unpacked_nlri.local_node_descriptor.ospf_area_id}")
        print(f"  Router ID: {unpacked_nlri.local_node_descriptor.router_id}")
        print("SRv6 SID Information:")
        for srv6_sid_information in unpacked_nlri.srv6_sid_information:
            print(f"  SID: {srv6_sid_information.sid}")
        print("Multi Topologies:")
        for multi_topology in unpacked_nlri.multi_topologies:
            print(f"  Type: {multi_topology.type}")
            print(f"  Length: {multi_topology.length}")
            print(f"  Multi Topology IDs: {multi_topology.mt_ids}")
        print("Service Chainings:")
        for service_chaining in unpacked_nlri.service_chainings:
            print(f"  Type: {service_chaining.type}")
            print(f"  Length: {service_chaining.length}")
            print(f"  Service Type: {service_chaining.service_type}")
            print(f"  Flags: {service_chaining.flags}")
            print(f"  Traffic Type: {service_chaining.traffic_type}")
            print(f"  Reserved: {service_chaining.reserved}")
        print("Opaque Metadata:")
        for opaque_metadata in unpacked_nlri.opaque_metadata:
            print(f"  Type: {opaque_metadata.type}")
            print(f"  Length: {opaque_metadata.length}")
            print(f"  Opaque Type: {opaque_metadata.opaque_type}")
            print(f"  Flags: {opaque_metadata.flags}")
            print(f"  Value: {opaque_metadata.value}")

        return unpacked_nlri
    except Exception as e:
        print(f"Error decoding SRv6 SID NLRI: {str(e)}")
        return None

if __name__ == "__main__":
    print("--- encode_srv6_sid_nlri ---")
    packed_nlri = encode_srv6_sid_nlri()
    print("--- decode_srv6_sid_nlri ---")
    decode_srv6_sid_nlri(packed_nlri)
