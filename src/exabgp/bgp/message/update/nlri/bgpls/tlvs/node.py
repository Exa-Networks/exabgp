"""node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.protocol.ip import IP
from exabgp.protocol.ip import IPv6
from exabgp.protocol.iso import ISO
from exabgp.util import hexstring

#           +--------------------+-------------------+----------+
#           | Sub-TLV Code Point | Description       |   Length |
#           +--------------------+-------------------+----------+
#           |        512         | Autonomous System |        4 |
#           |        513         | BGP-LS Identifier |        4 |
#           |        514         | OSPF Area-ID      |        4 |
#           |        515         | IGP Router-ID     | Variable |
#           +--------------------+-------------------+----------+
#            https://tools.ietf.org/html/rfc7752#section-3.2.1.4
# ================================================================== NODE-DESC-SUB-TLVs

# BGP-LS Node Descriptor Sub-TLV Types (RFC 7752)
NODE_DESC_TLV_AS = 512  # Autonomous System Number TLV
NODE_DESC_TLV_BGPLS_ID = 513  # BGP-LS Identifier TLV
NODE_DESC_TLV_OSPF_AREA = 514  # OSPF Area ID TLV
NODE_DESC_TLV_IGP_ROUTER = 515  # IGP Router ID TLV

# Fixed lengths for Node Descriptor TLVs
NODE_DESC_AS_LENGTH = 4  # Autonomous System Number is 4 bytes
NODE_DESC_BGPLS_ID_LENGTH = 4  # BGP-LS Identifier is 4 bytes
NODE_DESC_OSPF_AREA_LENGTH = 4  # OSPF Area ID is 4 bytes (may also be 16 for IPv6)

# IGP Router ID lengths
ISIS_SYSID_LENGTH = 6  # IS-IS System ID length
ISIS_SYSID_PSN_LENGTH = 7  # IS-IS System ID + PSN length
OSPF_ROUTER_ID_LENGTH = 4  # OSPF Router ID length (IPv4)
OSPF_ROUTER_DR_LENGTH = 8  # OSPF Router ID + DR ID length

# IGP Protocol Identifiers (RFC 7752 Section 3.2)
IGP_ISIS_L1 = 1  # IS-IS Level 1
IGP_ISIS_L2 = 2  # IS-IS Level 2
IGP_OSPFV2 = 3  # OSPFv2
IGP_OSPFV3 = 6  # OSPFv3
IGP_DIRECT = 5  # Direct
IGP_STATIC = 227  # Static configuration


class NodeDescriptor:
    _known_tlvs = {
        NODE_DESC_TLV_AS: 'autonomous-system',
        NODE_DESC_TLV_BGPLS_ID: 'bgp-ls-identifier',
        NODE_DESC_TLV_OSPF_AREA: 'ospf-area-id',
        NODE_DESC_TLV_IGP_ROUTER: 'router-id',
    }

    _error_tlvs = {
        NODE_DESC_TLV_AS: 'Invalid autonomous-system sub-tlv',
        NODE_DESC_TLV_BGPLS_ID: 'Invalid bgp-ls-identifier sub-tlv',
        NODE_DESC_TLV_OSPF_AREA: 'Invalid ospf-area-id sub-tlv',
        NODE_DESC_TLV_IGP_ROUTER: 'Invalid router-id sub-tlv',
    }

    def __init__(self, node_id, node_type, psn=None, dr_id=None, packed=None):
        self.node_id = node_id
        self.node_type = node_type
        self.psn = psn
        self.dr_id = dr_id
        self._packed = packed

    @classmethod
    def unpack(cls, data, igp):
        if len(data) < 4:
            raise Notify(3, 10, f'BGP-LS node descriptor is too short: need 4 bytes of header, got {len(data)}')
        node_type, length = unpack('!HH', data[0:4])
        if len(data) < 4 + length:
            raise Notify(
                3,
                10,
                f'BGP-LS node descriptor sub-tlv {node_type} claims {length} bytes but only {len(data) - 4} remain',
            )
        packed = data[: 4 + length]
        payload = packed[4:]
        remaining = data[4 + length :]

        node_id = None
        dr_id = None
        psn = None

        # autonomous-system
        if node_type == NODE_DESC_TLV_AS:
            if length != NODE_DESC_AS_LENGTH:
                raise Notify(3, 10, cls._error_tlvs[node_type])
            node_id = unpack('!L', payload)[0]
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # bgp-ls-id
        if node_type == NODE_DESC_TLV_BGPLS_ID:
            if length != NODE_DESC_BGPLS_ID_LENGTH:
                raise Notify(3, 10, cls._error_tlvs[node_type])
            node_id = unpack('!L', payload)[0]
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # ospf-area-id
        if node_type == NODE_DESC_TLV_OSPF_AREA:
            if length not in (NODE_DESC_OSPF_AREA_LENGTH, IPv6.BYTES):  # FIXME: it may only need to be 4
                raise Notify(3, 10, cls._error_tlvs[node_type])
            node_id = IP.unpack(payload)
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # IGP Router-ID: The TLV size in combination with the protocol
        # identifier enables the decoder to determine the node_typee
        # of the node: sec 3.2.1.4.
        if node_type == NODE_DESC_TLV_IGP_ROUTER:
            # IS-IS non-pseudonode
            if igp in (IGP_ISIS_L1, IGP_ISIS_L2):
                if length not in (ISIS_SYSID_LENGTH, ISIS_SYSID_PSN_LENGTH):
                    raise Notify(3, 10, cls._error_tlvs[node_type])
                node_id = (ISO.unpack_sysid(payload),)
                if length == ISIS_SYSID_PSN_LENGTH:
                    psn = unpack('!B', payload[6:7])[0]
                return cls(node_id, node_type, psn, dr_id, packed), remaining

            # OSPFv{2,3} non-pseudonode
            if igp in (IGP_OSPFV2, IGP_DIRECT, IGP_OSPFV3, IGP_STATIC):
                if length not in (OSPF_ROUTER_ID_LENGTH, OSPF_ROUTER_DR_LENGTH):
                    raise Notify(3, 10, cls._error_tlvs[node_type])
                node_id = (IP.unpack(payload[:4]),)
                if length == OSPF_ROUTER_DR_LENGTH:
                    dr_id = IP.unpack(payload[4:8])
                return cls(node_id, node_type, psn, dr_id, packed), remaining

        # RFC 9552 5.1: "Unknown and unsupported types MUST be preserved and propagated
        # within both the NLRI and the BGP-LS Attribute.  The presence of unknown or
        # unexpected TLVs MUST NOT result in the NLRI or the BGP-LS Attribute being
        # considered malformed."  516, BGP Router Identifier, was assigned by RFC 9086
        # after the four codes above were written, so refusing it took the session down
        # against a conforming producer.  This is the answer the BGP-LS Attribute side
        # has always given an unregistered TLV code, in GenericLSID: keep the bytes.
        #
        # An IGP Router-ID under a Protocol-ID this decoder does not know lands here too,
        # and for the same reason: its shape is defined by the protocol, so without the
        # protocol there is nothing to read it as but bytes.
        return GenericNodeDescriptor(node_type, payload, packed), remaining

    @classmethod
    def unpack_descriptors(cls, data, igp):
        """Read a whole Node Descriptor value, and hold it to the two rules of RFC 9552 5.2.1.

        "At most, there MUST be one instance of each sub-TLV type present in any Node
        Descriptor.  The sub-TLVs within a Node Descriptor MUST be arranged in ascending
        order by sub-TLV type."  Section 8.2.2 lists both as syntactic validation a BGP-LS
        speaker MUST perform, and names the ordering rule as its example of an error which
        makes the NLRI malformed.

        The comparison is on the sub-TLV *type code* and on nothing else, which is what
        keeps it clear of the other half of 8.2.2: a Link-State NLRI "MUST NOT be
        considered malformed or invalid based on the inclusion/exclusion of TLVs or
        contents of the TLV fields".  An unregistered code is still accepted, still kept
        byte for byte as a `GenericNodeDescriptor`, and is only required to be in its place
        in the order, which is the reason 5.2.1 gives for asking for the order at all:
        "This needs to be done to compare NLRIs, even when an implementation encounters an
        unknown sub-TLV."  Two NLRIs differing only in the order of their sub-TLVs would
        otherwise be two RIB entries for one link-state object.
        """
        descriptors = []
        previous = None
        while data:
            descriptor, remaining = cls.unpack(data, igp)
            if previous is not None and descriptor.node_type == previous:
                raise Notify(3, 10, f'BGP-LS node descriptor sub-tlv {descriptor.node_type} is present more than once')
            if previous is not None and descriptor.node_type < previous:
                raise Notify(
                    3,
                    10,
                    f'BGP-LS node descriptor sub-tlv {descriptor.node_type} follows {previous}, '
                    f'which is not the ascending order required',
                )
            previous = descriptor.node_type
            descriptors.append(descriptor)
            # `unpack` always consumes its four octet header, so this cannot loop, but the
            # bound is written down here rather than reasoned about at every call site.
            if len(remaining) >= len(data):
                raise Notify(3, 10, 'BGP-LS node descriptor made no progress')
            data = remaining
        return descriptors

    def json(self, compact=None):
        node = None
        if self.node_type == NODE_DESC_TLV_AS:
            node = f'"autonomous-system": {self.node_id}'
        if self.node_type == NODE_DESC_TLV_BGPLS_ID:
            node = f'"bgp-ls-identifier": "{self.node_id}"'
        if self.node_type == NODE_DESC_TLV_OSPF_AREA:
            node = f'"ospf-area-id": "{self.node_id}"'
        if self.node_type == NODE_DESC_TLV_IGP_ROUTER:
            node = f'"router-id": "{self.node_id[0]}"'
        designated = None
        if self.dr_id:
            designated = f'"designated-router-id": "{self.dr_id}"'
        psn = None
        if self.psn:
            psn = f'"psn": "{self.psn}"'
        content = ', '.join(_ for _ in [node, designated, psn] if _)
        return f'{{ {content} }}'

    def as_dict(self):
        result = {}
        if self.node_type == NODE_DESC_TLV_AS:
            result['autonomous-system'] = self.node_id
        if self.node_type == NODE_DESC_TLV_BGPLS_ID:
            result['bgp-ls-identifier'] = str(self.node_id)
        if self.node_type == NODE_DESC_TLV_OSPF_AREA:
            result['ospf-area-id'] = str(self.node_id)
        if self.node_type == NODE_DESC_TLV_IGP_ROUTER:
            result['router-id'] = str(self.node_id[0])
        if self.dr_id:
            result['designated-router-id'] = str(self.dr_id)
        if self.psn:
            result['psn'] = str(self.psn)
        return result

    def __eq__(self, other):
        return isinstance(other, NodeDescriptor) and self.node_id == other.node_id

    def __neq__(self, other):
        return self.node_id != other.node_id

    def __lt__(self, other):
        raise RuntimeError('Not implemented')

    def __le__(self, other):
        raise RuntimeError('Not implemented')

    def __gt__(self, other):
        raise RuntimeError('Not implemented')

    def __ge__(self, other):
        raise RuntimeError('Not implemented')

    def __str__(self):
        return self.json()

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(self._packed)

    def __hash__(self):
        return hash(str(self))

    def pack(self):
        if self._packed:
            return self._packed
        raise RuntimeError('pack when not fully implemented for {self.__name__}')


class GenericNodeDescriptor(NodeDescriptor):
    """A Node Descriptor sub-TLV whose code this build does not implement.

    The sibling of `GenericLSID` on the NLRI side of RFC 9552 5.1.  `_packed` is the whole
    sub-TLV, header included, so `pack` propagates it byte for byte, and both renderers
    carry the code so two unknown codes in one descriptor do not collide.
    """

    def __init__(self, node_type, payload, packed):
        NodeDescriptor.__init__(self, bytes(payload), node_type, None, None, packed)

    def _key(self):
        return f'generic-node-descriptor-{self.node_type}'

    def json(self, compact=None):
        return f'{{ "{self._key()}": "{hexstring(self.node_id)}" }}'

    def as_dict(self):
        return {self._key(): hexstring(self.node_id)}
