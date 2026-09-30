from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN, check_source_and_group
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IP, IPv4, IPv6
from exabgp.util.types import Buffer

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

# RFC 4607 1: the Source Specific Multicast ranges, 232.0.0.0/8 for IPv4 and FF3x::/32 for
# IPv6, where x is any scope. The IPv6 range is the first octet FF, a flags nibble of 3,
# any scope nibble, and a zero second sixteen bits.
SSM_IPV4_FIRST_OCTET: int = 232
SSM_IPV6_FIRST_OCTET: int = 0xFF
SSM_IPV6_FLAGS_NIBBLE: int = 0x3
SSM_IPV6_ZERO_BYTES: bytes = bytes(2)


def is_ssm_group(group: IP) -> bool:
    """Whether a multicast group is in the RFC 4607 Source Specific Multicast range."""
    packed = group.pack_ip()
    if len(packed) == IPv4.BYTES:
        return packed[0] == SSM_IPV4_FIRST_OCTET
    if len(packed) == IPv6.BYTES:
        return (
            packed[0] == SSM_IPV6_FIRST_OCTET
            and packed[1] >> 4 == SSM_IPV6_FLAGS_NIBBLE
            and packed[2:4] == SSM_IPV6_ZERO_BYTES
        )
    return False


class SourceAD(MVPN):
    NAME: ClassVar[str] = 'Source Active A-D Route'
    SHORT_NAME: ClassVar[str] = 'SourceAD'

    # Wire format offsets (after 2-byte type+length header)
    HEADER_SIZE: ClassVar[int] = 2  # type(1) + length(1)

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create SourceAD from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
            afi: Address Family Identifier
        """
        MVPN.__init__(self, afi=afi)
        self._packed = bytes(packed)  # Ensure bytes for storage

    @classmethod
    def make_sourcead(
        cls,
        rd: RouteDistinguisher,
        afi: AFI,
        source: IP,
        group: IP,
    ) -> 'SourceAD':
        """Factory method to create SourceAD from semantic parameters."""
        payload = (
            bytes(rd.pack_rd())
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
    def source(self) -> IP:
        sourceiplen = self._packed[10] // 8
        return IP.create_ip(self._packed[11 : 11 + sourceiplen])

    @property
    def group(self) -> IP:
        sourceiplen = self._packed[10] // 8
        cursor = 11 + sourceiplen
        groupiplen = self._packed[cursor] // 8
        return IP.create_ip(self._packed[cursor + 1 : cursor + 1 + groupiplen])

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, SourceAD)
            and self.CODE == other.CODE
            and self.rd == other.rd
            and self.source == other.source
            and self.group == other.group
        )

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __str__(self) -> str:
        return f'{self._prefix()}:{self.rd._str()}:{self.source!s}:{self.group!s}'

    def __hash__(self) -> int:
        # Direct _packed hash - include afi since MVPN supports both IPv4 and IPv6
        return hash((self.afi, self._packed))

    @classmethod
    def unpack_mvpn(cls, packed: Buffer, afi: AFI) -> 'MVPN':
        """Unpack SourceAD from complete wire format bytes.

        Args:
            packed: Complete wire format (type + length + payload)
            afi: Address Family Identifier
        """
        # packed includes header, payload starts at offset 2
        datalen = len(packed) - cls.HEADER_SIZE
        if datalen not in (MVPN_SOURCEAD_IPV4_LENGTH, MVPN_SOURCEAD_IPV6_LENGTH):  # IPv4 or IPv6
            raise Notify(3, 5, f'Unsupported Source Active A-D route length ({datalen} bytes).')

        # The Multicast Source Length octet sits after the header and the RD, and the two
        # address length octets are what the accessors below trust to slice the addresses.
        check_source_and_group(packed, 10, 'Source Active A-D Route')

        # The SSM range of RFC 6514 4.5 is not a decoding error: the route is well formed
        # and decodes, and MPRNLRI drops it on receipt through discard_on_receipt().
        return cls(packed, afi)

    def discard_on_receipt(self) -> str | None:
        # RFC 6514 4.5: a Source Active A-D route whose Multicast Group is in the SSM range
        # MUST be discarded if received. The local extension of the range the sentence
        # allows is not configurable, so the range is exactly RFC 4607's.
        if is_ssm_group(self.group):
            return f'Source Active A-D route for SSM group {self.group} (RFC 6514 4.5)'
        return None

    def json(self, announced: bool = True, compact: bool | None = None) -> str:
        content = ' "code": %d, ' % self.CODE
        content += '"parsed": true, '
        content += '"raw": "{}", '.format(self._raw())
        content += '"name": "{}", '.format(self.NAME)
        content += '{}, '.format(self.rd.json())
        content += '"source": "{}", '.format(str(self.source))
        content += '"group": "{}"'.format(str(self.group))
        return '{{{}}}'.format(content)


MVPN.register_mvpn(code=5)(SourceAD)
