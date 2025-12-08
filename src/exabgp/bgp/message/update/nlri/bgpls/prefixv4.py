"""prefixv4.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    pass

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS, PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ospfroute import OspfRoute
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.logger import lazymsg, log
from exabgp.protocol.ip import IP

# BGP-LS Prefix TLV type codes (RFC 7752)
TLV_LOCAL_NODE_DESC: int = 256  # Local Node Descriptors TLV
TLV_OSPF_ROUTE_TYPE: int = 264  # OSPF Route Type TLV
TLV_IP_REACHABILITY: int = 265  # IP Reachability Information TLV

#   The IPv4 and IPv6 Prefix NLRIs (NLRI Type = 3 and Type = 4) use the
#   same format, as shown in the following figure.
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+
#     |  Protocol-ID  |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                           Identifier                          |
#     |                            (64 bits)                          |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //              Local Node Descriptors (variable)              //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                Prefix Descriptors (variable)                //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


@BGPLS.register_bgpls
class PREFIXv4(BGPLS):
    CODE: ClassVar[int] = 3
    NAME: ClassVar[str] = 'bgpls-prefix-v4'
    SHORT_NAME: ClassVar[str] = 'PREFIX_V4'

    # Wire format offsets (after 4-byte header: type(2) + length(2))
    HEADER_SIZE: ClassVar[int] = 4
    PROTO_ID_OFFSET: ClassVar[int] = 4  # Byte 4: Protocol ID
    DOMAIN_OFFSET: ClassVar[int] = 5  # Bytes 5-12: Domain (8 bytes)
    TLV_OFFSET: ClassVar[int] = 13  # Bytes 13+: TLVs

    def __init__(
        self,
        packed: bytes,
        nexthop: IP = IP.NoNextHop,
        route_d: RouteDistinguisher | None = None,
        action: Action = Action.UNSET,
        addpath: PathInfo | None = None,
    ) -> None:
        """Create PREFIXv4 with complete wire format.

        Args:
            packed: Complete wire format including 4-byte header [type(2)][length(2)][payload]
        """
        BGPLS.__init__(self, action, addpath)
        self._packed = packed
        self.nexthop = nexthop
        self.route_d: RouteDistinguisher | None = route_d

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

    def _parse_tlvs(self) -> tuple[list[NodeDescriptor], OspfRoute | None, IpReach | None]:
        """Parse TLVs from packed data."""
        local_node: list[NodeDescriptor] = []
        ospf_type: OspfRoute | None = None
        prefix: IpReach | None = None

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
            elif tlv_type == TLV_OSPF_ROUTE_TYPE:
                ospf_type = OspfRoute.unpack_ospfroute(value)
            elif tlv_type == TLV_IP_REACHABILITY:
                prefix = IpReach.unpack_ipreachability(value, 3)

        return local_node, ospf_type, prefix

    @property
    def local_node(self) -> list[NodeDescriptor]:
        return self._parse_tlvs()[0]

    @property
    def ospf_type(self) -> OspfRoute | None:
        return self._parse_tlvs()[1]

    @property
    def prefix(self) -> IpReach | None:
        return self._parse_tlvs()[2]

    @classmethod
    def unpack_bgpls_nlri(cls, data: bytes, rd: RouteDistinguisher | None) -> PREFIXv4:
        """Unpack PREFIXv4 from complete wire format.

        Args:
            data: Complete wire format including 4-byte header [type(2)][length(2)][payload]
            rd: Route Distinguisher (for VPN SAFI)
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
            elif tlv_type not in [TLV_OSPF_ROUTE_TYPE, TLV_IP_REACHABILITY]:
                log.critical(lazymsg('unknown prefix v4 TLV {tlv_type}', tlv_type=tlv_type))

        # Store complete wire format including header
        return cls(data, route_d=rd)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, PREFIXv4)
            and self.CODE == other.CODE
            and self.domain == other.domain
            and self.proto_id == other.proto_id
            and self.route_d == other.route_d
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return self.json()

    def __hash__(self) -> int:
        return hash((self.CODE, self.domain, self.proto_id, self.route_d))

    def json(self, compact: bool = False) -> str:
        assert self.prefix is not None  # Set during unpack_bgpls_nlri
        nodes = ', '.join(d.json() for d in self.local_node)
        content = ', '.join(
            [
                f'"ls-nlri-type": "{self.NAME}"',
                f'"l3-routing-topology": {int(self.domain)}',
                f'"protocol-id": {int(self.proto_id)}',
                f'"node-descriptors": [ {nodes} ]',
                self.prefix.json(),
                f'"nexthop": "{self.nexthop}"',
            ],
        )
        if self.ospf_type:
            content += f', {self.ospf_type.json()}'

        if self.route_d:
            content += f', {self.route_d.json()}'

        return f'{{ {content} }}'

    # pack_nlri inherited from BGPLS base class - returns self._packed directly
