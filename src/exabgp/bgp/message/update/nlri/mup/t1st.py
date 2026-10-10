"""t1st.py

Created by Takeru Hayasaka on 2023-01-21.
Copyright (c) 2023 BBSakura Networks Inc. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar, Self, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.mup.nlri import MUP
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

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


# draft-mpmz-bess-mup-safi-05 3.1.3.1, the lengths in bits an address field may have
T1ST_ADDRESS_BITS: tuple[int, int] = (32, 128)
T1ST_NO_SOURCE_BITS = 0
T1ST_KEY_OFFSET = 4  # the route key starts after arch(1) + code(2) + length(1)
T1ST_PREFIX_OFFSET = 13  # header(4) + RD(8) + Prefix Length(1)
T1ST_TEID_QFI_SIZE = 5  # TEID(4) + QFI(1)


def architecture_error(data: Buffer, start: int) -> tuple[str, int]:
    """What is malformed in the 3gpp-5g part of a Type 1 ST route, and where its source starts.

    `start` is the end of the prefix, which the caller has checked is inside `data`. The
    reason is '' for a well formed part; the offset is that of the Source Address Length,
    which is `len(data)` for a route of -02, written without one.
    """
    end = len(data)
    if start > end:
        raise RuntimeError('the route key is checked before the architecture part is read')
    if end < start + T1ST_TEID_QFI_SIZE + 1:
        return 'the 3gpp-5g part is too short for its TEID, QFI and Endpoint Address Length', end
    if not any(data[start : start + 4]):
        return 'the TEID is 0, which is malformed', end
    endpoint_bits = data[start + T1ST_TEID_QFI_SIZE]
    if endpoint_bits not in T1ST_ADDRESS_BITS:
        return f'the Endpoint Address Length is {endpoint_bits}, not 32 or 128', end
    source_at = start + T1ST_TEID_QFI_SIZE + 1 + endpoint_bits // 8
    if source_at == end:
        return '', source_at
    if source_at > end:
        return 'the Endpoint Address runs past the route', end
    source_bits = data[source_at]
    if source_bits != T1ST_NO_SOURCE_BITS and source_bits not in T1ST_ADDRESS_BITS:
        return f'the Source Address Length is {source_bits}, not 0, 32 or 128', end
    if end != source_at + 1 + source_bits // 8:
        return 'the 3gpp-5g part is not encoded as shown, its size does not match its lengths', end
    return '', source_at


def with_source_length(data: Buffer) -> bytes:
    """A route of -02 with no source, as -05 writes it: a Source Address Length of 0 added.

    Held this way, it compares, hashes and is sent again as the route a -05 peer writes.
    """
    length = data[3] + 1
    # architecture_error passed a route ending at its Endpoint Address: 64 octets at most
    if length > 0xFF:
        raise RuntimeError('a Type 1 ST route without a source is far shorter than 255 octets')
    return bytes(data[:3]) + bytes([length]) + bytes(data[4:]) + bytes([T1ST_NO_SOURCE_BITS])


def route_key(packed: Buffer, afi: AFI) -> bytes:
    """RD, Prefix Length and Prefix, the route key of 3.1.3, behind a header of its own size.

    The prefix is padded to the full address, as the index always was.
    """
    prefix_len = packed[12]
    octets = (prefix_len + 7) // 8
    size = 16 if afi == AFI.ipv6 else 4
    prefix = bytes(packed[T1ST_PREFIX_OFFSET : T1ST_PREFIX_OFFSET + octets]) + bytes(size - octets)
    key = bytes(packed[T1ST_KEY_OFFSET:T1ST_PREFIX_OFFSET]) + prefix
    return pack('!BHB', packed[0], int.from_bytes(packed[1:3], 'big'), len(key)) + key


class Type1SessionTransformedRoute(MUP):
    NAME: ClassVar[str] = 'Type1SessionTransformedRoute'
    SHORT_NAME: ClassVar[str] = 'T1ST'

    # Wire format offsets (after 4-byte header: arch(1) + code(2) + length(1))
    HEADER_SIZE: ClassVar[int] = 4
    RD_OFFSET: ClassVar[int] = 4  # Bytes 4-11: RD (8 bytes)
    PREFIX_LEN_OFFSET: ClassVar[int] = 12  # Byte 12: prefix length
    PREFIX_OFFSET: ClassVar[int] = 13  # Bytes 13+: prefix (variable)

    def _fresh(self) -> Self:
        return type(self)(self._packed, self.afi)

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create T1ST with complete wire format.

        Args:
            packed: Complete wire format including 4-byte header
        """
        MUP.__init__(self, afi)
        self._packed: Buffer = packed

    @classmethod
    def make_t1st(
        cls,
        rd: RouteDistinguisher,
        prefix_ip_len: int,
        prefix_ip: IP,
        teid: int,
        qfi: int,
        endpoint_ip_len: int,
        endpoint_ip: IP,
        source_ip_len: int,
        source_ip: IP | bytes,
        afi: AFI,
    ) -> 'Type1SessionTransformedRoute':
        """Factory method to create T1ST from semantic parameters."""
        # draft-mpmz-bess-mup-safi-05 3.1.1 and 3.1.3: the configuration refuses anything else
        address_bits = 32 if afi == AFI.ipv4 else 128
        assert len(prefix_ip.pack_ip()) * 8 == address_bits, 'the prefix is of the family of the route'
        # not an assert: the length is written to the wire, so -O must not let a wrong one through
        if not 0 <= prefix_ip_len <= address_bits:
            raise RuntimeError(f'a prefix length of {prefix_ip_len} is longer than its address')
        offset = prefix_ip_len // 8
        remainder = prefix_ip_len % 8
        if remainder != 0:
            offset += 1

        prefix_ip_packed = prefix_ip.pack_ip()
        payload = (
            bytes(rd.pack_rd())
            + pack('!B', prefix_ip_len)
            + prefix_ip_packed[0:offset]
            + pack('!IB', teid, qfi)
            + pack('!B', endpoint_ip_len)
            + endpoint_ip.pack_ip()
        )

        # draft-mpmz-bess-mup-safi-05 3.1.3.1: the Source Address Length is always sent, 0
        # when there is no source.  -02 left the octet out, which a -05 peer reads as an
        # architecture part not "encoded as shown" and withdraws.
        source_ip_packed = b''
        if source_ip_len != 0:
            source_ip_packed = bytes(source_ip.pack_ip()) if isinstance(source_ip, IP) else source_ip
        payload += pack('!B', source_ip_len) + source_ip_packed

        # Include 4-byte header: arch(1) + code(2) + length(1) + payload
        packed = pack('!BHB', cls.ARCHTYPE, cls.CODE, len(payload)) + payload
        return cls(packed, afi)

    @property
    def rd(self) -> RouteDistinguisher:
        # Offset by 4-byte header: RD at bytes 4-11
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[4:12])

    @property
    def prefix_ip_len(self) -> int:
        # Offset by 4-byte header: prefix_len at byte 12
        return self._packed[12]

    @property
    def prefix_ip(self) -> IP:
        ip_offset = self.prefix_ip_len // 8
        ip_remainder = self.prefix_ip_len % 8
        if ip_remainder != 0:
            ip_offset += 1

        # Offset by 4-byte header: prefix at bytes 13+
        ip = self._packed[13 : 13 + ip_offset]
        ip_size = 4 if self.afi != AFI.ipv6 else 16
        ip_padding = ip_size - ip_offset
        if ip_padding > 0:
            ip = bytes(ip) + bytes(ip_padding)
        return IP.create_ip(ip)

    def _get_teid_qfi_offset(self) -> int:
        """Calculate offset to TEID field (includes 4-byte header)."""
        ip_offset = self.prefix_ip_len // 8
        ip_remainder = self.prefix_ip_len % 8
        if ip_remainder != 0:
            ip_offset += 1
        # 4 (header) + 8 (RD) + 1 (prefix_len) + ip_offset
        return 13 + ip_offset

    @property
    def teid(self) -> int:
        offset = self._get_teid_qfi_offset()
        return int.from_bytes(self._packed[offset : offset + 4], 'big')

    @property
    def qfi(self) -> int:
        offset = self._get_teid_qfi_offset() + 4
        return self._packed[offset]

    @property
    def endpoint_ip_len(self) -> int:
        offset = self._get_teid_qfi_offset() + 5
        return self._packed[offset]

    @property
    def endpoint_ip(self) -> IP:
        offset = self._get_teid_qfi_offset() + 6
        ep_len = self.endpoint_ip_len // 8
        return IP.create_ip(self._packed[offset : offset + ep_len])

    @property
    def source_ip_len(self) -> int:
        # unpack_nlri and make_t1st both write the octet, 0 when there is no source
        offset = self._get_teid_qfi_offset() + 6 + self.endpoint_ip_len // 8
        return self._packed[offset]

    @property
    def source_ip(self) -> IP | bytes:
        offset = self._get_teid_qfi_offset() + 6 + self.endpoint_ip_len // 8
        sip_len = self._packed[offset] // 8
        if not sip_len:
            return b''
        return IP.create_ip(self._packed[offset + 1 : offset + 1 + sip_len])

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Type1SessionTransformedRoute)
            # and self.ARCHTYPE == other.ARCHTYPE
            # and self.CODE == other.CODE
            and self.rd == other.rd
            and self.prefix_ip_len == other.prefix_ip_len
            and self.prefix_ip == other.prefix_ip
            and self.teid == other.teid
            and self.qfi == other.qfi
            and self.endpoint_ip_len == other.endpoint_ip_len
            and self.endpoint_ip == other.endpoint_ip
            and self.source_ip_len == other.source_ip_len
            and self.source_ip == other.source_ip
        )

    def __ne__(self, other: object) -> bool:
        # `not NotImplemented` is a DeprecationWarning today and a TypeError from 3.14
        # the operator, not a call to __eq__: it answers NotImplemented the way Python does,
        # where a compiled bool-typed local would refuse it
        return not self == other

    def __str__(self) -> str:
        s = '{}:{}:{}{}:{}:{}:{}{}'.format(
            self._prefix(),
            self.rd._str(),
            self.prefix_ip,
            '/%d' % self.prefix_ip_len,
            self.teid,
            self.qfi,
            self.endpoint_ip,
            '/%d' % self.endpoint_ip_len,
        )

        if self.source_ip_len != 0 and isinstance(self.source_ip, IP):
            s += ':%s/%d' % (self.source_ip, self.source_ip_len)

        return s

    def pack_index(self) -> bytes:
        # T1ST index excludes teid, qfi, endpoint for RIB uniqueness
        return route_key(self._packed, self.afi)

    def index(self) -> bytes:
        # T1ST uses custom index (excludes teid, qfi, endpoint)
        return bytes(Family.index(self)) + self.pack_index()

    def __hash__(self) -> int:
        # Direct _packed hash - include afi since MUP supports both IPv4 and IPv6
        return hash((self.afi, self._packed))

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: bool, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # Parent provides complete wire format including 4-byte header
        # Offsets: header(0-3), RD(4-11), prefix_len(12), prefix(13+)
        cls.check_length(data, T1ST_PREFIX_OFFSET)
        prefix_ip_len = data[12]
        max_bits = 32 if afi != AFI.ipv6 else 128
        if prefix_ip_len > max_bits:
            raise Notify(
                3,
                10,
                'mup t1st prefix length is %d bits, more than the %d of an %s address' % (prefix_ip_len, max_bits, afi),
            )
        key_end = T1ST_PREFIX_OFFSET + (prefix_ip_len + 7) // 8
        cls.check_length(data, key_end)

        # draft-mpmz-bess-mup-safi-05 3.1.3.1: everything after the prefix is the 3gpp-5g
        # part, and each of its rules is "Treat-as-withdraw".  The key, RD and prefix, is
        # intact here, so the route the peer announced before is withdrawn by it rather
        # than left in place, which is what skipping the NLRI did.
        reason, source_at = architecture_error(data, key_end)
        if reason:
            return MalformedType1SessionTransformedRoute(data, afi, reason), b''
        if source_at == len(data):
            data = with_source_length(data)
        return cls(data, afi), b''

    def json(self, announced: bool = True, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"prefix_ip_len": %d, ' % self.prefix_ip_len
        content += '"prefix_ip": "{}", '.format(str(self.prefix_ip))
        content += '"teid": "{}", '.format(str(self.teid))
        content += '"qfi": "{}", '.format(str(self.qfi))
        content += self.rd.json() + ', '
        content += '"endpoint_ip_len": %d, ' % self.endpoint_ip_len
        content += '"endpoint_ip": "{}", '.format(str(self.endpoint_ip))
        content += '"source_ip_len": %d, ' % self.source_ip_len
        # without a source the field is empty, not the repr of the empty bytes it is read as
        content += '"source_ip": "{}", '.format(str(self.source_ip) if self.source_ip_len else '')
        content += '"raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)


MUP.register_mup_route(archtype=1, code=3)(Type1SessionTransformedRoute)


class MalformedType1SessionTransformedRoute(MUP):
    """A Type 1 ST route whose key is intact and whose 3gpp-5g part is malformed.

    draft-mpmz-bess-mup-safi-05 3.1.3.1 makes such a route "Treat-as-withdraw", so it
    is only ever a withdrawal: withdrawn_on_receipt() moves it there from MP_REACH_NLRI.
    It keeps the octets the peer sent and reads nothing past the prefix, so no accessor
    can trip on the part which was malformed. Its index is the well formed route's.
    """

    __slots__ = ('_reason',)

    NAME: ClassVar[str] = Type1SessionTransformedRoute.NAME
    SHORT_NAME: ClassVar[str] = Type1SessionTransformedRoute.SHORT_NAME
    ARCHTYPE: ClassVar[int] = Type1SessionTransformedRoute.ARCHTYPE
    CODE: ClassVar[int] = Type1SessionTransformedRoute.CODE

    def __init__(self, packed: Buffer, afi: AFI, reason: str) -> None:
        MUP.__init__(self, afi)
        # unpack_nlri checked the route key, the only part this class reads, before building it
        self._packed = packed
        self._reason = reason

    def _fresh(self) -> Self:
        return type(self)(self._packed, self.afi, self._reason)

    def withdrawn_on_receipt(self) -> str | None:
        return f'Type 1 ST route: {self._reason} (draft-mpmz-bess-mup-safi-05 3.1.3.1)'

    @property
    def rd(self) -> RouteDistinguisher:
        return RouteDistinguisher.unpack_routedistinguisher(self._packed[4:12])

    @property
    def prefix_ip_len(self) -> int:
        return self._packed[12]

    @property
    def prefix_ip(self) -> IP:
        return IP.create_ip(route_key(self._packed, self.afi)[T1ST_PREFIX_OFFSET:])

    def index(self) -> bytes:
        return bytes(Family.index(self)) + route_key(self._packed, self.afi)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, MalformedType1SessionTransformedRoute) and self.index() == other.index()

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __hash__(self) -> int:
        return hash(self.index())

    def __str__(self) -> str:
        return '{}:{}:{}/{}'.format(self._prefix(), self.rd._str(), self.prefix_ip, self.prefix_ip_len)

    def json(self, announced: bool = True, compact: bool | None = None) -> str:
        content = '"name": "{}", '.format(self.NAME)
        content += '"arch": %d, ' % self.ARCHTYPE
        content += '"code": %d, ' % self.CODE
        content += '"prefix_ip_len": %d, ' % self.prefix_ip_len
        content += '"prefix_ip": "{}", '.format(str(self.prefix_ip))
        content += self.rd.json() + ', '
        content += '"raw": "{}"'.format(self._raw())
        return '{{ {} }}'.format(content)
