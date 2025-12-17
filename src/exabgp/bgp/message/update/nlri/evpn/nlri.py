"""nlri.py

Created by Thomas Morin on 2014-06-23.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
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
    """EVPN NLRI (RFC 7432) using packed-bytes-first pattern.

    _packed stores wire format: [type(1)][length(1)][payload...]
    AFI/SAFI set via Family parent class in __init__.
    """

    # EVPN has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    registered_evpn: ClassVar[dict[int, type[EVPN]]] = dict()

    # Wire format constant
    HEADER_SIZE = 2  # type(1) + length(1)

    # Set by decorator, override in GenericEVPN
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, packed: Buffer) -> None:
        """Create an EVPN NLRI from packed wire-format bytes.

        Args:
            packed: [type(1)][length(1)][payload...]

        Note: action, addpath, and nexthop are NOT part of NLRI wire format.
        - action defaults to UNSET, set after creation (announce/withdraw)
        - nexthop is in MP_REACH_NLRI attribute (RFC 4760)
        - addpath is a prefix when negotiated (RFC 7911)
        """
        NLRI.__init__(self, AFI.l2vpn, SAFI.evpn)
        self._packed = bytes(packed)  # Ensure bytes for storage

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}'.format(self.afi, self.safi, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        return len(self._packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EVPN):
            return False
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        # _packed[2:] is the payload (skip type + length header)
        return 'evpn:{}:{}'.format(
            self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed[self.HEADER_SIZE :]),
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

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def _prefix(self) -> str:
        return 'evpn:{}:'.format(self.registered_evpn.get(self.CODE, self).SHORT_NAME.lower())

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for EVPN (AFI 25, SAFI 70) but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(AFI.l2vpn, SAFI.evpn)
        return self._packed

    def index(self) -> bytes:
        return bytes(Family.index(self)) + self._packed

    @classmethod
    def unpack_evpn_route(cls, data: Buffer) -> EVPN:
        """Unpack route-type-specific data. Override in subclasses."""
        raise NotImplementedError(f'{cls.__name__} must implement unpack_evpn')

    @classmethod
    def register_evpn_route(cls, code: int):
        """Register an EVPN route type subclass by its code."""

        def decorator(klass: type[EVPN]) -> type[EVPN]:
            # Set class attribute
            klass.CODE = code
            # Register
            if code in cls.registered_evpn:
                raise RuntimeError('only one EVPN registration allowed')
            cls.registered_evpn[code] = klass
            return klass

        return decorator

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # EVPN NLRI: route_type(1) + length(1) + route_data(length)
        if len(data) < 2:
            raise Notify(3, 10, f'EVPN NLRI too short: need at least 2 bytes, got {len(data)}')
        code = data[0]
        length = data[1]
        total_length = 2 + length  # header (2) + payload

        if len(data) < total_length:
            raise Notify(3, 10, f'EVPN NLRI truncated: need {total_length} bytes, got {len(data)}')

        # Store COMPLETE wire format including type + length header
        packed = bytes(data[0:total_length])

        if code in cls.registered_evpn:
            nlri = cls.registered_evpn[code].unpack_evpn(packed)
        else:
            nlri = GenericEVPN(packed)
        nlri.addpath = addpath

        return nlri, data[total_length:]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._packed)


class GenericEVPN(EVPN):
    """Generic EVPN for unrecognized route types.

    Stores complete wire format including type + length header.
    """

    __slots__ = ()  # No extra storage needed - CODE extracted from _packed

    def __init__(self, packed: Buffer) -> None:
        """Create a GenericEVPN from complete wire format bytes.

        Args:
            packed: Complete wire format bytes (type + length + payload)
        """
        EVPN.__init__(self, packed)

    @property
    def CODE(self) -> int:
        """Route type code - extracted from wire bytes."""
        return self._packed[0]

    def json(self, compact: bool | None = None) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
