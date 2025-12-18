"""link.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    pass

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS, PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ifaceaddr import IfaceAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.linkid import LinkIdentifier
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MTID
from exabgp.bgp.message.update.nlri.bgpls.tlvs.neighaddr import NeighAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.logger import lazymsg, log
from exabgp.util.types import Buffer

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


@BGPLS.register_bgpls
class LINK(BGPLS):
    CODE: ClassVar[int] = 2
    NAME: ClassVar[str] = 'bgpls-link'
    SHORT_NAME: ClassVar[str] = 'Link'

    # Wire format offsets (after 4-byte header: type(2) + length(2))
    HEADER_SIZE: ClassVar[int] = 4
    PROTO_ID_OFFSET: ClassVar[int] = 4  # Byte 4: Protocol ID
    DOMAIN_OFFSET: ClassVar[int] = 5  # Bytes 5-12: Domain (8 bytes)
    TLV_OFFSET: ClassVar[int] = 13  # Bytes 13+: TLVs

    def __init__(
        self,
        packed: Buffer,
        route_d: RouteDistinguisher = RouteDistinguisher.NORD,
        addpath: PathInfo | None = None,
    ) -> None:
        """Create LINK with complete wire format.

        Args:
            packed: Complete wire format including 4-byte header [type(2)][length(2)][payload]
            route_d: Route Distinguisher (for VPN SAFI), NORD if none
            addpath: AddPath path identifier
        """
        BGPLS.__init__(self, addpath)
        self._packed = packed
        self.route_d: RouteDistinguisher = route_d

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

    def _parse_tlvs(
        self,
    ) -> tuple[
        list[NodeDescriptor],
        list[NodeDescriptor],
        list[IfaceAddr],
        list[NeighAddr],
        list[LinkIdentifier],
        list[MTID],
    ]:
        """Parse TLVs from packed data."""
        local_node: list[NodeDescriptor] = []
        remote_node: list[NodeDescriptor] = []
        iface_addrs: list[IfaceAddr] = []
        neigh_addrs: list[NeighAddr] = []
        link_identifiers: list[LinkIdentifier] = []
        topology_ids: list[MTID] = []

        # Offset by 4-byte header: TLVs start at byte 13 (4 + 1 + 8)
        tlvs = self._packed[13:]
        proto_id = self.proto_id

        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            value = tlvs[4 : 4 + tlv_length]
            tlvs = tlvs[4 + tlv_length :]

            if tlv_type == TLV_LOCAL_NODE_DESC:
                while value:
                    node, left = NodeDescriptor.unpack_node(value, proto_id)
                    local_node.append(node)
                    if left == value:
                        break
                    value = left
            elif tlv_type == TLV_REMOTE_NODE_DESC:
                while value:
                    node, left = NodeDescriptor.unpack_node(value, proto_id)
                    remote_node.append(node)
                    if left == value:
                        break
                    value = left
            elif tlv_type == TLV_LINK_ID:
                link_identifiers = [LinkIdentifier.unpack_linkid(value)]
            elif tlv_type in [TLV_IPV4_IFACE_ADDR, TLV_IPV6_IFACE_ADDR]:
                iface_addrs.append(IfaceAddr.unpack_ifaceaddr(value))
            elif tlv_type in [TLV_IPV4_NEIGH_ADDR, TLV_IPV6_NEIGH_ADDR]:
                neigh_addrs.append(NeighAddr.unpack_neighaddr(value))
            elif tlv_type == TLV_MULTI_TOPO_ID:
                topology_ids.append(MTID.unpack_mtid(value))

        return local_node, remote_node, iface_addrs, neigh_addrs, link_identifiers, topology_ids

    @property
    def local_node(self) -> list[NodeDescriptor]:
        return self._parse_tlvs()[0]

    @property
    def remote_node(self) -> list[NodeDescriptor]:
        return self._parse_tlvs()[1]

    @property
    def iface_addrs(self) -> list[IfaceAddr]:
        return self._parse_tlvs()[2]

    @property
    def neigh_addrs(self) -> list[NeighAddr]:
        return self._parse_tlvs()[3]

    @property
    def link_ids(self) -> list[LinkIdentifier]:
        return self._parse_tlvs()[4]

    @property
    def topology_ids(self) -> list[MTID]:
        return self._parse_tlvs()[5]

    @classmethod
    def unpack_bgpls_nlri(cls, data: Buffer, rd: RouteDistinguisher) -> LINK:
        """Unpack LINK from complete wire format.

        Args:
            data: Complete wire format including 4-byte header [type(2)][length(2)][payload]
            rd: Route Distinguisher (for VPN SAFI), NORD if none
        """
        # Data includes 4-byte header, payload starts at offset 4
        proto_id = unpack('!B', data[4:5])[0]
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')

        # Validate TLVs can be parsed (logging unknown TLVs)
        # Offset by 4-byte header: TLVs start at byte 13 (4 + 1 + 8)
        tlvs = data[13:]
        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            value = tlvs[4 : 4 + tlv_length]
            tlvs = tlvs[4 + tlv_length :]

            if tlv_type == TLV_LOCAL_NODE_DESC:
                while value:
                    _node, left = NodeDescriptor.unpack_node(value, proto_id)
                    if left == value:
                        raise RuntimeError('sub-calls should consume data')
                    value = left
            elif tlv_type == TLV_REMOTE_NODE_DESC:
                while value:
                    _node, left = NodeDescriptor.unpack_node(value, proto_id)
                    if left == value:
                        raise RuntimeError('sub-calls should consume data')
                    value = left
            elif tlv_type not in [
                TLV_LINK_ID,
                TLV_IPV4_IFACE_ADDR,
                TLV_IPV6_IFACE_ADDR,
                TLV_IPV4_NEIGH_ADDR,
                TLV_IPV6_NEIGH_ADDR,
                TLV_MULTI_TOPO_ID,
            ]:
                log.critical(lazymsg('unknown link TLV {tlv_type}', tlv_type=tlv_type))

        # Store complete wire format including header
        return cls(data, route_d=rd)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LINK):
            return False
        # Direct _packed comparison - CODE, proto_id, domain, topology_ids all encoded in wire format
        return self._packed == other._packed and self.route_d == other.route_d

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return self.json()

    def __hash__(self) -> int:
        # Direct _packed hash - all wire fields encoded in bytes
        return hash((self._packed, self.route_d))

    # pack_nlri inherited from BGPLS base class - returns self._packed directly

    def json(self, announced: bool = True, compact: bool = False) -> str:
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
