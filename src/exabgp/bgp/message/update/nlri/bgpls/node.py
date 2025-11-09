"""
node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.nlri import PROTO_CODES
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor

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
#             +------------+----------------------------------+
#   The Protocol-ID field can contain one of the following values:
# ===================================================================== DOMAIN


@BGPLS.register
class NODE(BGPLS):
    CODE = 1
    NAME = 'bgpls-node'
    SHORT_NAME = 'Node'

    def __init__(self, domain, proto_id, node_ids, packed=None, nexthop=None, action=None, route_d=None, addpath=None):
        BGPLS.__init__(self, action, addpath)
        self.domain = domain
        self.proto_id = proto_id
        self.node_ids = node_ids
        self.nexthop = nexthop
        self._pack = packed
        self.route_d = route_d

    def json(self, compact=None):
        nodes = ', '.join(d.json() for d in self.node_ids)
        content = ', '.join(
            [
                f'"ls-nlri-type": "{self.NAME}"',
                f'"l3-routing-topology": {int(self.domain)}',
                f'"protocol-id": {int(self.proto_id)}',
                f'"node-descriptors": [ {nodes} ]',
                f'"nexthop": "{self.nexthop}"',
            ]
        )
        if self.route_d:
            content += f', {self.route_d.json()}'
        return f'{{ {content} }}'

    @classmethod
    def unpack_nlri(cls, data, rd):
        proto_id = unpack('!B', data[0:1])[0]
        if proto_id not in PROTO_CODES.keys():
            raise Exception(f'Protocol-ID {proto_id} is not valid')
        domain = unpack('!Q', data[1:9])[0]

        # unpack list of node descriptors
        node_type, node_length = unpack('!HH', data[9:13])
        if node_type != 256:
            raise Exception(
                f'Unknown type: {node_type}. Only Local Node descriptors are allowed inNode type msg'
            )
        values = data[13 : 13 + node_length]

        node_ids = []
        while values:
            # Unpack Node Descriptor Sub-TLVs
            node_id, left = NodeDescriptor.unpack(values, proto_id)
            node_ids.append(node_id)
            if left == values:
                raise RuntimeError('sub-calls should consume data')
            values = left

        return cls(domain=domain, proto_id=proto_id, node_ids=node_ids, route_d=rd, packed=data)

    def __eq__(self, other):
        return (
            isinstance(other, BGPLS)
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
        return hash((self.proto_id, tuple(self.node_ids)))

    def pack(self, negotiated=None):
        return self._pack
