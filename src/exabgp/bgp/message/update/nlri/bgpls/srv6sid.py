"""srv6sid.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

import json
from struct import pack, unpack

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MTID
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.srv6sidinformation import Srv6SIDInformation
from exabgp.util import hexstring

# BGP-LS SRv6 SID TLV type codes (RFC 9514)
TLV_LOCAL_NODE_DESC = 256  # Local Node Descriptors TLV
TLV_MULTI_TOPO_ID = 263  # Multi-Topology Identifier TLV
TLV_SRV6_SID_INFO = 518  # SRv6 SID Information TLV

# Minimum TLV header size for validation
MIN_TLV_HEADER_SIZE = 2  # Type (2 bytes) + Length (2 bytes) = 4 bytes, checking for at least 2

#     RFC 9514: 6.  SRv6 SID NLRI
#
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+
#    |  Protocol-ID  |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |                        Identifier                             |
#    |                        (8 octets)                             |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Local Node Descriptors (variable)              //
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               SRv6 SID Descriptors (variable)                //
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                        Figure 5: SRv6 SID NLRI Format


@BGPLS.register
class SRv6SID(BGPLS):
    CODE = 6
    NAME = 'bgpls-srv6sid'
    SHORT_NAME = 'SRv6_SID'

    def __init__(self, protocol_id, domain, local_node_descriptors, srv6_sid_descriptors, action=None, addpath=None):
        BGPLS.__init__(self, action, addpath)
        self.proto_id = protocol_id
        self.domain = domain
        self.local_node_descriptors = local_node_descriptors
        self.srv6_sid_descriptors = srv6_sid_descriptors

    @classmethod
    def unpack_nlri(cls, data, length):
        proto_id = unpack('!B', data[0:1])[0]
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')
        domain = unpack('!Q', data[1:9])[0]

        tlvs = data[9:length]
        node_type, node_length = unpack('!HH', tlvs[0:4])
        if node_type != TLV_LOCAL_NODE_DESC:
            raise Exception(
                f'Unknown type: {node_type}. Only Local Node descriptors are allowed inNode type msg',
            )
        tlvs = tlvs[4:]
        local_node_descriptors = tlvs[:node_length]
        node_ids = []
        while local_node_descriptors:
            node_id, left = NodeDescriptor.unpack(local_node_descriptors, proto_id)
            node_ids.append(node_id)
            if left == local_node_descriptors:
                raise RuntimeError('sub-calls should consume data')
            local_node_descriptors = left

        tlvs = tlvs[node_length:]
        srv6_sid_descriptors = {}
        srv6_sid_descriptors['multi-topology-ids'] = []

        while tlvs:
            if len(tlvs) < MIN_TLV_HEADER_SIZE:
                raise RuntimeError('SRv6 SID Descriptors are too short')
            sid_type, sid_length = unpack('!HH', tlvs[:4])
            if sid_type == TLV_MULTI_TOPO_ID:
                srv6_sid_descriptors['multi-topology-ids'].append(MTID.unpack(tlvs[4 : sid_length + 4]).json())
            elif sid_type == TLV_SRV6_SID_INFO:
                srv6_sid_descriptors['srv6-sid'] = str(Srv6SIDInformation.unpack(tlvs[4 : sid_length + 4]))
            else:
                if f'generic-tlv-{sid_type}' not in srv6_sid_descriptors:
                    srv6_sid_descriptors[f'generic-tlv-{sid_type}'] = []
                srv6_sid_descriptors[f'generic-tlv-{sid_type}'].append(hexstring(tlvs[4 : sid_length + 4]))

            tlvs = tlvs[sid_length + 4 :]
        return cls(proto_id, domain, node_ids, srv6_sid_descriptors)

    def pack(self, packed=None):
        nlri = pack('!B', self.proto_id)
        nlri += pack('!Q', self.domain)
        nlri += self.local_node_descriptors
        nlri += self.srv6_sid_descriptors
        return nlri

    def __len__(self):
        return 1 + 8 + len(self.local_node_descriptors) + len(self.srv6_sid_descriptors)

    def __repr__(self):
        return f'{self.NAME}(protocol_id={self.proto_id}, domain={self.domain})'

    def json(self, compact=None):
        nodes = ', '.join(d.json() for d in self.local_node_descriptors)
        content = ', '.join(
            [
                f'"ls-nlri-type": "{self.NAME}"',
                f'"l3-routing-topology": {int(self.domain)}',
                f'"protocol-id": {int(self.proto_id)}',
                f'"node-descriptors": [ {nodes} ]',
                f'"srv6-sid-descriptors": {json.dumps(self.srv6_sid_descriptors)}',
            ],
        )

        return f'{{ {content} }}'
