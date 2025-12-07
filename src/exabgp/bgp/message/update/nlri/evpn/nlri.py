"""nlri.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.util.types import Buffer

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

    # EVPN has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    registered_evpn: ClassVar[dict[int, type[EVPN]]] = dict()

    # NEED to be defined in the subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, action: Action = Action.UNSET, addpath: PathInfo | None = None) -> None:
        # Family.__init__ detects afi/safi properties and skips setting them
        NLRI.__init__(self, AFI.l2vpn, SAFI.evpn, action)
        self.addpath = addpath if addpath is not None else PathInfo.DISABLED
        self._packed = b''

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

    def __copy__(self) -> 'EVPN':
        new = self.__class__.__new__(self.__class__)
        # Family/NLRI slots (afi/safi are class-level)
        self._copy_nlri_slots(new)
        # EVPN has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'EVPN':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family/NLRI slots (afi/safi are class-level)
        self._deepcopy_nlri_slots(new, memo)
        # EVPN has empty __slots__ - nothing else to copy
        return new

    def feedback(self, action: int) -> str:
        # if self.nexthop is None and action == Action.ANNOUNCE:
        # 	raise RuntimeError('evpn nlri next-hop is missing')
        return ''

    def _prefix(self) -> str:
        return 'evpn:{}:'.format(self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower())

    def _pack_nlri_simple(self) -> Buffer:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for EVPN (AFI 25, SAFI 70) but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.evpn)
        return self._pack_nlri_simple()

    def index(self) -> Buffer:
        return bytes(Family.index(self)) + bytes(self._pack_nlri_simple())

    @classmethod
    def unpack_evpn_route(cls, data: Buffer) -> EVPN:
        """Unpack route-type-specific data. Override in subclasses."""
        raise NotImplementedError(f'{cls.__name__} must implement unpack_evpn')

    @classmethod
    def register_evpn_route(cls, klass: type[EVPN]) -> type[EVPN]:
        """Register an EVPN route type subclass by its CODE."""
        if klass.CODE in cls.registered_evpn:
            raise RuntimeError('only one EVPN registration allowed')
        cls.registered_evpn[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # EVPN NLRI: route_type(1) + length(1) + route_data(length)
        if len(data) < 2:
            raise Notify(3, 10, f'EVPN NLRI too short: need at least 2 bytes, got {len(data)}')
        code = data[0]
        length = data[1]

        if len(data) < length + 2:
            raise Notify(3, 10, f'EVPN NLRI truncated: need {length + 2} bytes, got {len(data)}')

        if code in cls.registered_evpn:
            nlri = cls.registered_evpn[code].unpack_evpn(bytes(data[2 : length + 2]))
        else:
            nlri = GenericEVPN(code, bytes(data[2 : length + 2]))
        nlri.action = action
        nlri.addpath = addpath

        return nlri, data[length + 2 :]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._pack_nlri_simple())


class GenericEVPN(EVPN):
    """Generic EVPN for unrecognized route types."""

    __slots__ = ('_code',)

    def __init__(self, code: int, packed: bytes) -> None:
        EVPN.__init__(self)
        self._code = code
        self._packed = packed

    @property
    def CODE(self) -> int:  # type: ignore[override]
        return self._code

    def json(self, compact: bool | None = None) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
