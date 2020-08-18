"""
prefixv4.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ospfroute import OspfRoute
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach

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
    CODE = 3
    NAME = "bgpls-prefix-v4"
    SHORT_NAME = "PREFIX_V4"

    def __init__(
        self,
        domain,
        proto_id,
        local_node,
        packed=None,
        ospf_type=None,
        prefix=None,
        nexthop=None,
        route_d=None,
        action=None,
        addpath=None,
    ):
        BGPLS.__init__(self, action, addpath)
        self.domain = domain
        self.ospf_type = ospf_type
        self.proto_id = proto_id
        self.local_node = local_node
        self.prefix = prefix
        self.nexthop = nexthop
        self._pack = packed
        self.route_d = route_d

    @classmethod
    def unpack_nlri(cls, data, rd):
        ospf_type = None
        proto_id = unpack('!B', data[0:1])[0]
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
                    if left == values:
                        raise RuntimeError("sub-calls should consume data")
                    values = left
                tlvs = tlvs[4 + tlv_length :]
                continue
            if tlv_type == 264:
                values = tlvs[4 : 4 + tlv_length]
                ospf_type = OspfRoute.unpack(values)
                tlvs = tlvs[4 + tlv_length :]
            if tlv_type == 265:
                values = tlvs[4 : 4 + tlv_length]
                prefix = IpReach.unpack(values, 3)
                tlvs = tlvs[4 + tlv_length :]

        return cls(
            domain=domain,
            proto_id=proto_id,
            packed=data,
            local_node=local_node,
            ospf_type=ospf_type,
            prefix=prefix,
            route_d=rd,
        )

    def __eq__(self, other):
        return (
            isinstance(other, PREFIXv4)
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

    def json(self, compact=None):
        nodes = ', '.join(d.json() for d in self.local_node)
        content = ', '.join(
            [
                '"ls-nlri-type": "%s"' % self.NAME,
                '"l3-routing-topology": %d' % int(self.domain),
                '"protocol-id": %d' % int(self.proto_id),
                '"node-descriptors": { %s }' % nodes,
                self.prefix.json(),
                '"nexthop": "%s"' % self.nexthop,
            ]
        )
        if self.ospf_type:
            content += ', %s' % self.ospf_type.json()

        if self.route_d:
            content += ', %s' % self.route_d.json()

        return '{ %s }' % (content)

    def pack(self, negotiated=None):
        return self._pack
