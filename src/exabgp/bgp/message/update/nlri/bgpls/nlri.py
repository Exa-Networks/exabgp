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
    _packed: bytes

    def __init__(self, action: Action = Action.UNSET, addpath: PathInfo | None = None) -> None:
        NLRI.__init__(self, AFI.bgpls, SAFI.bgp_ls, action)
        self._packed = b''

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for BGP-LS but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.bgpls, self.safi)
        # Wire format: [code(1)][length(1)][payload]
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    def index(self) -> bytes:
        # Wire format: [family][code(1)][length(1)][payload]
        return bytes(Family.index(self)) + pack('!BB', self.CODE, len(self._packed)) + self._packed

    def __len__(self) -> int:
        return len(self._packed) + 2

    def __hash__(self) -> int:
        packed = pack('!BB', self.CODE, len(self._packed)) + self._packed
        return hash((self.afi, self.safi, self.CODE, packed))

    def __str__(self) -> str:
        return 'bgp-ls:{}:{}'.format(
            self.registered_bgpls.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    def __copy__(self) -> 'BGPLS':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi/safi)
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._copy_nlri_slots(new)
        # BGPLS has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'BGPLS':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family slots (afi/safi) - immutable enums
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
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
                # Extract Route Distinguisher
                rd: RouteDistinguisher | None = RouteDistinguisher.unpack_routedistinguisher(bytes(data[4:12]))
                klass = cls.registered_bgpls[code].unpack_bgpls_nlri(bytes(data[12 : length + 4]), rd)
            else:
                rd = None
                klass = cls.registered_bgpls[code].unpack_bgpls_nlri(bytes(data[4 : length + 4]), rd)
        else:
            klass = GenericBGPLS(code, bytes(data[4 : length + 4]))

        klass.action = action
        klass.addpath = addpath

        return klass, data[length + 4 :]

    def _raw(self) -> str:
        packed = pack('!BB', self.CODE, len(self._packed)) + self._packed
        return ''.join('{:02X}'.format(_) for _ in packed)


class GenericBGPLS(BGPLS):
    CODE: int

    def __init__(self, code: int, packed: bytes) -> None:
        BGPLS.__init__(self)
        self.CODE = code
        self._packed = packed

    def json(self, compact: bool = False) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
