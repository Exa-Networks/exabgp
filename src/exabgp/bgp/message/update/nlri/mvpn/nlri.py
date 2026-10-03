from __future__ import annotations

from typing import Any, Callable, ClassVar, Self, TYPE_CHECKING, Type

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.protocol.ip import IP
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IPv4, IPv6

# https://datatracker.ietf.org/doc/html/rfc6514

# +-----------------------------------+
# |    Route Type (1 octet)           |
# +-----------------------------------+
# |     Length (1 octet)              |
# +-----------------------------------+
# | Route Type specific (variable)    |
# +-----------------------------------+

# RFC 6514 sections 4.3, 4.5, 4.6 and 4.7 all end the same way: a Multicast Source
# Length or Multicast Group Length octet is 32 when the address which follows is IPv4
# and 128 when it is IPv6, and "usage of other values [...] is outside the scope of this
# document".
MVPN_ADDRESS_LENGTH_BITS: tuple[int, int] = (IPv4.BITS, IPv6.BITS)

# RFC 6514 4: the seven route types the MCAST-VPN specification defines. 5, 6 and 7 are
# decoded, 1 to 4 are kept as the bytes the peer sent. Any other type is unrecognised.
RFC6514_ROUTE_TYPES: frozenset[int] = frozenset(range(1, 8))


def check_source_and_group(packed: Buffer, cursor: int, name: str) -> None:
    """Check the Multicast Source and Multicast Group of a route which carries both.

    The octet is compared against 32 and 128 rather than its quotient by eight, because a
    quotient accepts far more than the RFC defines: 33 to 39 divide to four octets and are
    read back as an IPv4 address the peer never sent, and 129 to 135 divide to sixteen and
    move the cursor past the end of an eighteen octet payload, where the read of the group
    length octet raises IndexError instead of closing the session with a NOTIFICATION.

    `cursor` is the offset of the Multicast Source Length octet within `packed`.
    """
    for field in ('Multicast Source', 'Multicast Group'):
        if cursor >= len(packed):
            raise Notify(3, 5, f'{name} is too short to hold its {field} Length octet.')
        bits = packed[cursor]
        if bits not in MVPN_ADDRESS_LENGTH_BITS:
            raise Notify(
                3,
                5,
                f'Unsupported {name} {field} IP length ({bits} bits). Expected 32 bits (IPv4) or 128 bits (IPv6).',
            )
        cursor += 1 + bits // 8
    if cursor != len(packed):
        raise Notify(3, 5, f'{name} length does not match its Multicast Source and Multicast Group addresses.')


# ========================================================================= MVPN


class MVPN(NLRI):
    """MVPN NLRI (RFC 6514) using packed-bytes-first pattern.

    _packed stores wire format: [type(1)][length(1)][payload...]
    AFI set via Family parent class in __init__.
    """

    # MVPN has no additional instance attributes beyond NLRI base class
    __slots__ = ()

    registered_mvpn: ClassVar[dict[int, Type[MVPN]]] = dict()

    # Wire format constant
    HEADER_SIZE: ClassVar[int] = 2  # type(1) + length(1)

    # Set by decorator, override in GenericMVPN
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = 'Unknown'
    SHORT_NAME: ClassVar[str] = 'unknown'

    def v4_text(self, nexthop: IP | None = None) -> str:
        """As 5.x wrote it: the route without its next-hop."""
        return self.extensive()

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

    # written out: mypyc fails to derive __ne__ from __eq__ for the subclasses. The operator,
    # not a call to __eq__, so NotImplemented is answered the way Python answers it.
    def __ne__(self, other: object) -> bool:
        return not self == other

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
        new = self._fresh()
        # NLRI slots (includes Family slots: _afi, _safi)
        self._copy_nlri_slots(new)
        # MVPN has empty __slots__ - nothing else to copy
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'MVPN':
        new = self._fresh()
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
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: bool, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        # RFC 7911 3: with ADD-PATH negotiated the peer puts a four byte Path
        # Identifier in front of every NLRI of this family, and it has to come off
        # before the NLRI is read.
        path_info, data = NLRI.consume_path_information(data, addpath)
        # MVPN NLRI: route_type(1) + length(1) + route_data(length)
        if len(data) < 2:
            raise Notify.short(3, 10, 'MVPN NLRI', 2, len(data))
        code = data[0]
        length = data[1]
        total_length = length + 2  # header + payload

        if len(data) < total_length:
            raise Notify.short(3, 10, 'MVPN NLRI', total_length, len(data))

        # Store COMPLETE wire format including type + length header
        packed = bytes(data[0:total_length])

        if code in cls.registered_mvpn:
            klass = cls.registered_mvpn[code].unpack_mvpn(packed, afi)
        else:
            klass = GenericMVPN(packed, afi)

        klass.addpath = path_info

        return klass, data[total_length:]

    def _raw(self) -> str:
        return ''.join('{:02X}'.format(_) for _ in self._packed)


NLRI.register(AFI.ipv6, SAFI.mcast_vpn)(MVPN)
NLRI.register(AFI.ipv4, SAFI.mcast_vpn)(MVPN)


class GenericMVPN(MVPN):
    """Generic MVPN for unrecognized route types.

    Stores complete wire format including type + length header.
    """

    __slots__ = ()  # No extra storage needed - CODE extracted from _packed

    def _fresh(self) -> Self:
        return type(self)(self._packed, self.afi)

    def __init__(self, packed: Buffer, afi: AFI) -> None:
        """Create a GenericMVPN from complete wire format bytes.

        Args:
            packed: Complete wire format bytes (type + length + payload)
            afi: Address Family Identifier
        """
        MVPN.__init__(self, afi)
        self._packed = bytes(packed)  # Ensure bytes for storage

    @property
    def route_code(self) -> int:
        """Route type code - extracted from wire bytes.

        Note: Named route_code to avoid overriding base MVPN.CODE ClassVar.
        Base classes use CODE set by decorator; GenericMVPN extracts dynamically.
        """
        return self._packed[0]

    def discard_on_receipt(self) -> str | None:
        # RFC 7606 5.4, the same rule as GenericEVPN: an announced route of a type we do
        # not recognise is discarded, a withdrawn one is reported. Types 1 to 4 are
        # recognised: RFC 6514 defines them, and we keep them as opaque bytes rather than
        # decode them, so dropping them would lose most of what an MVPN peer sends.
        if self.route_code in RFC6514_ROUTE_TYPES:
            return None
        return f'unrecognised MCAST-VPN route type {self.route_code} (RFC 7606 5.4)'

    def json(self, announced: bool = True, compact: bool | None = None) -> str:
        return '{ "code": %d, "parsed": false, "raw": "%s" }' % (self.route_code, self._raw())
