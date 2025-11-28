"""node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, ClassVar, List

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+
#     |  Protocol-ID  |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                           Identifier                          |
#     |                            (64 bits)                          |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                Local Node Descriptors (variable)            //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# ===================================================================== NODENLRI
#             +------------+----------------------------------+
#             | Identifier | Routing Universe                 |
#             +------------+----------------------------------+
#             |     0      | Default Layer 3 Routing topology |

# BGP-LS Node Descriptor TLV type
NODE_DESCRIPTOR_TYPE: int = 256  # Local Node Descriptors TLV type
#             +------------+----------------------------------+
#   The Protocol-ID field can contain one of the following values:
# ===================================================================== DOMAIN


@BGPLS.register
class NODE(BGPLS):
    CODE: ClassVar[int] = 1
    NAME: ClassVar[str] = 'bgpls-node'
    SHORT_NAME: ClassVar[str] = 'Node'

    def __init__(
        self,
        domain: int,
        proto_id: int,
        node_ids: List[NodeDescriptor],
        packed: bytes | None = None,
        nexthop: IP = IP.NoNextHop,
        action: Action = Action.UNSET,
        route_d: RouteDistinguisher | None = None,
        addpath: PathInfo | None = None,
    ) -> None:
        BGPLS.__init__(self, action, addpath)
        self.domain: int = domain
        self.proto_id: int = proto_id
        self.node_ids: List[NodeDescriptor] = node_ids
        self.nexthop = nexthop
        self._pack: bytes | None = packed
        self.route_d: RouteDistinguisher | None = route_d

    def json(self, compact: bool = False) -> str:
        nodes = ', '.join(d.json() for d in self.node_ids)
        content = ', '.join(
            [
                f'"ls-nlri-type": "{self.NAME}"',
                f'"l3-routing-topology": {int(self.domain)}',
                f'"protocol-id": {int(self.proto_id)}',
                f'"node-descriptors": [ {nodes} ]',
                f'"nexthop": "{self.nexthop}"',
            ],
        )
        if self.route_d:
            content += f', {self.route_d.json()}'
        return f'{{ {content} }}'

    @classmethod
    def unpack_bgpls_nlri(cls, data: bytes, rd: RouteDistinguisher | None) -> NODE:
        proto_id = unpack('!B', data[0:1])[0]
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')
        domain = unpack('!Q', data[1:9])[0]

        # unpack list of node descriptors
        node_type, node_length = unpack('!HH', data[9:13])
        if node_type != NODE_DESCRIPTOR_TYPE:
            raise Exception(
                f'Unknown type: {node_type}. Only Local Node descriptors are allowed inNode type msg',
            )
        values = data[13 : 13 + node_length]

        node_ids: List[NodeDescriptor] = []
        while values:
            # Unpack Node Descriptor Sub-TLVs
            node_id, left = NodeDescriptor.unpack_node(values, proto_id)
            node_ids.append(node_id)
            if left == values:
                raise RuntimeError('sub-calls should consume data')
            values = left

        return cls(domain=domain, proto_id=proto_id, node_ids=node_ids, route_d=rd, packed=data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NODE):
            return False
        return (
            self.CODE == other.CODE
            and self.domain == other.domain
            and self.proto_id == other.proto_id
            and self.route_d == other.route_d
        )

    def __str__(self) -> str:
        return self.json()

    def __hash__(self) -> int:
        return hash((self.proto_id, tuple(self.node_ids)))

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        if self._pack:
            return self._pack

        # Calculate packed bytes dynamically
        # Pack node descriptor TLVs
        node_tlvs = b''.join(node_id.pack_tlv() for node_id in self.node_ids)
        node_length = len(node_tlvs)

        # Structure: proto_id (1) + domain (8) + node_type (2) + node_length (2) + node_tlvs
        self._pack = (
            pack('!BQ', self.proto_id, self.domain) + pack('!HH', NODE_DESCRIPTOR_TYPE, node_length) + node_tlvs
        )
        return self._pack
