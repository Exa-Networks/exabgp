"""nlri.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, ClassVar, Dict, Tuple, Type

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family

from exabgp.bgp.message import Action

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
    registered_evpn: ClassVar[Dict[int, Type[EVPN]]] = dict()

    # NEED to be defined in the subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, action: Action = Action.UNSET, addpath: PathInfo | None = None) -> None:
        NLRI.__init__(self, AFI.l2vpn, SAFI.evpn, action)
        self._packed: bytes = b''

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}'.format(self.afi, self.safi, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        return len(self._packed) + 2

    def __eq__(self, other: object) -> bool:
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        return 'evpn:{}:{}'.format(
            self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    def __repr__(self) -> str:
        return str(self)

    def feedback(self, action: Action) -> str:
        # if self.nexthop is None and action == Action.ANNOUNCE:
        # 	return 'evpn nlri next-hop is missing'
        return ''

    def _prefix(self) -> str:
        return 'evpn:{}:'.format(self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower())

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    def pack_nlri(self, negotiated: Negotiated) -> bytes:  # type: ignore[assignment]
        # RFC 7911 ADD-PATH is possible for EVPN (AFI 25, SAFI 70) but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.evpn)
        return self._pack_nlri_simple()

    def index(self) -> bytes:
        return Family.index(self) + self._pack_nlri_simple()

    @classmethod
    def register(cls, klass: Type[EVPN]) -> Type[EVPN]:
        if klass.CODE in cls.registered_evpn:
            raise RuntimeError('only one EVPN registration allowed')
        cls.registered_evpn[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: PathInfo | None, negotiated: Negotiated
    ) -> Tuple[EVPN, bytes]:
        code = bgp[0]
        length = bgp[1]

        if code in cls.registered_evpn:
            klass = cls.registered_evpn[code].unpack_evpn_route(bgp[2 : length + 2])
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
        self.CODE = code
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
