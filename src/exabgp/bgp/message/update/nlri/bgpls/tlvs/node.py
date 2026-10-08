"""node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from struct import unpack
from typing import Any, ClassVar

from exabgp.bgp.message.notification import NLRIDiscard, Notify
from exabgp.protocol.ip import IP
from exabgp.protocol.ip import IPv6
from exabgp.protocol.iso import ISO
from exabgp.util import hexstring
from exabgp.util.types import Buffer

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

# IGP Protocol Identifiers (RFC 9552 section 5.2, Table 2)
IGP_ISIS_L1 = 1  # IS-IS Level 1
IGP_ISIS_L2 = 2  # IS-IS Level 2
IGP_OSPFV2 = 3  # OSPFv2
IGP_DIRECT = 4  # Direct
IGP_STATIC = 5  # Static configuration
IGP_OSPFV3 = 6  # OSPFv3
# Not assigned by IANA: freertr's own value, which this decoder has always read with the
# OSPF Router-ID shapes.  It was named IGP_STATIC, while 5, which is Static configuration,
# was named IGP_DIRECT and 4, Direct, was not handled at all.
IGP_FREERTR = 227


class NodeDescriptor:
    _known_tlvs: ClassVar = {
        NODE_DESC_TLV_AS: 'autonomous-system',
        NODE_DESC_TLV_BGPLS_ID: 'bgp-ls-identifier',
        NODE_DESC_TLV_OSPF_AREA: 'ospf-area-id',
        NODE_DESC_TLV_IGP_ROUTER: 'router-id',
    }

    _error_tlvs: ClassVar = {
        NODE_DESC_TLV_AS: 'Invalid autonomous-system sub-tlv',
        NODE_DESC_TLV_BGPLS_ID: 'Invalid bgp-ls-identifier sub-tlv',
        NODE_DESC_TLV_OSPF_AREA: 'Invalid ospf-area-id sub-tlv',
        NODE_DESC_TLV_IGP_ROUTER: 'Invalid router-id sub-tlv',
    }

    def __init__(
        self,
        node_id: Any,  # int | IP | tuple - varies by node_type
        node_type: int,
        psn: int | None,
        dr_id: IP | None,
        packed: Buffer,
    ) -> None:
        self.node_id = node_id
        self.node_type = node_type
        self.psn = psn
        self.dr_id = dr_id
        self._packed = packed

    @classmethod
    def unpack_node(cls, data: Buffer, igp: int) -> tuple['NodeDescriptor', Buffer]:
        if len(data) < 4:
            raise Notify.short(3, 10, 'BGP-LS node descriptor header', 4, len(data))
        node_type, length = unpack('!HH', bytes(data[0:4]))
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
        dr_id: IP | None = None
        psn: int | None = None

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
            node_id = IP.create_ip(payload)
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        if node_type == NODE_DESC_TLV_IGP_ROUTER:
            descriptor = cls._unpack_igp_router_id(payload, igp, packed)
            if descriptor is not None:
                return descriptor, remaining

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
    def _unpack_igp_router_id(cls, payload: Buffer, igp: int, packed: Buffer) -> 'NodeDescriptor | None':
        """The IGP Router-ID, read as the Protocol-ID says, or None for a protocol we cannot read.

        RFC 9552 5.2.1.4: "The TLV size in combination with the protocol identifier enables
        the decoder to determine the type of the node."
        """
        length = len(payload)
        node_type = NODE_DESC_TLV_IGP_ROUTER
        # IS-IS, a non-pseudonode or, with its PSN, a pseudonode
        if igp in (IGP_ISIS_L1, IGP_ISIS_L2):
            if length not in (ISIS_SYSID_LENGTH, ISIS_SYSID_PSN_LENGTH):
                raise Notify(3, 10, cls._error_tlvs[node_type])
            psn = unpack('!B', payload[6:7])[0] if length == ISIS_SYSID_PSN_LENGTH else None
            return cls((ISO.unpack_sysid(payload),), node_type, psn, None, packed)

        # OSPFv{2,3}, a non-pseudonode or, with the DR's interface, a pseudonode
        if igp in (IGP_OSPFV2, IGP_OSPFV3, IGP_FREERTR):
            if length not in (OSPF_ROUTER_ID_LENGTH, OSPF_ROUTER_DR_LENGTH):
                raise Notify(3, 10, cls._error_tlvs[node_type])
            dr_id = IP.create_ip(payload[4:8]) if length == OSPF_ROUTER_DR_LENGTH else None
            return cls((IP.create_ip(payload[:4]),), node_type, None, dr_id, packed)

        # "For 'Direct' or 'Static configuration', the value SHOULD be taken from an IPv4
        # or IPv6 address (e.g., loopback interface) configured on the node."  It MAY be
        # an IGP Router-ID instead, of whichever IGP, so any other size is not an error:
        # it is kept as bytes, by the generic descriptor the caller falls back to.
        if igp in (IGP_DIRECT, IGP_STATIC) and length in (OSPF_ROUTER_ID_LENGTH, IPv6.BYTES):
            return cls((IP.create_ip(payload),), node_type, None, None, packed)

        return None

    @classmethod
    def unpack_descriptors(cls, data: Buffer, igp: int) -> list['NodeDescriptor']:
        """Read a whole Node Descriptor value, and hold it to the two rules of RFC 9552 5.2.1.

        "At most, there MUST be one instance of each sub-TLV type present in any Node
        Descriptor.  The sub-TLVs within a Node Descriptor MUST be arranged in ascending
        order by sub-TLV type."  Section 8.2.2 lists both as syntactic validation a BGP-LS
        speaker MUST perform, and the ordering rule as the very example of an error the
        NLRI is malformed for.

        The comparison is on the sub-TLV *type code* and on nothing else, which is what
        keeps it clear of the other half of 8.2.2: a Link-State NLRI "MUST NOT be
        considered malformed or invalid based on the inclusion/exclusion of TLVs or
        contents of the TLV fields".  An unrecognised code is still accepted, still kept
        byte for byte as a `GenericNodeDescriptor`, and is only required to be in its place
        in the order, which is the reason 5.2.1 gives for asking for the order at all:
        "This needs to be done to compare NLRIs, even when an implementation encounters an
        unknown sub-TLV."  Two NLRIs which differ only in the order of their sub-TLVs would
        otherwise be two RIB entries for one link-state object.
        """
        descriptors: list['NodeDescriptor'] = []
        previous: int | None = None
        while data:
            descriptor, remaining = cls.unpack_node(data, igp)
            # RFC 9552 8.2.2: a rule broken inside a length which still frames the NLRI
            if previous is not None and descriptor.node_type == previous:
                raise NLRIDiscard(f'BGP-LS node descriptor sub-tlv {descriptor.node_type} is present more than once')
            if previous is not None and descriptor.node_type < previous:
                raise NLRIDiscard(
                    f'BGP-LS node descriptor sub-tlv {descriptor.node_type} follows {previous}, '
                    f'which is not the ascending order required'
                )
            previous = descriptor.node_type
            descriptors.append(descriptor)
            # `unpack_node` always consumes its four octet header, so this cannot loop, but
            # the bound is written down rather than reasoned about at every call site.
            if len(remaining) >= len(data):
                raise Notify(3, 10, 'BGP-LS node descriptor made no progress')
            data = remaining
        return descriptors

    def json(self, compact: bool = False) -> str:
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

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NodeDescriptor):
            return NotImplemented
        return bool(self.node_id == other.node_id)

    # written out: mypyc fails to derive __ne__ from __eq__ for the subclasses. The operator,
    # not a call to __eq__, so NotImplemented is answered the way Python answers it.
    def __ne__(self, other: object) -> bool:
        return not self == other

    def __lt__(self, other: NodeDescriptor) -> bool:
        raise RuntimeError('Not implemented')

    def __le__(self, other: NodeDescriptor) -> bool:
        raise RuntimeError('Not implemented')

    def __gt__(self, other: NodeDescriptor) -> bool:
        raise RuntimeError('Not implemented')

    def __ge__(self, other: NodeDescriptor) -> bool:
        raise RuntimeError('Not implemented')

    def __str__(self) -> str:
        return self.json()

    def __repr__(self) -> str:
        return self.__str__()

    def __len__(self) -> int:
        return len(self._packed)

    def __hash__(self) -> int:
        return hash(str(self))

    def pack_tlv(self) -> Buffer:
        return self._packed


class GenericNodeDescriptor(NodeDescriptor):
    """A Node Descriptor sub-TLV whose code this build does not implement.

    The sibling of `GenericLSID` on the NLRI side of RFC 9552 5.1.  `_packed` is the whole
    sub-TLV, header included, so `pack_tlv` propagates it byte for byte, and the render
    carries the code so two unknown codes in one descriptor do not collide.
    """

    def __init__(self, node_type: int, payload: Buffer, packed: Buffer) -> None:
        NodeDescriptor.__init__(self, bytes(payload), node_type, None, None, packed)

    def json(self, compact: bool = False) -> str:
        return f'{{ "generic-node-descriptor-{self.node_type}": "{hexstring(self.node_id)}" }}'
