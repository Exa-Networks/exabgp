"""prefixv4.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ospfroute import OspfRoute
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach

from exabgp.logger import log

# BGP-LS Prefix TLV type codes (RFC 7752)
TLV_LOCAL_NODE_DESC = 256  # Local Node Descriptors TLV
TLV_OSPF_ROUTE_TYPE = 264  # OSPF Route Type TLV
TLV_IP_REACHABILITY = 265  # IP Reachability Information TLV

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
    NAME = 'bgpls-prefix-v4'
    SHORT_NAME = 'PREFIX_V4'

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
        # `_packed`, not `_pack`.  The base class reads `_packed` in pack_nlri, __len__ and
        # index, so writing the wire to `_pack` left `_packed` at the b'' the base set and
        # pack_nlri answered a four octet header announcing a length of zero: identical for
        # every route of this type, which is what index() keys the RIB on.  The name is not
        # an override of anything this class has, GenericBGPLS is a sibling rather than an
        # ancestor, which is why nothing ever raised.
        if packed is not None:
            self._packed = packed
        self.route_d = route_d

    @classmethod
    def unpack_nlri(cls, data, rd):
        ospf_type = None
        local_node = []
        prefix = None
        cls.check_length(data, cls.DESCRIPTOR_OFFSET)
        # RFC 9552 8.2.2: the NLRI may not be called malformed over the contents of a
        # field, so an unrecognised Protocol-ID is carried rather than refused.  It is
        # still read, because the IGP Router-ID sub-TLV is typed by it.
        proto_id = unpack('!B', data[0:1])[0]
        domain = unpack('!Q', data[1:9])[0]
        seen = set()
        for tlv_type, value in cls.iter_tlvs(data[cls.DESCRIPTOR_OFFSET :]):
            seen.add(tlv_type)
            if tlv_type == TLV_LOCAL_NODE_DESC:
                # proto_id goes in because a sub-TLV's shape follows the IGP type.
                # RFC 9552 5.2.1: one instance of each sub-TLV type at most, ascending by type.
                local_node = NodeDescriptor.unpack_descriptors(value, proto_id)
                continue

            if tlv_type == TLV_OSPF_ROUTE_TYPE:
                ospf_type = OspfRoute.unpack(value)
                continue

            if tlv_type == TLV_IP_REACHABILITY:
                prefix = IpReach.unpack(value, 3)
                continue

            log.critical(lambda tlv_type=tlv_type: f'unknown prefix v4 TLV {tlv_type}')

        # RFC 7752 section 3.2 makes both mandatory, but only one of them is load bearing here.
        # Without the reachability TLV the accessors have nothing to read and json() fails, so
        # that one is refused. The Local Node Descriptors are not read by anything on this path,
        # and a prefix NLRI without them decoded and rendered before, so refusing it would drop
        # a route on upgrade. RFC 9552 8.2.2 is explicit that an NLRI is not to be called
        # malformed over which optional TLVs it includes or excludes, and link.py in this same
        # package already accepts their absence.
        if TLV_IP_REACHABILITY not in seen:
            raise Notify(3, 10, f'BGP-LS {cls.NAME} NLRI is missing the IP Reachability Information TLV')

        if TLV_LOCAL_NODE_DESC not in seen:
            log.debug(
                lambda: f'BGP-LS {cls.NAME} NLRI carries no Local Node Descriptors TLV',
                'parser',
            )

        return cls(
            domain=domain,
            proto_id=proto_id,
            packed=data,
            local_node=local_node,
            ospf_type=ospf_type,
            prefix=prefix,
            route_d=rd,
        )

    # The identity of these NLRI is their wire: the descriptors are what tell two routes of
    # one type apart, and `_packed` holds them.  __eq__ used to compare only CODE, domain,
    # proto_id and route_d, so two prefixes of one domain were equal whatever they described,
    # and NODE.__hash__ used (proto_id, node_ids) while its __eq__ used neither, which breaks
    # the rule that equal objects hash equal.  Both now read the same tuple, and it is the
    # same information index() carries, so equality agrees with RIB identity.
    def _identity(self):
        return (self.CODE, self.domain, self.proto_id, self.route_d, self._packed)

    def __eq__(self, other):
        return isinstance(other, PREFIXv4) and self._identity() == other._identity()

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return self.json()

    def __hash__(self):
        return hash(self._identity())

    def as_dict(self):
        nlri = BGPLS.as_dict(self)
        nlri['parsed'] = True
        nlri['l3-routing-topology'] = int(self.domain)
        nlri['protocol-id'] = int(self.proto_id)
        nlri['node-descriptors'] = [d.as_dict() for d in self.local_node]
        nlri.update(self.prefix.as_dict())
        nlri['nexthop'] = None if self.nexthop is None else str(self.nexthop)
        if self.ospf_type:
            nlri.update(self.ospf_type.as_dict())
        nlri['rd'] = None if self.route_d is None else self.route_d._str()
        return nlri

    def json(self, compact=None):
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

    def pack(self, negotiated=None):
        return self._packed
