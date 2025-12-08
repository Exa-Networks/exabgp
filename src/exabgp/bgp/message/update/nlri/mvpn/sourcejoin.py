from __future__ import annotations

from struct import pack
from typing import ClassVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP, IPv4, IPv6
from exabgp.util.types import Buffer

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


@MVPN.register_mvpn
class SourceJoin(MVPN):
    CODE: ClassVar[int] = 7
    NAME: ClassVar[str] = 'C-Multicast Source Tree Join route'
    SHORT_NAME: ClassVar[str] = 'Source-Join'

    # Wire format offsets (after 2-byte type+length header)
    HEADER_SIZE = 2  # type(1) + length(1)

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create SourceJoin from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
            afi: Address Family Identifier
        """
        MVPN.__init__(self, afi=afi)
        self._packed = bytes(packed)  # Ensure bytes for storage

    @classmethod
    def make_sourcejoin(
        cls,
        rd: RouteDistinguisher,
        afi: AFI,
        source: IP,
        group: IP,
        source_as: int,
    ) -> 'SourceJoin':
        """Factory method to create SourceJoin from semantic parameters."""
        payload = (
            bytes(rd.pack_rd())
            + pack('!I', source_as)
            + bytes([len(source) * 8])
            + source.pack_ip()
            + bytes([len(group) * 8])
            + group.pack_ip()
        )
        # Prepend type + length header
        packed = bytes([cls.CODE, len(payload)]) + payload
        return cls(packed, afi)

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[2:10])

    @property
    def source_as(self) -> int:
        return int.from_bytes(self._packed[10:14], 'big')

    @property
    def source(self) -> IP:
        cursor = 14  # 2 (header) + 8 (RD) + 4 (source_as)
        sourceiplen = int(self._packed[cursor] / 8)
        return IP.unpack_ip(self._packed[cursor + 1 : cursor + 1 + sourceiplen])

    @property
    def group(self) -> IP:
        cursor = 14  # 2 (header) + 8 (RD) + 4 (source_as)
        sourceiplen = int(self._packed[cursor] / 8)
        cursor += 1 + sourceiplen
        groupiplen = int(self._packed[cursor] / 8)
        return IP.unpack_ip(self._packed[cursor + 1 : cursor + 1 + groupiplen])

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
        # Direct _packed hash - include afi since MVPN supports both IPv4 and IPv6
        return hash((self.afi, self._packed))

    @classmethod
    def unpack_mvpn(cls, packed: bytes, afi: AFI) -> 'MVPN':
        """Unpack SourceJoin from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
            afi: Address Family Identifier
        """
        # packed includes header, payload starts at offset 2
        datalen = len(packed) - cls.HEADER_SIZE
        if datalen not in (MVPN_SOURCEJOIN_IPV4_LENGTH, MVPN_SOURCEJOIN_IPV6_LENGTH):  # IPv4 or IPv6
            raise Notify(3, 5, f'Invalid C-Multicast Route length ({datalen} bytes).')

        # Validate source IP length (offset +2 for header)
        cursor = 14  # 2 (header) + 8 (RD) + 4 (Source AS)
        sourceiplen = int(packed[cursor] / 8)
        cursor += 1
        if sourceiplen != IPv4.BYTES and sourceiplen != IPv6.BYTES:
            raise Notify(
                3,
                5,
                f'Invalid C-Multicast Route length ({sourceiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        cursor += sourceiplen

        # Validate group IP length
        groupiplen = int(packed[cursor] / 8)
        if groupiplen != IPv4.BYTES and groupiplen != IPv6.BYTES:
            raise Notify(
                3,
                5,
                f'Invalid C-Multicast Route length ({groupiplen * 8} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )

        return cls(packed, afi)

    def json(self, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '"source-as": "{}", '.format(str(self.source_as))
        content += '"source": "{}", '.format(str(self.source))
        content += '"group": "{}"'.format(str(self.group))
        return '{{{}}}'.format(content)
