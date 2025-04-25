from __future__ import annotations

from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.bgp.message.notification import Notify
from exabgp.protocol.ip import IP
from struct import pack

# +-----------------------------------+
# |      RD   (8 octets)              |
# +-----------------------------------+
# |    Source AS (4 octets)           |
# +-----------------------------------+
# | Multicast Source Length (1 octet) |
# +-----------------------------------+
# |   Multicast Source (variable)     |
# +-----------------------------------+
# |  Multicast Group Length (1 octet) |
# +-----------------------------------+
# |  Multicast Group   (variable)     |
# +-----------------------------------+


@MVPN.register
class SharedJoin(MVPN):
    CODE = 6
    NAME = 'C-Multicast Shared Tree Join route'
    SHORT_NAME = 'Shared-Join'

    def __init__(self, rd, afi, source, group, source_as, packed=None, action=None, addpath=None):
        MVPN.__init__(self, afi=afi, action=action, addpath=addpath)
        self.rd = rd
        self.group = group
        self.source = source
        self.source_as = source_as
        self._pack(packed)

    def __eq__(self, other):
        return (
            isinstance(other, SharedJoin)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.source == other.source
            and self.group == other.group
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __str__(self):
        return f'{self._prefix()}:{self.rd._str()}:{str(self.source_as)}:{str(self.source)}:{str(self.group)}'

    def __hash__(self):
        return hash((self.rd, self.source, self.group, self.source_as))

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed
        self._packed = (
            self.rd.pack()
            + pack('!I', self.source_as)
            + bytes([len(self.source) * 8])
            + self.source.pack()
            + bytes([len(self.group) * 8])
            + self.group.pack()
        )
        return self._packed

    @classmethod
    def unpack(cls, data, afi):
        datalen = len(data)
        if datalen not in (22, 46):  # IPv4 or IPv6
            raise Notify(3, 5, f'Invalid C-Multicast Route length ({datalen} bytes).')
        cursor = 0
        rd = RouteDistinguisher.unpack(data[cursor:8])
        cursor += 8
        source_as = int.from_bytes(data[cursor : cursor + 4], 'big')
        cursor += 4
        sourceiplen = int(data[cursor] / 8)
        cursor += 1
        if sourceiplen != 4 and sourceiplen != 16:
            raise Notify(
                3,
                5,
                f'Invalid C-Multicast Route length ({sourceiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        sourceip = IP.unpack(data[cursor : cursor + sourceiplen])
        cursor += sourceiplen
        groupiplen = int(data[cursor] / 8)
        cursor += 1
        if groupiplen != 4 and groupiplen != 16:
            raise Notify(
                3,
                5,
                f'Invalid C-Multicast Route length ({groupiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        groupip = IP.unpack(data[cursor : cursor + groupiplen])
        return cls(afi=afi, rd=rd, source=sourceip, group=groupip, source_as=source_as, packed=data)

    def json(self, compact=None):
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "%s", ' % self._raw()
        content += '"name": "%s", ' % self.NAME
        content += '%s, ' % self.rd.json()
        content += '"source-as": "%s", ' % str(self.source_as)
        content += '"source": "%s", ' % str(self.source)
        content += '"group": "%s"' % str(self.group)
        return '{%s}' % content
