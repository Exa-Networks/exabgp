from __future__ import annotations

from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.bgp.message.notification import Notify
from exabgp.protocol.ip import IP

# +-----------------------------------+
# |      RD   (8 octets)              |
# +-----------------------------------+
# | Multicast Source Length (1 octet) |
# +-----------------------------------+
# |   Multicast Source (variable)     |
# +-----------------------------------+
# |  Multicast Group Length (1 octet) |
# +-----------------------------------+
# |  Multicast Group (variable)       |
# +-----------------------------------+


@MVPN.register
class SourceAD(MVPN):
    CODE = 5
    NAME = 'Source Active A-D Route'
    SHORT_NAME = 'SourceAD'

    def __init__(self, rd, afi, source, group, packed=None, action=None, addpath=None):
        MVPN.__init__(self, afi=afi, action=action, addpath=addpath)
        self.rd = rd
        self.source = source
        self.group = group
        self._pack(packed)

    def __eq__(self, other):
        return (
            isinstance(other, SourceAD)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.source == other.source
            and self.group == other.group
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return f'{self._prefix()}:{self.rd._str()}:{self.source!s}:{self.group!s}'

    def __hash__(self):
        return hash((self.rd, self.source, self.group))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed
        self._packed = (
            self.rd.pack()
            + bytes([len(self.source) * 8])
            + self.source.pack()
            + bytes([len(self.group) * 8])
            + self.group.pack()
        )
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        datalen = len(data)
        if datalen not in (18, 42):  # IPv4 or IPv6
            raise Notify(3, 5, f'Unsupported Source Active A-D route length ({datalen} bytes).')
        cursor = 0
        rd = RouteDistinguisher.unpack(data[cursor:8])
        cursor += 8
        sourceiplen = int(data[cursor] / 8)
        cursor += 1
        if sourceiplen != 4 and sourceiplen != 16:
            raise Notify(
                3,
                5,
                f'Unsupported Source Active A-D Route Multicast Source IP length ({sourceiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        sourceip = IP.unpack(data[cursor : cursor + sourceiplen])
        cursor += sourceiplen
        groupiplen = int(data[cursor] / 8)
        cursor += 1
        if groupiplen != 4 and groupiplen != 16:
            raise Notify(
                3,
                5,
                f'Unsupported Source Active A-D Route Multicast Group IP length ({groupiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        groupip = IP.unpack(data[cursor : cursor + groupiplen])

        # Missing implementation of this check from RFC 6514:
        # Source Active A-D routes with a Multicast group belonging to the
        # Source Specific Multicast (SSM) range (as defined in [RFC4607], and
        # potentially extended locally on a router) MUST NOT be advertised by a
        # router and MUST be discarded if received.

        return cls(afi=afi, rd=rd, source=sourceip, group=groupip, packed=data)

    def json(self, compact=None):
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '%s, ' % self.rd.json()
        content += '"source": "%s", ' % str(self.source)
        content += '"group": "%s"' % str(self.group)
        return '{%s}' % content
