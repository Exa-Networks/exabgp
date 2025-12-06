"""srv6sid.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MTID
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.srv6sidinformation import Srv6SIDInformation
from exabgp.util import hexstring

# BGP-LS SRv6 SID TLV type codes (RFC 9514)
TLV_LOCAL_NODE_DESC: int = 256  # Local Node Descriptors TLV
TLV_MULTI_TOPO_ID: int = 263  # Multi-Topology Identifier TLV
TLV_SRV6_SID_INFO: int = 518  # SRv6 SID Information TLV

# Minimum TLV header size for validation
MIN_TLV_HEADER_SIZE: int = 2  # Type (2 bytes) + Length (2 bytes) = 4 bytes, checking for at least 2

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
    CODE: ClassVar[int] = 6
    NAME: ClassVar[str] = 'bgpls-srv6sid'
    SHORT_NAME: ClassVar[str] = 'SRv6_SID'

    def __init__(
        self,
        packed: bytes,
        action: Action = Action.UNSET,
        addpath: PathInfo | None = None,
    ) -> None:
        BGPLS.__init__(self, action, addpath)
        self._packed = packed

    @property
    def proto_id(self) -> int:
        value: int = unpack('!B', self._packed[0:1])[0]
        return value

    @property
    def domain(self) -> int:
        value: int = unpack('!Q', self._packed[1:9])[0]
        return value

    def _parse_tlvs(self) -> tuple[list[NodeDescriptor], dict[str, Any]]:
        """Parse TLVs from packed data."""
        proto_id = self.proto_id
        tlvs = self._packed[9:]

        node_type, node_length = unpack('!HH', tlvs[0:4])
        if node_type != TLV_LOCAL_NODE_DESC:
            return [], {}

        tlvs = tlvs[4:]
        local_node_data = tlvs[:node_length]
        node_ids: list[NodeDescriptor] = []
        while local_node_data:
            node_id, left = NodeDescriptor.unpack_node(local_node_data, proto_id)
            node_ids.append(node_id)
            if left == local_node_data:
                break
            local_node_data = left

        tlvs = tlvs[node_length:]
        srv6_sid_descriptors: dict[str, Any] = {}
        srv6_sid_descriptors['multi-topology-ids'] = []

        while tlvs:
            if len(tlvs) < MIN_TLV_HEADER_SIZE:
                break
            sid_type, sid_length = unpack('!HH', tlvs[:4])
            if sid_type == TLV_MULTI_TOPO_ID:
                srv6_sid_descriptors['multi-topology-ids'].append(MTID.unpack_mtid(tlvs[4 : sid_length + 4]).json())
            elif sid_type == TLV_SRV6_SID_INFO:
                srv6_sid_descriptors['srv6-sid'] = str(Srv6SIDInformation.unpack_srv6sid(tlvs[4 : sid_length + 4]))
            else:
                if f'generic-tlv-{sid_type}' not in srv6_sid_descriptors:
                    srv6_sid_descriptors[f'generic-tlv-{sid_type}'] = []
                srv6_sid_descriptors[f'generic-tlv-{sid_type}'].append(hexstring(tlvs[4 : sid_length + 4]))

            tlvs = tlvs[sid_length + 4 :]

        return node_ids, srv6_sid_descriptors

    @property
    def local_node_descriptors(self) -> list[NodeDescriptor]:
        return self._parse_tlvs()[0]

    @property
    def srv6_sid_descriptors(self) -> dict[str, Any]:
        return self._parse_tlvs()[1]

    @classmethod
    def unpack_bgpls_nlri(cls, data: bytes, length: int) -> SRv6SID:
        proto_id = unpack('!B', data[0:1])[0]
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')

        # Validate node descriptor TLV type
        tlvs = data[9:length]
        node_type, node_length = unpack('!HH', tlvs[0:4])
        if node_type != TLV_LOCAL_NODE_DESC:
            raise Exception(
                f'Unknown type: {node_type}. Only Local Node descriptors are allowed inNode type msg',
            )

        # Validate node descriptors can be parsed
        tlvs = tlvs[4:]
        local_node_data = tlvs[:node_length]
        while local_node_data:
            _node_id, left = NodeDescriptor.unpack_node(local_node_data, proto_id)
            if left == local_node_data:
                raise RuntimeError('sub-calls should consume data')
            local_node_data = left

        # Validate SRv6 SID descriptors
        tlvs = tlvs[node_length:]
        while tlvs:
            if len(tlvs) < MIN_TLV_HEADER_SIZE:
                raise RuntimeError('SRv6 SID Descriptors are too short')
            _sid_type, sid_length = unpack('!HH', tlvs[:4])
            tlvs = tlvs[sid_length + 4 :]

        return cls(data[:length])

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return self._packed

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        # RFC 7911 ADD-PATH is possible for BGP-LS but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.bgpls, SAFI.bgp_ls)
        return self._packed

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return f'{self.NAME}(protocol_id={self.proto_id}, domain={self.domain})'

    def json(self, compact: bool = False) -> str:
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
