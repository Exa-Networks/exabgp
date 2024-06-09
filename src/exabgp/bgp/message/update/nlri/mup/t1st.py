"""
t1st.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI
from exabgp.protocol.family import Family

from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from struct import pack


# +-----------------------------------+
# |           RD  (8 octets)          |
# +-----------------------------------+
# |      Prefix Length (1 octet)      |
# +-----------------------------------+
# |         Prefix (variable)         |
# +-----------------------------------+
# | Architecture specific (variable)  |
# +-----------------------------------+

# 3gpp-5g Specific BGP Type 1 ST Route
#   +-----------------------------------+
#   |          TEID (4 octets)          |
#   +-----------------------------------+
#   |          QFI (1 octet)            |
#   +-----------------------------------+
#   | Endpoint Address Length (1 octet) |
#   +-----------------------------------+
#   |    Endpoint Address (variable)    |
#   +-----------------------------------+
#   |  Source Address Length (1 octet)  |
#   +-----------------------------------+
#   |     Source Address (variable)     |
#   +-----------------------------------+


@MUP.register
class Type1SessionTransformedRoute(MUP):
    ARCHTYPE = 1
    CODE = 3
    NAME = "Type1SessionTransformedRoute"
    SHORT_NAME = "T1ST"

    def __init__(
        self,
        rd,
        ipprefix_len,
        ipprefix,
        teid,
        qfi,
        endpoint_ip_len,
        endpoint_ip,
        afi,
        source_ip_len,
        source_ip,
        packed=None,
    ):
        MUP.__init__(self, afi)
        self.rd = rd
        self.ipprefix_len = ipprefix_len
        self.ipprefix = ipprefix
        self.teid = teid
        self.qfi = qfi
        self.endpoint_ip_len = endpoint_ip_len
        self.endpoint_ip = endpoint_ip
        self.source_ip_len = source_ip_len
        self.source_ip = source_ip
        self._pack(packed)

    def __eq__(self, other):
        return (
            isinstance(other, Type1SessionTransformedRoute)
            and self.ARCHTYPE == other.ARCHTYPE
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.ipprefix_len == other.ipprefix_len
            and self.ipprefix == other.ipprefix
            and self.teid == other.teid
            and self.qfi == other.qfi
            and self.endpoint_ip_len == other.endpoint_ip_len
            and self.endpoint_ip == other.endpoint_ip
            and self.source_ip_len == other.source_ip_len
            and self.source_ip == other.source_ip
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        s = "%s:%s:%s%s:%s:%s:%s%s" % (
            self._prefix(),
            self.rd._str(),
            self.ipprefix,
            "/%d" % self.ipprefix_len,
            self.teid,
            self.qfi,
            self.endpoint_ip,
            "/%d" % self.ipprefix_len,
        )

        if self.source_ip_len != 0 and self.source_ip != b'':
            s += ":%s/%d" % (self.source_ip, self.source_ip_len)

        return s

    def pack_index(self):
        # removed teid, qfi, endpointip
        packed = self.rd.pack() + pack('!B', self.ipprefix_len) + self.ipprefix.pack()
        return pack('!BHB', self.ARCHTYPE, self.CODE, len(packed)) + packed

    def index(self):
        return Family.index(self) + self.pack_index()

    def __hash__(self):
        return hash(
            (
                self.rd,
                self.ipprefix_len,
                self.ipprefix,
                self.teid,
                self.qfi,
                self.endpoint_ip_len,
                self.endpoint_ip,
                self.source_ip_len,
                self.source_ip,
            )
        )

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        offset = self.ipprefix_len // 8
        remainder = self.ipprefix_len % 8
        if remainder != 0:
            offset += 1

        ipprefix_packed = self.ipprefix.pack()

        # fmt: off
        self._packed = (
            self.rd.pack()
            + pack('!B',self.ipprefix_len)
            + ipprefix_packed[0: offset]
            + pack('!IB',self.teid, self.qfi)
            + pack('!B',self.endpoint_ip_len)
            + self.endpoint_ip.pack()
        )

        if self.source_ip_len != 0:
            self._packed += pack('!B', self.source_ip_len) + self.source_ip.pack()

        # fmt: on
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        datasize = len(data)
        rd = RouteDistinguisher.unpack(data[:8])
        ipprefix_len = data[8]
        ip_offset = ipprefix_len // 8
        ip_remainder = ipprefix_len % 8
        if ip_remainder != 0:
            ip_offset += 1

        ip = data[9 : 9 + ip_offset]
        ip_size = 4 if afi != AFI.ipv6 else 16
        ip_padding = ip_size - ip_offset
        if ip_padding != 0 and 0 < ip_padding:
            ip += bytes(ip_padding)

        size = ip_offset
        ipprefix = IP.unpack(ip)
        size += 9
        teid = int.from_bytes(data[size : size + 4], "big")
        size += 4
        qfi = data[size]
        size += 1
        endpoint_ip_len = data[size]
        size += 1

        if endpoint_ip_len in [32, 128]:
            ep_len = endpoint_ip_len // 8
            endpoint_ip = IP.unpack(data[size : size + ep_len])
            size += ep_len
        else:
            raise RuntimeError('mup t1st endpoint ip length is not 32bit or 128bit, unexpect len: %d' % endpoint_ip_len)

        source_ip_size = datasize - size

        source_ip_len = 0
        source_ip = b''

        if 0 < source_ip_size:
            source_ip_len = data[size]
            size += 1
            if source_ip_len in [32, 128]:
                sip_len = source_ip_len // 8
                source_ip = IP.unpack(data[size : size + sip_len])
                size += sip_len
            else:
                raise RuntimeError('mup t1st source ip length is not 32bit or 128bit, unexpect len: %d' % source_ip_len)

        return cls(rd, ipprefix_len, ipprefix, teid, qfi, endpoint_ip_len, endpoint_ip, afi, source_ip_len, source_ip)

    def json(self, compact=None):
        content = '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '"rd": "%s", ' % self.rd.json()
        content += '"ipprefix_len": %d, ' % self.ipprefix_len
        content += '"ipprefix": "%s", ' % str(self.ipprefix)
        content += '"teid": "%s", ' % str(self.teid)
        content += '"qfi": "%s", ' % str(self.qfi)
        content += '"endpoint_ip_len": %d, ' % self.endpoint_ip_len
        content += '"endpoint_ip": "%s"' % str(self.endpoint_ip)
        content += '"source_ip_len": %d, ' % self.source_ip_len
        content += '"source_ip": "%s"' % str(self.source_ip)
        return '{ %s }' % content
