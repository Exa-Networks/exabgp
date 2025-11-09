
"""
node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import unpack

from exabgp.protocol.ip import IP
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


class NodeDescriptor:
    _known_tlvs = {
        512: 'autonomous-system',
        513: 'bgp-ls-identifier',
        514: 'ospf-area-id',
        515: 'router-id',
    }

    _error_tlvs = {
        512: 'Invalid autonomous-system sub-tlv',
        513: 'Invalid bgp-ls-identifier sub-tlv',
        514: 'Invalid ospf-area-id sub-tlv',
        515: 'Invalid router-id sub-tlv',
    }

    def __init__(self, node_id, node_type, psn=None, dr_id=None, packed=None):
        self.node_id = node_id
        self.node_type = node_type
        self.psn = psn
        self.dr_id = dr_id
        self._packed = packed

    @classmethod
    def unpack(cls, data, igp):
        node_type, length = unpack('!HH', data[0:4])
        packed = data[: 4 + length]
        payload = packed[4:]
        remaining = data[4 + length :]

        node_id = None
        dr_id = None
        psn = None

        # autonomous-system
        if node_type == 512:
            if length != 4:
                raise Exception(cls._error_tlvs[node_type])
            node_id = unpack('!L', payload)[0]
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # bgp-ls-id
        if node_type == 513:
            if length != 4:
                raise Exception(cls._error_tlvs[node_type])
            node_id = unpack('!L', payload)[0]
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # ospf-area-id
        if node_type == 514:
            if length not in (4, 16):  # FIXME: it may only need to be 4
                raise Exception(cls._error_tlvs[node_type])
            node_id = IP.unpack(payload)
            return cls(node_id, node_type, psn, dr_id, packed), remaining

        # IGP Router-ID: The TLV size in combination with the protocol
        # identifier enables the decoder to determine the node_typee
        # of the node: sec 3.2.1.4.
        if node_type == 515:
            # IS-IS non-pseudonode
            if igp in (1, 2):
                if length not in (6, 7):
                    raise Exception(cls._error_tlvs[node_type])
                node_id = (ISO.unpack_sysid(payload),)
                if length == 7:
                    psn = unpack('!B', payload[6:7])[0]
                return cls(node_id, node_type, psn, dr_id, packed), remaining

            # OSPFv{2,3} non-pseudonode
            if igp in (3, 5, 6, 227):
                if length not in (4, 8):
                    raise Exception(cls._error_tlvs[node_type])
                node_id = (IP.unpack(payload[:4]),)
                if length == 8:
                    dr_id = IP.unpack(payload[4:8])
                return cls(node_id, node_type, psn, dr_id, packed), remaining

        raise Exception(f'unknown node descriptor sub-tlv (node-type: {node_type}, igp: {igp})')

    def json(self, compact=None):
        node = None
        if self.node_type == 512:
            node = f'"autonomous-system": {self.node_id}'
        if self.node_type == 513:
            node = f'"bgp-ls-identifier": "{self.node_id}"'
        if self.node_type == 514:
            node = f'"ospf-area-id": "{self.node_id}"'
        if self.node_type == 515:
            node = f'"router-id": "{self.node_id[0]}"'
        designated = None
        if self.dr_id:
            designated = f'"designated-router-id": "{self.dr_id}"'
        psn = None
        if self.psn:
            psn = f'"psn": "{self.psn}"'
        content = ', '.join(_ for _ in [node, designated, psn] if _)
        return f'{{ {content} }}'

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
