"""prefixv4.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, ClassVar, List, Optional, Union

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ospfroute import OspfRoute
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP, _NoNextHop
from exabgp.logger import log

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


@BGPLS.register
class PREFIXv4(BGPLS):
    CODE: ClassVar[int] = 3
    NAME: ClassVar[str] = 'bgpls-prefix-v4'
    SHORT_NAME: ClassVar[str] = 'PREFIX_V4'

    def __init__(
        self,
        domain: int,
        proto_id: int,
        local_node: List[NodeDescriptor],
        packed: Optional[bytes] = None,
        ospf_type: Optional[OspfRoute] = None,
        prefix: Optional[IpReach] = None,
        nexthop: Optional[Union[IP, _NoNextHop]] = None,
        route_d: Optional[RouteDistinguisher] = None,
        action: Action = Action.UNSET,
        addpath: Optional[PathInfo] = None,
    ) -> None:
        BGPLS.__init__(self, action, addpath)
        self.domain: int = domain
        self.ospf_type: Optional[OspfRoute] = ospf_type
        self.proto_id: int = proto_id
        self.local_node: List[NodeDescriptor] = local_node
        self.prefix: Optional[IpReach] = prefix
        self.nexthop: Optional[Union[IP, _NoNextHop]] = nexthop
        self._pack: Optional[bytes] = packed
        self.route_d: Optional[RouteDistinguisher] = route_d

    @classmethod
    def unpack_bgpls_nlri(cls, data: bytes, rd: Optional[RouteDistinguisher]) -> PREFIXv4:
        ospf_type: Optional[OspfRoute] = None
        local_node: List[NodeDescriptor] = []
        prefix: Optional[IpReach] = None
        proto_id = unpack('!B', data[0:1])[0]
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')
        domain = unpack('!Q', data[1:9])[0]
        tlvs = data[9:]

        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            value = tlvs[4 : 4 + tlv_length]
            tlvs = tlvs[4 + tlv_length :]

            if tlv_type == TLV_LOCAL_NODE_DESC:
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

            if tlv_type == TLV_OSPF_ROUTE_TYPE:
                ospf_type = OspfRoute.unpack_ospfroute(value)
                continue

            if tlv_type == TLV_IP_REACHABILITY:
                prefix = IpReach.unpack_ipreachability(value, 3)
                continue

            log.critical(lambda tlv_type=tlv_type: f'unknown prefix v4 TLV {tlv_type}')

        return cls(
            domain=domain,
            proto_id=proto_id,
            packed=data,
            local_node=local_node,
            ospf_type=ospf_type,
            prefix=prefix,
            route_d=rd,
        )

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
        nodes = ', '.join(d.json() for d in self.local_node)
        content = ', '.join(
            [
                f'"ls-nlri-type": "{self.NAME}"',
                f'"l3-routing-topology": {int(self.domain)}',
                f'"protocol-id": {int(self.proto_id)}',
                f'"node-descriptors": [ {nodes} ]',
                self.prefix.json(),  # type: ignore[union-attr]
                f'"nexthop": "{self.nexthop}"',
            ],
        )
        if self.ospf_type:
            content += f', {self.ospf_type.json()}'

        if self.route_d:
            content += f', {self.route_d.json()}'

        return f'{{ {content} }}'

    def pack(self, negotiated: Negotiated = None) -> Optional[bytes]:  # type: ignore[assignment]
        return self._pack
