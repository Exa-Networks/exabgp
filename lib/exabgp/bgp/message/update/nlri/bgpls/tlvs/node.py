# encoding: utf-8
"""
node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IP
from exabgp.protocol.iso import ISO
from exabgp.bgp.message.notification import Notify
from exabgp.util import ordinal

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

NODE_TLVS = {
    512: 'autonomous-system',
    513: 'bgp-ls-id',
    514: 'ospf-area-id',
    515: 'igp-rid',
}


# TODO
# 3.2.1.5.  Multi-Topology ID


class NodeDescriptor(object):
    def __init__(self, node_id, dtype, psn=None, dr_id=None, packed=None):
        self.node_id = node_id
        self.dtype = dtype
        self.psn = psn
        self.dr_id = dr_id
        self._packed = packed

    @classmethod
    def unpack(cls, data, igp):
        dtype, dlength = unpack('!HH', data[0:4])
        if dtype not in NODE_TLVS.keys():
            raise Exception("Unknown Node Descriptor Sub-TLV")
        # OSPF Area-ID
        if dtype == 514:
            return (
                cls(node_id=IP.unpack(data[4 : 4 + dlength]), dtype=dtype, packed=data[: 4 + dlength]),
                data[4 + dlength :],
            )
        # IGP Router-ID: The TLV size in combination with the protocol
        # identifier enables the decoder to determine the type
        # of the node: sec 3.2.1.4.
        elif dtype == 515:
            # OSPFv{2,3} non-pseudonode
            if (igp == 3 or igp == 6) and dlength == 4:
                r_id = IP.unpack(data[4 : 4 + 4])
                return cls(node_id=r_id, dtype=dtype, packed=data[: 4 + dlength]), data[4 + 4 :]
            # OSPFv{2,3} LAN pseudonode
            if (igp == 3 or igp == 6) and dlength == 8:
                r_id = IP.unpack(data[4 : 4 + 4])
                dr_id = IP.unpack(data[8 : 4 + 8])
                return cls(node_id=r_id, dtype=dtype, psn=None, dr_id=dr_id, packed=data[: 4 + dlength]), data[4 + 8 :]
            # IS-IS non-pseudonode
            if (igp == 1 or igp == 2) and dlength == 6:
                return (
                    cls(node_id=ISO.unpack_sysid(data[4 : 4 + 6]), dtype=dtype, packed=data[: 4 + dlength]),
                    data[4 + 6 :],
                )
            # IS-IS LAN pseudonode = ISO Node-ID + PSN
            # Unpack ISO address
            if (igp == 1 or igp == 2) and dlength == 7:
                iso_node = ISO.unpack_sysid(data[4 : 4 + 6])
                psn = unpack('!B', data[4 + 6 : 4 + 7])[0]
                return cls(node_id=iso_node, dtype=dtype, psn=psn, packed=data[: 4 + dlength]), data[4 + 7 :]
        elif dtype == 512 and dlength == 4:
            # ASN
            return (
                cls(node_id=unpack('!L', data[4 : 4 + dlength])[0], dtype=dtype, packed=data[: 4 + dlength]),
                data[4 + 4 :],
            )
        elif dtype == 513 and dlength == 4:
            # BGP-LS
            return (
                cls(node_id=unpack('!L', data[4 : 4 + dlength])[0], dtype=dtype, packed=data[: 4 + dlength]),
                data[4 + 4 :],
            )
        else:
            raise Notify(3, 5, 'could not decode Local Node descriptor')

    def json(self, compact=None):
        ospf = None
        designated = None
        psn = None
        router_id = None
        asn = None
        bgpls_id = None
        if self.dtype == 514:
            ospf = '"ospf-area-id": "%s"' % self.node_id
        if self.dr_id is not None:
            designated = '"designated-router-id": "%s"' % self.dr_id
        if self.psn is not None:
            psn = '"psn": "%s"' % self.psn
        if self.dtype == 515:
            router_id = '"router-id": "%s"' % self.node_id
        if self.dtype == 512:
            asn = '"autonomous-system": %d' % self.node_id
        if self.dtype == 513:
            bgpls_id = '"bgp-ls-identifier": "%d"' % self.node_id
        content = ', '.join(d for d in [ospf, designated, psn, router_id, asn, bgpls_id] if d)
        return content

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
        return self._packed
