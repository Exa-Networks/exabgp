"""node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    pass

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS, PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
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


@BGPLS.register_bgpls
class NODE(BGPLS):
    CODE: ClassVar[int] = 1
    NAME: ClassVar[str] = 'bgpls-node'
    SHORT_NAME: ClassVar[str] = 'Node'

    # Wire format offsets (after 4-byte header: type(2) + length(2))
    HEADER_SIZE: ClassVar[int] = 4
    PROTO_ID_OFFSET: ClassVar[int] = 4  # Byte 4: Protocol ID
    DOMAIN_OFFSET: ClassVar[int] = 5  # Bytes 5-12: Domain (8 bytes)
    NODE_DESC_OFFSET: ClassVar[int] = 13  # Bytes 13+: Node descriptor TLV

    def __init__(
        self,
        packed: bytes,
        nexthop: IP = IP.NoNextHop,
        action: Action = Action.UNSET,
        route_d: RouteDistinguisher | None = None,
        addpath: PathInfo | None = None,
    ) -> None:
        """Create NODE with complete wire format.

        Args:
            packed: Complete wire format including 4-byte header [type(2)][length(2)][payload]
        """
        BGPLS.__init__(self, action, addpath)
        self._packed = packed
        self.nexthop = nexthop
        self.route_d: RouteDistinguisher | None = route_d

    @classmethod
    def make_node(
        cls,
        domain: int,
        proto_id: int,
        node_ids: list[NodeDescriptor],
        nexthop: IP = IP.NoNextHop,
        action: Action = Action.UNSET,
        route_d: RouteDistinguisher | None = None,
        addpath: PathInfo | None = None,
    ) -> 'NODE':
        """Factory method to create NODE from semantic parameters."""
        node_tlvs = b''.join(node_id.pack_tlv() for node_id in node_ids)
        node_length = len(node_tlvs)
        # Build payload: proto_id(1) + domain(8) + node_descriptor_tlv(4+n)
        payload = pack('!BQ', proto_id, domain) + pack('!HH', NODE_DESCRIPTOR_TYPE, node_length) + node_tlvs
        # Include 4-byte header: type(2) + length(2) + payload
        packed = pack('!HH', cls.CODE, len(payload)) + payload
        return cls(packed, nexthop, action, route_d, addpath)

    @property
    def proto_id(self) -> int:
        # Offset by 4-byte header: proto_id at byte 4
        value: int = unpack('!B', self._packed[4:5])[0]
        return value

    @property
    def domain(self) -> int:
        # Offset by 4-byte header: domain at bytes 5-12
        value: int = unpack('!Q', self._packed[5:13])[0]
        return value

    @property
    def node_ids(self) -> list[NodeDescriptor]:
        # Offset by 4-byte header: node descriptor TLV at bytes 13+
        node_type, node_length = unpack('!HH', self._packed[13:17])
        if node_type != NODE_DESCRIPTOR_TYPE:
            return []
        values = self._packed[17 : 17 + node_length]
        node_ids: list[NodeDescriptor] = []
        while values:
            node_id, left = NodeDescriptor.unpack_node(values, self.proto_id)
            node_ids.append(node_id)
            if left == values:
                break
            values = left
        return node_ids

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
        """Unpack NODE from complete wire format.

        Args:
            data: Complete wire format including 4-byte header [type(2)][length(2)][payload]
            rd: Route Distinguisher (for VPN SAFI)
        """
        # Data includes 4-byte header, payload starts at offset 4
        proto_id = unpack('!B', data[4:5])[0]
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')

        # Validate node descriptor TLV type (offset by 4-byte header)
        node_type, node_length = unpack('!HH', data[13:17])
        if node_type != NODE_DESCRIPTOR_TYPE:
            raise Exception(
                f'Unknown type: {node_type}. Only Local Node descriptors are allowed inNode type msg',
            )

        # Validate node descriptors can be parsed (ensures data integrity)
        values = data[17 : 17 + node_length]
        while values:
            _node_id, left = NodeDescriptor.unpack_node(values, proto_id)
            if left == values:
                raise RuntimeError('sub-calls should consume data')
            values = left

        # Store complete wire format including header
        return cls(data, route_d=rd)

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
        return hash((self.proto_id, self.domain, tuple(self.node_ids), self.route_d))

    # pack_nlri inherited from BGPLS base class - returns self._packed directly
