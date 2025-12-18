"""nlri.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Any, ClassVar, Type, TypeVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI, Family

# https://tools.ietf.org/html/rfc7752#section-3.2
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |            NLRI Type          |     Total NLRI Length         |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                                                               |
#     //                  Link-State NLRI (variable)                 //
#     |                                                               |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |            NLRI Type          |     Total NLRI Length         |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                                                               |
#     +                       Route Distinguisher                     +
#     |                                                               |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |                                                               |
#     //                  Link-State NLRI (variable)                 //
#     |                                                               |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                   +------+---------------------------+
#                   | Type | NLRI Type                 |
#                   +------+---------------------------+
#                   |  1   | Node NLRI                 |
#                   |  2   | Link NLRI                 |
#                   |  3   | IPv4 Topology Prefix NLRI |
#                   |  4   | IPv6 Topology Prefix NLRI |
#                   +------+---------------------------+
# ==================================================================== BGP LINK_STATE
#            +-------------+----------------------------------+
#            | Protocol-ID | NLRI information source protocol |
#            +-------------+----------------------------------+
#            |      1      | IS-IS Level 1                    |
#            |      2      | IS-IS Level 2                    |
#            |      3      | OSPFv2                           |
#            |      4      | Direct                           |
#            |      5      | Static configuration             |
#            |      6      | OSPFv3                           |
#            +-------------+----------------------------------+
# ===================================================================== PROTO_ID

PROTO_CODES: dict[int, str] = {
    1: 'isis_l1',
    2: 'isis_l2',
    3: 'ospf_v2',
    4: 'direct',
    5: 'static',
    6: 'ospfv3',
    # not RFC/draft defined
    227: 'freertr',
}

T = TypeVar('T', bound='BGPLS')


@NLRI.register(AFI.bgpls, SAFI.bgp_ls)
@NLRI.register(AFI.bgpls, SAFI.bgp_ls_vpn)
class BGPLS(NLRI):
    # BGPLS has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    registered_bgpls: ClassVar[dict[int, Type[BGPLS]]] = dict()

    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    # Type declaration: subclasses may pass packed data or leave as empty
    _packed: Buffer

    def __init__(self, addpath: PathInfo | None = None) -> None:
        NLRI.__init__(self, AFI.bgpls, SAFI.bgp_ls)
        self._packed = b''

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for BGP-LS but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.bgpls, self.safi)
        # Wire format: [type(2)][length(2)][payload] - _packed includes header
        return self._packed

    def index(self) -> bytes:
        # Wire format: [family][type(2)][length(2)][payload] - _packed includes header
        return bytes(Family.index(self)) + self._packed

    @classmethod
    def unpack_bgpls_nlri(cls, data: Buffer, rd: 'RouteDistinguisher') -> 'BGPLS':
        """Unpack NLRI-type-specific data. Override in subclasses."""
        raise NotImplementedError(f'{cls.__name__} must implement unpack_bgpls_nlri')

    def __len__(self) -> int:
        # _packed includes 4-byte header
        return len(self._packed)

    def __hash__(self) -> int:
        # _packed includes header
        return hash((self.afi, self.safi, self.CODE, self._packed))

    def __str__(self) -> str:
        # _packed includes 4-byte header, payload starts at offset 4
        payload = self._packed[4:] if len(self._packed) > 4 else b''
        return 'bgp-ls:{}:{}'.format(
            self.registered_bgpls.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in payload),
        )

    def __copy__(self) -> 'BGPLS':
        new = self.__class__.__new__(self.__class__)
        # NLRI slots (includes Family slots: _afi, _safi)
        self._copy_nlri_slots(new)
        # BGPLS has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'BGPLS':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # NLRI slots (includes Family slots: _afi, _safi)
        self._deepcopy_nlri_slots(new, memo)
        # BGPLS has empty __slots__ - nothing else to copy
        return new

    @classmethod
    def register_bgpls(cls, klass: Type[BGPLS]) -> Type[BGPLS]:
        if klass.CODE in cls.registered_bgpls:
            raise RuntimeError('only one BGP LINK_STATE registration allowed')
        cls.registered_bgpls[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # BGP-LS NLRI header: type(2) + length(2) = 4 bytes minimum
        if len(data) < 4:
            raise Notify(3, 10, f'BGP-LS NLRI too short: need at least 4 bytes, got {len(data)}')
        code, length = unpack('!HH', bytes(data[:4]))

        # For VPN, need 8 more bytes for RD
        if safi == SAFI.bgp_ls_vpn:
            if len(data) < 12:
                raise Notify(3, 10, f'BGP-LS VPN NLRI too short: need at least 12 bytes, got {len(data)}')

        if len(data) < length + 4:
            raise Notify(3, 10, f'BGP-LS NLRI truncated: need {length + 4} bytes, got {len(data)}')

        if code in cls.registered_bgpls:
            if safi == SAFI.bgp_ls_vpn:
                # Extract Route Distinguisher (between header and payload)
                rd: RouteDistinguisher = RouteDistinguisher.unpack_routedistinguisher(bytes(data[4:12]))
                # Reconstruct wire format without RD: [type(2)][length(2)][payload]
                # Original length includes RD (8 bytes), subtract for payload-only length
                payload_length = length - 8
                wire_format = pack('!HH', code, payload_length) + bytes(data[12 : length + 4])
                klass = cls.registered_bgpls[code].unpack_bgpls_nlri(wire_format, rd)
            else:
                rd = RouteDistinguisher.NORD
                # Complete wire format including 4-byte header
                wire_format = bytes(data[0 : length + 4])
                klass = cls.registered_bgpls[code].unpack_bgpls_nlri(wire_format, rd)
        else:
            # GenericBGPLS receives complete wire format including header
            wire_format = bytes(data[0 : length + 4])
            klass = GenericBGPLS(code, wire_format)

        klass.addpath = addpath

        return klass, data[length + 4 :]

    def _raw(self) -> str:
        # _packed includes 4-byte header
        return ''.join('{:02X}'.format(_) for _ in self._packed)


class GenericBGPLS(BGPLS):
    __slots__ = ('_code',)

    def __init__(self, code: int, packed: Buffer) -> None:
        """Create GenericBGPLS with complete wire format.

        Args:
            code: NLRI type code
            packed: Complete wire format including 4-byte header [type(2)][length(2)][payload]
        """
        BGPLS.__init__(self)
        self._code = code
        self._packed = packed

    @property
    def CODE(self) -> int:  # type: ignore[override]
        return self._code

    def json(self, compact: bool = False) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
