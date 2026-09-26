"""node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
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

# BGP-LS Node Descriptor TLV type
NODE_DESCRIPTOR_TYPE = 256  # Local Node Descriptors TLV type
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
        # `_packed`, not `_pack`.  The base class reads `_packed` in pack_nlri, __len__ and
        # index, so writing the wire to `_pack` left `_packed` at the b'' the base set and
        # pack_nlri answered a four octet header announcing a length of zero: identical for
        # every route of this type, which is what index() keys the RIB on.  The name is not
        # an override of anything this class has, GenericBGPLS is a sibling rather than an
        # ancestor, which is why nothing ever raised.
        if packed is not None:
            self._packed = packed
        self.route_d = route_d

    def as_dict(self):
        nlri = BGPLS.as_dict(self)
        nlri['parsed'] = True
        nlri['l3-routing-topology'] = int(self.domain)
        nlri['protocol-id'] = int(self.proto_id)
        nlri['node-descriptors'] = [d.as_dict() for d in self.node_ids]
        nlri['nexthop'] = None if self.nexthop is None else str(self.nexthop)
        nlri['rd'] = None if self.route_d is None else self.route_d._str()
        return nlri

    def json(self, compact=None):
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
    def unpack_nlri(cls, data, rd):
        cls.check_length(data, cls.DESCRIPTOR_OFFSET)
        # RFC 9552 8.2.2: the NLRI may not be called malformed over the contents of a
        # field, so an unrecognised Protocol-ID is carried rather than refused.  It is
        # still read, because the IGP Router-ID sub-TLV is typed by it.
        proto_id = unpack('!B', data[0:1])[0]
        domain = unpack('!Q', data[1:9])[0]

        # unpack list of node descriptors
        tlvs = list(cls.iter_tlvs(data[cls.DESCRIPTOR_OFFSET :]))
        if not tlvs:
            raise Notify(3, 10, 'BGP-LS Node NLRI has no Local Node descriptor')
        node_type, values = tlvs[0]
        if node_type != NODE_DESCRIPTOR_TYPE:
            raise Notify(
                3,
                10,
                f'Unknown type: {node_type}. Only Local Node descriptors are allowed in a Node type msg',
            )

        # Unpack the Node Descriptor Sub-TLVs, holding them to RFC 9552 5.2.1: one
        # instance of each sub-TLV type at most, and ascending order by type.
        node_ids = NodeDescriptor.unpack_descriptors(values, proto_id)

        return cls(domain=domain, proto_id=proto_id, node_ids=node_ids, route_d=rd, packed=data)

    # The identity of these NLRI is their wire: the descriptors are what tell two routes of
    # one type apart, and `_packed` holds them.  __eq__ used to compare only CODE, domain,
    # proto_id and route_d, so two prefixes of one domain were equal whatever they described,
    # and NODE.__hash__ used (proto_id, node_ids) while its __eq__ used neither, which breaks
    # the rule that equal objects hash equal.  Both now read the same tuple, and it is the
    # same information index() carries, so equality agrees with RIB identity.
    def _identity(self):
        return (self.CODE, self.domain, self.proto_id, self.route_d, self._packed)

    def __eq__(self, other):
        return isinstance(other, NODE) and self._identity() == other._identity()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.json()

    def __hash__(self):
        return hash((self.proto_id, tuple(self.node_ids)))

    def pack(self, negotiated=None):
        return self._packed
