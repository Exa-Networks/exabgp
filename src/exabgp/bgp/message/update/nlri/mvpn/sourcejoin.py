from __future__ import annotations

from struct import pack
from typing import ClassVar, Optional

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.ip import IP, IPv4, IPv6
from exabgp.protocol.family import AFI
from exabgp.bgp.message import Action

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

# MVPN Source Join Route length constants (RFC 6514)
MVPN_SOURCEJOIN_IPV4_LENGTH: int = 22  # 8 (RD) + 4 (Source AS) + 1 (source len) + 4 (IPv4) + 1 (group len) + 4 (IPv4)
MVPN_SOURCEJOIN_IPV6_LENGTH: int = 46  # 8 (RD) + 4 (Source AS) + 1 (source len) + 16 (IPv6) + 1 (group len) + 16 (IPv6)


@MVPN.register
class SourceJoin(MVPN):
    CODE: ClassVar[int] = 7
    NAME: ClassVar[str] = 'C-Multicast Source Tree Join route'
    SHORT_NAME: ClassVar[str] = 'Source-Join'

    def __init__(
        self,
        rd: RouteDistinguisher,
        afi: AFI,
        source: IP,
        group: IP,
        source_as: int,
        packed: Optional[bytes] = None,
        action: Optional[Action] = None,
        addpath: Optional[int] = None,
    ) -> None:
        MVPN.__init__(self, afi=afi, action=action, addpath=addpath)  # type: ignore[arg-type]
        self.rd: RouteDistinguisher = rd
        self.group: IP = group
        self.source: IP = source
        self.source_as: int = source_as
        self._pack(packed)

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, SourceJoin)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.source == other.source
            and self.group == other.group
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return f'{self._prefix()}:{self.rd._str()}:{self.source_as!s}:{self.source!s}:{self.group!s}'

    def __hash__(self) -> int:
        return hash((self.rd, self.source, self.group, self.source_as))

    def _pack(self, packed: Optional[bytes] = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed
        self._packed = (
            self.rd.pack_rd()
            + pack('!I', self.source_as)
            + bytes([len(self.source) * 8])  # type: ignore[arg-type]
            + self.source.pack()
            + bytes([len(self.group) * 8])  # type: ignore[arg-type]
            + self.group.pack()
        )
        return self._packed

    @classmethod
    def unpack_mvpn_route(cls, data: bytes, afi: AFI) -> SourceJoin:
        datalen = len(data)
        if datalen not in (MVPN_SOURCEJOIN_IPV4_LENGTH, MVPN_SOURCEJOIN_IPV6_LENGTH):  # IPv4 or IPv6
            raise Notify(3, 5, f'Invalid C-Multicast Route length ({datalen} bytes).')
        cursor = 0
        rd = RouteDistinguisher.unpack_routedistinguisher(data[cursor:8])
        cursor += 8
        source_as = int.from_bytes(data[cursor : cursor + 4], 'big')
        cursor += 4
        sourceiplen = int(data[cursor] / 8)
        cursor += 1
        if sourceiplen != IPv4.BYTES and sourceiplen != IPv6.BYTES:
            raise Notify(
                3,
                5,
                f'Invalid C-Multicast Route length ({sourceiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        sourceip = IP.unpack_ip(data[cursor : cursor + sourceiplen])
        cursor += sourceiplen
        groupiplen = int(data[cursor] / 8)
        cursor += 1
        if groupiplen != IPv4.BYTES and groupiplen != IPv6.BYTES:
            raise Notify(
                3,
                5,
                f'Invalid C-Multicast Route length ({groupiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        groupip = IP.unpack_ip(data[cursor : cursor + groupiplen])
        return cls(afi=afi, rd=rd, source=sourceip, group=groupip, source_as=source_as, packed=data)

    def json(self, compact: Optional[bool] = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '"source-as": "{}", '.format(str(self.source_as))
        content += '"source": "{}", '.format(str(self.source))
        content += '"group": "{}"'.format(str(self.group))
        return '{{{}}}'.format(content)
