"""nlri.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, ClassVar, Type, final

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.nlri import NLRI

# https://tools.ietf.org/html/rfc7432

# +-----------------------------------+
# |    Route Type (1 octet)           |
# +-----------------------------------+
# |     Length (1 octet)              |
# +-----------------------------------+
# | Route Type specific (variable)    |
# +-----------------------------------+

# ========================================================================= EVPN


@NLRI.register(AFI.l2vpn, SAFI.evpn)
class EVPN(NLRI):
    """EVPN NLRI (RFC 7432) - single-family type with fixed AFI/SAFI.

    This class uses class-level AFI/SAFI constants to minimize per-instance
    storage, preparing for eventual buffer protocol sharing.
    """

    registered_evpn: ClassVar[dict[int, Type[EVPN]]] = dict()

    # Fixed AFI/SAFI for this single-family NLRI type
    _class_afi: ClassVar[AFI] = AFI.l2vpn
    _class_safi: ClassVar[SAFI] = SAFI.evpn

    # NEED to be defined in the subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, action: Action = Action.UNSET, addpath: PathInfo | None = None) -> None:
        # Family.__init__ detects afi/safi properties and skips setting them
        NLRI.__init__(self, AFI.l2vpn, SAFI.evpn, action)
        self.addpath = addpath if addpath is not None else PathInfo.DISABLED
        self._packed = b''

    @property
    @final
    def afi(self) -> AFI:
        """Return class-level AFI (l2vpn) - EVPN is always L2VPN."""
        return self._class_afi

    @property
    @final
    def safi(self) -> SAFI:
        """Return class-level SAFI (evpn) - EVPN is always EVPN."""
        return self._class_safi

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}'.format(self.afi, self.safi, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        return len(self._packed) + 2

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EVPN):
            return False
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        return 'evpn:{}:{}'.format(
            self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    def __repr__(self) -> str:
        return str(self)

    def feedback(self, action: int) -> None:
        # if self.nexthop is None and action == Action.ANNOUNCE:
        # 	raise RuntimeError('evpn nlri next-hop is missing')
        return None

    def _prefix(self) -> str:
        return 'evpn:{}:'.format(self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower())

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        # RFC 7911 ADD-PATH is possible for EVPN (AFI 25, SAFI 70) but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.evpn)
        return self._pack_nlri_simple()

    def index(self) -> bytes:
        return Family.index(self) + self._pack_nlri_simple()

    @classmethod
    def register(cls, klass: Type[EVPN]) -> Type[EVPN]:  # type: ignore[override]
        if klass.CODE in cls.registered_evpn:
            raise RuntimeError('only one EVPN registration allowed')
        cls.registered_evpn[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: PathInfo | None, negotiated: Negotiated
    ) -> tuple[EVPN, bytes]:
        # EVPN NLRI: route_type(1) + length(1) + route_data(length)
        if len(bgp) < 2:
            raise Notify(3, 10, f'EVPN NLRI too short: need at least 2 bytes, got {len(bgp)}')
        code = bgp[0]
        length = bgp[1]

        if len(bgp) < length + 2:
            raise Notify(3, 10, f'EVPN NLRI truncated: need {length + 2} bytes, got {len(bgp)}')

        if code in cls.registered_evpn:
            klass = cls.registered_evpn[code].unpack_evpn_route(bgp[2 : length + 2])  # type: ignore[attr-defined]
        else:
            klass = GenericEVPN(code, bgp[2 : length + 2])
        klass.CODE = code
        klass.action = action
        klass.addpath = addpath

        return klass, bgp[length + 2 :]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._pack_nlri_simple())


class GenericEVPN(EVPN):
    def __init__(self, code: int, packed: bytes) -> None:
        EVPN.__init__(self)
        self.CODE = code  # type: ignore[misc]
        self._pack(packed)

    def _pack(self, packed: bytes | None = None) -> bytes:
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed
        return b''

    def json(self, compact: bool | None = None) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
