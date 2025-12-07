from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, ClassVar, Type

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
    # MVPN has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    registered_mvpn: ClassVar[dict[int, Type[MVPN]]] = dict()

    # NEED to be defined in the subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def __init__(self, afi: AFI) -> None:
        NLRI.__init__(self, afi=afi, safi=SAFI.mcast_vpn)

    def __hash__(self) -> int:
        return hash('{}:{}:{}:{}'.format(self.afi, self.safi, self.CODE, self._packed.hex()))

    def __len__(self) -> int:
        return len(self._packed) + 2

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MVPN):
            return False
        return NLRI.__eq__(self, other) and self.CODE == other.CODE

    def __str__(self) -> str:
        return 'mvpn:{}:{}'.format(
            self.registered_mvpn.get(self.CODE, self).SHORT_NAME.lower(),
            '0x' + ''.join('{:02x}'.format(_) for _ in self._packed),
        )

    def __repr__(self) -> str:
        return str(self)

    def feedback(self, action: Action) -> str:
        # if self.nexthop is None and action == Action.ANNOUNCE:
        # 	raise RuntimeError('mvpn nlri next-hop is missing')
        return ''

    def _prefix(self) -> str:
        return 'mvpn:{}:'.format(self.registered_mvpn.get(self.CODE, self).SHORT_NAME.lower())

    def _pack_nlri_simple(self) -> Buffer:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return pack('!BB', self.CODE, len(self._packed)) + self._packed

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for MVPN but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(self.afi, SAFI.mcast_vpn)
        return self._pack_nlri_simple()

    def index(self) -> Buffer:
        return bytes(Family.index(self)) + self._pack_nlri_simple()

    def __copy__(self) -> 'MVPN':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi/safi)
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._copy_nlri_slots(new)
        # MVPN has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'MVPN':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family slots (afi/safi) - immutable enums
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._deepcopy_nlri_slots(new, memo)
        # MVPN has empty __slots__ - nothing else to copy
        return new

    @classmethod
    def register_mvpn(cls, klass: Type[MVPN]) -> Type[MVPN]:
        if klass.CODE in cls.registered_mvpn:
            raise RuntimeError('only one MVPN registration allowed')
        cls.registered_mvpn[klass.CODE] = klass
        return klass

    @classmethod
    def unpack_mvpn(cls, data: bytes, afi: AFI) -> 'MVPN':
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

        if len(data) < length + 2:
            raise Notify(3, 10, f'MVPN NLRI truncated: need {length + 2} bytes, got {len(data)}')

        if code in cls.registered_mvpn:
            klass = cls.registered_mvpn[code].unpack_mvpn(bytes(data[2 : length + 2]), afi)
        else:
            klass = GenericMVPN(afi, code, bytes(data[2 : length + 2]))

        klass.action = action
        klass.addpath = addpath

        return klass, data[length + 2 :]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._pack_nlri_simple())


class GenericMVPN(MVPN):
    CODE: int

    def __init__(self, afi: AFI, code: int, packed: Buffer) -> None:
        MVPN.__init__(self, afi)
        self.CODE = code
        self._packed = packed

    def json(self, compact: bool | None = None) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.CODE, self._raw())
