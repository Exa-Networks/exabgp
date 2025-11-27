"""link.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, ClassVar, List

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.linkid import LinkIdentifier
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ifaceaddr import IfaceAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.neighaddr import NeighAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MTID

from exabgp.logger import log, lazymsg

# BGP-LS Link TLV type codes (RFC 7752)
TLV_LOCAL_NODE_DESC: int = 256  # Local Node Descriptors TLV
TLV_REMOTE_NODE_DESC: int = 257  # Remote Node Descriptors TLV
TLV_LINK_ID: int = 258  # Link Local/Remote Identifiers TLV
TLV_IPV4_IFACE_ADDR: int = 259  # IPv4 Interface Address TLV
TLV_IPV4_NEIGH_ADDR: int = 260  # IPv4 Neighbor Address TLV
TLV_IPV6_IFACE_ADDR: int = 261  # IPv6 Interface Address TLV
TLV_IPV6_NEIGH_ADDR: int = 262  # IPv6 Neighbor Address TLV
TLV_MULTI_TOPO_ID: int = 263  # Multi-Topology Identifier TLV

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+
#     |  Protocol-ID  |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                           Identifier                          |
#     |                            (64 bits)                          |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //               Local Node Descriptors (variable)             //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //               Remote Node Descriptors (variable)            //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                  Link Descriptors (variable)                //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#                     Figure 8: The Link NLRI format
#
#   +-----------+---------------------+--------------+------------------+
#   |  TLV Code | Description         |  IS-IS TLV   | Reference        |
#   |   Point   |                     |   /Sub-TLV   | (RFC/Section)    |
#   +-----------+---------------------+--------------+------------------+
#   |    258    | Link Local/Remote   |     22/4     | [RFC5307]/1.1    |
#   |           | Identifiers         |              |                  |
#   |    259    | IPv4 interface      |     22/6     | [RFC5305]/3.2    |
#   |           | address             |              |                  |
#   |    260    | IPv4 neighbor       |     22/8     | [RFC5305]/3.3    |
#   |           | address             |              |                  |
#   |    261    | IPv6 interface      |    22/12     | [RFC6119]/4.2    |
#   |           | address             |              |                  |
#   |    262    | IPv6 neighbor       |    22/13     | [RFC6119]/4.3    |
#   |           | address             |              |                  |
#   |    263    | Multi-Topology      |     ---      | Section 3.2.1.5  |
#   |           | Identifier          |              |                  |
#   +-----------+---------------------+--------------+------------------+


@BGPLS.register
class LINK(BGPLS):
    CODE: ClassVar[int] = 2
    NAME: ClassVar[str] = 'bgpls-link'
    SHORT_NAME: ClassVar[str] = 'Link'

    def __init__(
        self,
        domain: int,
        proto_id: int,
        local_node: List[NodeDescriptor] | None,
        remote_node: List[NodeDescriptor] | None,
        neigh_addrs: List[NeighAddr] | None = None,
        iface_addrs: List[IfaceAddr] | None = None,
        topology_ids: List[MTID] | None = None,
        link_ids: List[LinkIdentifier] | None = None,
        nexthop: IP = IP.NoNextHop,
        action: Action = Action.UNSET,
        route_d: RouteDistinguisher | None = None,
        addpath: PathInfo | None = None,
        packed: bytes | None = None,
    ) -> None:
        BGPLS.__init__(self, action, addpath)
        self.domain: int = domain
        self.proto_id: int = proto_id
        self.local_node: List[NodeDescriptor] = local_node if local_node else []
        self.remote_node: List[NodeDescriptor] = remote_node if remote_node else []
        self.neigh_addrs: List[NeighAddr] = neigh_addrs if neigh_addrs else []
        self.iface_addrs: List[IfaceAddr] = iface_addrs if iface_addrs else []
        self.link_ids: List[LinkIdentifier] = link_ids if link_ids else []
        self.topology_ids: List[MTID] = topology_ids if topology_ids else []
        self.nexthop = nexthop
        self.route_d: RouteDistinguisher | None = route_d
        self._packed: bytes | None = packed  # type: ignore[assignment]

    @classmethod
    def unpack_bgpls_nlri(cls, data: bytes, rd: RouteDistinguisher | None) -> LINK:
        proto_id = unpack('!B', data[0:1])[0]
        # FIXME: all these list should probably be defined in the objects
        iface_addrs: List[IfaceAddr] = []
        neigh_addrs: List[NeighAddr] = []
        link_identifiers: List[LinkIdentifier] = []
        topology_ids: List[MTID] = []
        remote_node: List[NodeDescriptor] = []
        local_node: List[NodeDescriptor] = []
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')
        domain = unpack('!Q', data[1:9])[0]
        tlvs = data[9:]

        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            value = tlvs[4 : 4 + tlv_length]
            tlvs = tlvs[4 + tlv_length :]

            if tlv_type == TLV_LOCAL_NODE_DESC:
                local_node = []
                while value:
                    # Unpack Local Node Descriptor Sub-TLVs
                    # We pass proto_id as TLV interpretation
                    # follows IGP type
                    node, left = NodeDescriptor.unpack_node(value, proto_id)
                    local_node.append(node)
                    if left == value:
                        raise RuntimeError('sub-calls should consume data')
                    value = left
                continue

            if tlv_type == TLV_REMOTE_NODE_DESC:
                # Remote Node Descriptor
                remote_node = []
                while value:
                    node, left = NodeDescriptor.unpack_node(value, proto_id)
                    remote_node.append(node)
                    if left == value:
                        raise RuntimeError('sub-calls should consume data')
                    value = left
                continue

            if tlv_type == TLV_LINK_ID:
                # Link Local/Remote identifiers
                link_identifiers = LinkIdentifier.unpack_linkid(value)
                continue

            if tlv_type in [TLV_IPV4_IFACE_ADDR, TLV_IPV6_IFACE_ADDR]:
                # IPv{4,6} Interface Address
                iface_addrs.append(IfaceAddr.unpack_ifaceaddr(value))
                continue

            if tlv_type in [TLV_IPV4_NEIGH_ADDR, TLV_IPV6_NEIGH_ADDR]:
                # IPv{4,6} Neighbor Address
                neigh_addrs.append(NeighAddr.unpack_neighaddr(value))
                continue

            if tlv_type == TLV_MULTI_TOPO_ID:
                topology_ids.append(MTID.unpack_mtid(value))
                continue

            log.critical(lazymsg('unknown link TLV {tlv_type}', tlv_type=tlv_type))

        return cls(
            domain=domain,
            proto_id=proto_id,
            local_node=local_node,
            remote_node=remote_node,
            neigh_addrs=neigh_addrs,
            iface_addrs=iface_addrs,
            link_ids=link_identifiers,
            topology_ids=topology_ids,
            route_d=rd,
            packed=data,
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, LINK)
            and self.CODE == other.CODE
            and self.domain == other.domain
            and self.proto_id == other.proto_id
            and self.topology_ids == other.topology_ids
            and self.route_d == other.route_d
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return self.json()

    def __hash__(self) -> int:
        return hash((self.CODE, self.domain, self.proto_id, tuple(self.topology_ids), self.route_d))

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        if self._packed:
            return self._packed
        raise RuntimeError('Not implemented')

    def json(self, compact: bool = False) -> str:
        content = f'"ls-nlri-type": "{self.NAME}", '
        content += f'"l3-routing-topology": {int(self.domain)}, '
        content += f'"protocol-id": {int(self.proto_id)}, '

        local = ', '.join(_.json() for _ in self.local_node)
        content += f'"local-node-descriptors": [ {local} ], '

        remote = ', '.join(_.json() for _ in self.remote_node)
        content += f'"remote-node-descriptors": [ {remote} ], '

        interface_addrs = ', '.join(_.json() for _ in self.iface_addrs)
        content += f'"interface-addresses": [ {interface_addrs} ], '

        neighbor_addrs = ', '.join(_.json() for _ in self.neigh_addrs)
        content += f'"neighbor-addresses": [ {neighbor_addrs} ], '

        topology_ids = ', '.join(_.json() for _ in self.topology_ids)
        content += f'"multi-topology-ids": [ {topology_ids} ], '

        links = ', '.join(_.json() for _ in self.link_ids)
        content += f'"link-identifiers": [ {links} ]'
        # # content is ending without a , here in purpose

        if self.route_d:
            content += f', {{ {self.route_d.json()} }}'

        return f'{{ {content} }}'
