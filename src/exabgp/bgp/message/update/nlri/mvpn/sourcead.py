from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.ip import IP, IPv4, IPv6
from exabgp.protocol.family import AFI
from exabgp.bgp.message import Action

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

# MVPN Source Active A-D Route length constants (RFC 6514)
MVPN_SOURCEAD_IPV4_LENGTH: int = 18  # 8 (RD) + 1 (source len) + 4 (IPv4) + 1 (group len) + 4 (IPv4)
MVPN_SOURCEAD_IPV6_LENGTH: int = 42  # 8 (RD) + 1 (source len) + 16 (IPv6) + 1 (group len) + 16 (IPv6)


@MVPN.register
class SourceAD(MVPN):
    CODE: ClassVar[int] = 5
    NAME: ClassVar[str] = 'Source Active A-D Route'
    SHORT_NAME: ClassVar[str] = 'SourceAD'

    def __init__(
        self,
        packed: bytes,
        afi: AFI,
        action: Action | None = None,
        addpath: int | None = None,
    ) -> None:
        MVPN.__init__(self, afi=afi, action=action, addpath=addpath)
        self._packed = packed

    @classmethod
    def make_sourcead(
        cls,
        rd: RouteDistinguisher,
        afi: AFI,
        source: IP,
        group: IP,
        action: Action | None = None,
        addpath: int | None = None,
    ) -> 'SourceAD':
        """Factory method to create SourceAD from semantic parameters."""
        packed = rd.pack_rd() + bytes([len(source) * 8]) + source.pack_ip() + bytes([len(group) * 8]) + group.pack_ip()
        return cls(packed, afi, action, addpath)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[:8])

    @property
    def source(self) -> IP:
        sourceiplen = int(self._packed[8] / 8)
        return IP.unpack_ip(self._packed[9 : 9 + sourceiplen])

    @property
    def group(self) -> IP:
        sourceiplen = int(self._packed[8] / 8)
        cursor = 9 + sourceiplen
        groupiplen = int(self._packed[cursor] / 8)
        return IP.unpack_ip(self._packed[cursor + 1 : cursor + 1 + groupiplen])

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, SourceAD)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.source == other.source
            and self.group == other.group
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __str__(self) -> str:
        return f'{self._prefix()}:{self.rd._str()}:{self.source!s}:{self.group!s}'

    def __hash__(self) -> int:
        return hash((self.rd, self.source, self.group))

    @classmethod
    def unpack_mvpn_route(cls, data: bytes, afi: AFI) -> SourceAD:
        datalen = len(data)
        if datalen not in (MVPN_SOURCEAD_IPV4_LENGTH, MVPN_SOURCEAD_IPV6_LENGTH):  # IPv4 or IPv6
            raise Notify(3, 5, f'Unsupported Source Active A-D route length ({datalen} bytes).')

        # Validate source IP length
        cursor = 8
        sourceiplen = int(data[cursor] / 8)
        cursor += 1
        if sourceiplen != IPv4.BYTES and sourceiplen != IPv6.BYTES:
            raise Notify(
                3,
                5,
                f'Unsupported Source Active A-D Route Multicast Source IP length ({sourceiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        cursor += sourceiplen

        # Validate group IP length
        groupiplen = int(data[cursor] / 8)
        if groupiplen != IPv4.BYTES and groupiplen != IPv6.BYTES:
            raise Notify(
                3,
                5,
                f'Unsupported Source Active A-D Route Multicast Group IP length ({groupiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )

        # Missing implementation of this check from RFC 6514:
        # Source Active A-D routes with a Multicast group belonging to the
        # Source Specific Multicast (SSM) range (as defined in [RFC4607], and
        # potentially extended locally on a router) MUST NOT be advertised by a
        # router and MUST be discarded if received.

        return cls(data, afi)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '"source": "{}", '.format(str(self.source))
        content += '"group": "{}"'.format(str(self.group))
        return '{{{}}}'.format(content)
