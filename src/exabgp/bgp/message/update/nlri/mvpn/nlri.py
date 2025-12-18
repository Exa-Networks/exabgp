from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, ClassVar, Type

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family

# https://datatracker.ietf.org/doc/html/rfc6514

# +-----------------------------------+
# |    Route Type (1 octet)           |
# +-----------------------------------+
# |     Length (1 octet)              |
# +-----------------------------------+
# | Route Type specific (variable)    |
# +-----------------------------------+

# ========================================================================= MVPN


@NLRI.register(AFI.ipv4, SAFI.mcast_vpn)
@NLRI.register(AFI.ipv6, SAFI.mcast_vpn)
class MVPN(NLRI):
    """MVPN NLRI (RFC 6514) using packed-bytes-first pattern.

    _packed stores wire format: [type(1)][length(1)][payload...]
    AFI set via Family parent class in __init__.
    """

    # MVPN has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    registered_mvpn: ClassVar[dict[int, Type[MVPN]]] = dict()

    # Wire format constant
    HEADER_SIZE = 2  # type(1) + length(1)

    # Set by decorator, override in GenericMVPN
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, afi: AFI) -> None:
        NLRI.__init__(self, afi=afi, safi=SAFI.mcast_vpn)

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}'.format(self.afi, self.safi, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        return len(self._packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MVPN):
            return False
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        # _packed[2:] is the payload (skip type + length header)
        return 'mvpn:{}:{}'.format(
            self.registered_mvpn.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed[self.HEADER_SIZE :]),
        )

    def __repr__(self) -> str:
        return str(self)

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def _prefix(self) -> str:
        return 'mvpn:{}:'.format(self.registered_mvpn.get(self.CODE, self).SHORT_NAME.lower())

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for MVPN but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(self.afi, SAFI.mcast_vpn)
        return self._packed

    def index(self) -> bytes:
        return bytes(Family.index(self)) + self._packed

    def __copy__(self) -> 'MVPN':
        new = self.__class__.__new__(self.__class__)
        # NLRI slots (includes Family slots: _afi, _safi)
        self._copy_nlri_slots(new)
        # MVPN has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'MVPN':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # NLRI slots (includes Family slots: _afi, _safi)
        self._deepcopy_nlri_slots(new, memo)
        # MVPN has empty __slots__ - nothing else to copy
        return new

    @classmethod
    def register_mvpn(cls, code: int) -> Callable[[Type[MVPN]], Type[MVPN]]:
        """Register an MVPN route type subclass by its code."""

        def decorator(klass: Type[MVPN]) -> Type[MVPN]:
            # Set class attribute
            klass.CODE = code
            # Register
            if code in cls.registered_mvpn:
                raise RuntimeError('only one MVPN registration allowed')
            cls.registered_mvpn[code] = klass
            return klass

        return decorator

    @classmethod
    def unpack_mvpn(cls, data: Buffer, afi: AFI) -> 'MVPN':
        """Unpack MVPN route from bytes. Must be implemented by subclasses."""
        raise NotImplementedError('unpack_mvpn must be implemented by subclasses')

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # MVPN NLRI: route_type(1) + length(1) + route_data(length)
        if len(data) < 2:
            raise Notify(3, 10, f'MVPN NLRI too short: need at least 2 bytes, got {len(data)}')
        code = data[0]
        length = data[1]
        total_length = length + 2  # header + payload

        if len(data) < total_length:
            raise Notify(3, 10, f'MVPN NLRI truncated: need {total_length} bytes, got {len(data)}')

        # Store COMPLETE wire format including type + length header
        packed = bytes(data[0:total_length])

        if code in cls.registered_mvpn:
            klass = cls.registered_mvpn[code].unpack_mvpn(packed, afi)
        else:
            klass = GenericMVPN(packed, afi)

        klass.addpath = addpath

        return klass, data[total_length:]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._packed)


class GenericMVPN(MVPN):
    """Generic MVPN for unrecognized route types.

    Stores complete wire format including type + length header.
    """

    __slots__ = ()  # No extra storage needed - CODE extracted from _packed

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create a GenericMVPN from complete wire format bytes.

        Args:
            packed: Complete wire format bytes (type + length + payload)
            afi: Address Family Identifier
        """
        MVPN.__init__(self, afi)
        self._packed = bytes(packed)  # Ensure bytes for storage

    @property
    def CODE(self) -> int:
        """Route type code - extracted from wire bytes."""
        return self._packed[0]

    def json(self, compact: bool | None = None) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
