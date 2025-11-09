"""
link.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.linkid import LinkIdentifier
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ifaceaddr import IfaceAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.neighaddr import NeighAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MTID

from exabgp.logger import log

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
    CODE = 2
    NAME = 'bgpls-link'
    SHORT_NAME = 'Link'

    def __init__(
        self,
        domain,
        proto_id,
        local_node,
        remote_node,
        neigh_addrs=None,
        iface_addrs=None,
        topology_ids=None,
        link_ids=None,
        nexthop=None,
        action=None,
        route_d=None,
        addpath=None,
        packed=None,
    ):
        BGPLS.__init__(self, action, addpath)
        self.domain = domain
        self.proto_id = proto_id
        self.local_node = local_node if local_node else []
        self.remote_node = remote_node if remote_node else []
        self.neigh_addrs = neigh_addrs if neigh_addrs else []
        self.iface_addrs = iface_addrs if iface_addrs else []
        self.link_ids = link_ids if link_ids else []
        self.topology_ids = topology_ids if topology_ids else []
        self.nexthop = nexthop
        self.route_d = route_d
        self._packed = packed

    @classmethod
    def unpack_nlri(cls, data, rd):
        proto_id = unpack('!B', data[0:1])[0]
        # FIXME: all these list should probably be defined in the objects
        iface_addrs = []
        neigh_addrs = []
        link_identifiers = []
        topology_ids = []
        remote_node = []
        local_node = []
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')
        domain = unpack('!Q', data[1:9])[0]
        tlvs = data[9:]

        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            value = tlvs[4 : 4 + tlv_length]
            tlvs = tlvs[4 + tlv_length :]

            if tlv_type == 256:
                local_node = []
                while value:
                    # Unpack Local Node Descriptor Sub-TLVs
                    # We pass proto_id as TLV interpretation
                    # follows IGP type
                    node, left = NodeDescriptor.unpack(value, proto_id)
                    local_node.append(node)
                    if left == value:
                        raise RuntimeError('sub-calls should consume data')
                    value = left
                continue

            if tlv_type == 257:
                # Remote Node Descriptor
                remote_node = []
                while value:
                    node, left = NodeDescriptor.unpack(value, proto_id)
                    remote_node.append(node)
                    if left == value:
                        raise RuntimeError('sub-calls should consume data')
                    value = left
                continue

            if tlv_type == 258:
                # Link Local/Remote identifiers
                link_identifiers = LinkIdentifier.unpack(value)
                continue

            if tlv_type in [259, 261]:
                # IPv{4,6} Interface Address
                iface_addrs.append(IfaceAddr.unpack(value))
                continue

            if tlv_type in [260, 262]:
                # IPv{4,6} Neighbor Address
                neigh_addrs.append(NeighAddr.unpack(value))
                continue

            if tlv_type == 263:
                topology_ids.append(MTID.unpack(value))
                continue

            log.critical(lambda tlv_type=tlv_type: f'unknown link TLV {tlv_type}')

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

    def __eq__(self, other):
        return (
            isinstance(other, LINK)
            and self.CODE == other.CODE
            and self.domain == other.domain
            and self.proto_id == other.proto_id
            and self.topology_ids == other.topology_ids
            and self.route_d == other.route_d
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.json()

    def __hash__(self):
        return hash((self.CODE, self.domain, self.proto_id, tuple(self.topology_ids), self.route_d))

    def pack(self, negotiated=None):
        if self._packed:
            return self._packed
        raise RuntimeError('Not implemented')

    def json(self, compact=None):
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
