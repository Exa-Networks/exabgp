"""
link.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.linkid import LinkIdentifier
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ifaceaddr import IfaceAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.neighaddr import NeighAddr
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor


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
    NAME = "bgpls-link"
    SHORT_NAME = "Link"

    def __init__(
        self,
        domain,
        proto_id,
        local_node,
        remote_node,
        neigh_addrs=None,
        iface_addrs=None,
        packed=None,
        link_ids=None,
        nexthop=None,
        action=None,
        route_d=None,
        addpath=None,
    ):
        BGPLS.__init__(self, action, addpath)
        self.domain = domain
        self.proto_id = proto_id
        self.local_node = local_node
        self.remote_node = remote_node
        self.neigh_addrs = neigh_addrs
        self.iface_addrs = iface_addrs
        self.link_ids = link_ids
        self.nexthop = nexthop
        self.route_d = route_d
        self._pack = packed

    @classmethod
    def unpack_nlri(cls, data, rd):
        proto_id = unpack('!B', data[0:1])[0]
        iface_addrs = []
        neigh_addrs = []
        link_identifiers = []
        remote_node = []
        local_node = []
        if proto_id not in PROTO_CODES.keys():
            raise Exception('Protocol-ID {} is not valid'.format(proto_id))
        domain = unpack('!Q', data[1:9])[0]
        tlvs = data[9:]

        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            if tlv_type == 256:
                values = tlvs[4 : 4 + tlv_length]
                local_node = []
                while values:
                    # Unpack Local Node Descriptor Sub-TLVs
                    # We pass proto_id as TLV interpretation
                    # follows IGP type
                    node, left = NodeDescriptor.unpack(values, proto_id)
                    local_node.append(node)
                    if left == tlvs:
                        raise RuntimeError("sub-calls should consume data")
                    values = left
                tlvs = tlvs[4 + tlv_length :]
                continue
            elif tlv_type == 257:
                # Remote Node Descriptor
                values = tlvs[4 : 4 + tlv_length]
                remote_node = []
                while values:
                    node, left = NodeDescriptor.unpack(values, proto_id)
                    remote_node.append(node)
                    if left == tlvs:
                        raise RuntimeError("sub-calls should consume data")
                    values = left
                tlvs = tlvs[4 + tlv_length :]
                continue
            elif tlv_type == 258:
                # Link Local/Remote identifiers
                value = tlvs[4 : 4 + 8]
                link_identifiers = LinkIdentifier.unpack(value)
                tlvs = tlvs[4 + 8 :]
                continue
            elif tlv_type in [259, 261]:
                # IPv{4,6} Interface Address
                value = tlvs[4 : 4 + tlv_length]
                iface_addrs.append(IfaceAddr.unpack(value))
                tlvs = tlvs[4 + tlv_length :]
                continue
            elif tlv_type in [260, 262]:
                # IPv{4,6} Neighbor Address
                value = tlvs[4 : 4 + tlv_length]
                neigh_addrs.append(NeighAddr.unpack(value))
                tlvs = tlvs[4 + tlv_length :]
                continue

        return cls(
            domain=domain,
            proto_id=proto_id,
            local_node=local_node,
            remote_node=remote_node,
            neigh_addrs=neigh_addrs,
            iface_addrs=iface_addrs,
            link_ids=link_identifiers,
            route_d=rd,
            packed=data,
        )

    def __eq__(self, other):
        return (
            isinstance(other, LINK)
            and self.CODE == other.CODE
            and self.domain == other.domain
            and self.proto_id == other.proto_id
            and self.route_d == other.route_d
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.json()

    def __hash__(self):
        return hash((self))

    def pack(self, negotiated=None):
        return self._pack

    def json(self, compact=None):
        local = ', '.join(d.json() for d in self.local_node)
        remote = ', '.join(d.json() for d in self.remote_node)
        interface_addrs = ', '.join(d.json() for d in self.iface_addrs)
        neighbor_addrs = ', '.join(d.json() for d in self.neigh_addrs)
        content = '"ls-nlri-type": "%s", ' % self.NAME
        content += '"l3-routing-topology": %d, ' % int(self.domain)
        content += '"protocol-id": %d, ' % int(self.proto_id)
        content += '"local-node-descriptors": { %s }, ' % local
        content += '"remote-node-descriptors": { %s }, ' % remote
        content += '"interface-address": { %s }, ' % interface_addrs
        content += '"neighbor-address": { %s }' % neighbor_addrs
        if self.link_ids:
            links = ', '.join(d.json() for d in self.link_ids)
            content += '" ,link-identifiers": { %s }' % links
        if self.route_d:
            content += ", { %s }" % self.route_d.json()
        return '{ %s }' % content
