"""nlri.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional, Tuple, Type, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import Action

from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher

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

PROTO_CODES: Dict[int, str] = {
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
    registered_bgpls: ClassVar[Dict[int, Type[BGPLS]]] = dict()

    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, action: Action = Action.UNSET, addpath: Any = None) -> None:
        NLRI.__init__(self, AFI.bgpls, SAFI.bgp_ls, action)
        self._packed: bytes = b''

    def pack_nlri(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    def __len__(self) -> int:
        return len(self._packed) + 2

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}'.format(self.afi, self.safi, self.CODE, self._packed))  # type: ignore[str-bytes-safe]

    def __str__(self) -> str:
        return 'bgp-ls:{}:{}'.format(
            self.registered_bgpls.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    @classmethod
    def register(cls, klass: Type[BGPLS]) -> Type[BGPLS]:
        if klass.CODE in cls.registered_bgpls:
            raise RuntimeError('only one BGP LINK_STATE registration allowed')
        cls.registered_bgpls[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls: Type[T], afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: Any, negotiated
    ) -> Tuple[T, bytes]:
        code, length = unpack('!HH', bgp[:4])
        if code in cls.registered_bgpls:
            if safi == SAFI.bgp_ls_vpn:
                # Extract Route Distinguisher
                rd: Optional[RouteDistinguisher] = RouteDistinguisher.unpack(bgp[4:12])
                klass = cls.registered_bgpls[code].unpack_nlri(bgp[12 : length + 4], rd)  # type: ignore[arg-type,call-arg]
            else:
                rd = None
                klass = cls.registered_bgpls[code].unpack_nlri(bgp[4 : length + 4], rd)  # type: ignore[arg-type,call-arg]
        else:
            klass = GenericBGPLS(code, bgp[4 : length + 4])
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, bgp[length + 4 :]  # type: ignore[return-value]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self.pack())


class GenericBGPLS(BGPLS):
    def __init__(self, code: int, packed: bytes) -> None:
        BGPLS.__init__(self)
        self.CODE = code
        self._pack(packed)

    def _pack(self, packed: Optional[bytes] = None) -> Optional[bytes]:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed
        return None

    def json(self, compact: Any = None) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
