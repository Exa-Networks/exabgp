"""node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import IPv6
from exabgp.protocol.iso import ISO

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
    def unpack_node(cls, data, igp):
        node_type, length = unpack('!HH', data[0:4])
        packed = data[: 4 + length]
        payload = packed[4:]
        remaining = data[4 + length :]

        node_id = None
        dr_id = None
        psn = None

        # autonomous-system
        if node_type == NODE_DESC_TLV_AS:
            if length != NODE_DESC_AS_LENGTH:
                raise Exception(cls._error_tlvs[node_type])
            node_id = unpack('!L', payload)[0]
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # bgp-ls-id
        if node_type == NODE_DESC_TLV_BGPLS_ID:
            if length != NODE_DESC_BGPLS_ID_LENGTH:
                raise Exception(cls._error_tlvs[node_type])
            node_id = unpack('!L', payload)[0]
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # ospf-area-id
        if node_type == NODE_DESC_TLV_OSPF_AREA:
            if length not in (NODE_DESC_OSPF_AREA_LENGTH, IPv6.BYTES):  # FIXME: it may only need to be 4
                raise Exception(cls._error_tlvs[node_type])
            node_id = IP.unpack_ip(payload)
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # IGP Router-ID: The TLV size in combination with the protocol
        # identifier enables the decoder to determine the node_typee
        # of the node: sec 3.2.1.4.
        if node_type == NODE_DESC_TLV_IGP_ROUTER:
            # IS-IS non-pseudonode
            if igp in (IGP_ISIS_L1, IGP_ISIS_L2):
                if length not in (ISIS_SYSID_LENGTH, ISIS_SYSID_PSN_LENGTH):
                    raise Exception(cls._error_tlvs[node_type])
                node_id = (ISO.unpack_sysid(payload),)
                if length == ISIS_SYSID_PSN_LENGTH:
                    psn = unpack('!B', payload[6:7])[0]
                return cls(node_id, node_type, psn, dr_id, packed), remaining

            # OSPFv{2,3} non-pseudonode
            if igp in (IGP_OSPFV2, IGP_DIRECT, IGP_OSPFV3, IGP_STATIC):
                if length not in (OSPF_ROUTER_ID_LENGTH, OSPF_ROUTER_DR_LENGTH):
                    raise Exception(cls._error_tlvs[node_type])
                node_id = (IP.unpack_ip(payload[:4]),)
                if length == OSPF_ROUTER_DR_LENGTH:
                    dr_id = IP.unpack_ip(payload[4:8])
                return cls(node_id, node_type, psn, dr_id, packed), remaining

        raise Exception(f'unknown node descriptor sub-tlv (node-type: {node_type}, igp: {igp})')

    def json(self, compact: bool = False):
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
            return False
        return self.node_id == other.node_id

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

    def pack_tlv(self):
        if self._packed:
            return self._packed
        raise RuntimeError('pack when not fully implemented for {self.__name__}')
