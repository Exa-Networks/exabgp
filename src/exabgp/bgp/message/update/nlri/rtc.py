"""rtc.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import Any, Self, TYPE_CHECKING, Type, TypeVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import RTCSettings

from exabgp.bgp.message import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import RouteTarget
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family

T = TypeVar('T', bound='RTCBase')


# RFC 4684 section 4: the RTC prefix covers the origin AS and the route target, so it is
# between the origin alone and the whole of both
RTC_PREFIX_MIN_BITS = 32
RTC_PREFIX_MAX_BITS = 96
# the origin AS ends at octet 5 of the packed form, and the route target starts there
RTC_ROUTE_TARGET_OFFSET = 5


class RTCBase(NLRI):
    """RTC (Route Target Constraint) NLRI using packed-bytes-first pattern.

    Wire format (13 bytes for full RTC, 1 byte for wildcard):
    [length(1)] [origin(4)] [rt(8)]
     0:1         1:5         5:13

    - length: Length in bits (96 for full RTC, 0 for wildcard)
    - origin: Origin ASN (4 bytes, big-endian)
    - rt: RouteTarget with flags reset (8 bytes)

    RFC 4684 section 4 makes it a prefix: a length from 32 to 95 bits carries the origin AS and
    only the leading ceil(length / 8) - 4 octets of the route target. Such a prefix is decoded
    and kept as received, has no `rt`, and cannot be configured.
    """

    __slots__ = ()  # Only _packed needed, inherited from NLRI

    # Wire format constants
    PACKED_LENGTH_FULL = 13  # 1 + 4 + 8
    PACKED_LENGTH_WILDCARD = 1

    # Fixed AFI/SAFI for this single-family NLRI type
    @property
    def afi(self) -> AFI:
        return AFI.ipv4

    @property
    def safi(self) -> SAFI:
        return SAFI.rtc

    def __init__(self, packed: Buffer) -> None:
        """Create an RTC NLRI from packed wire-format bytes.

        Args:
            packed: Wire format bytes (13 bytes for full RTC, 1 byte for wildcard)
        """
        NLRI.__init__(self, AFI.ipv4, SAFI.rtc)
        self._packed: Buffer = packed

    @property
    def prefix_length(self) -> int:
        """Length of the prefix in bits: 0 for the default route target, 96 for a full one."""
        return self._packed[0]

    @property
    def origin(self) -> ASN:
        """Origin ASN - unpacked from wire bytes on access."""
        if len(self._packed) < 5:
            return ASN(0)
        return ASN(unpack('!L', self._packed[1:5])[0])

    @property
    def rt(self) -> RouteTarget | None:
        """RouteTarget - lazily unpacked from wire bytes on access."""
        from typing import cast

        if self.prefix_length != RTC_PREFIX_MAX_BITS:
            return None
        # RT is stored with flags already reset, use unpack_attribute for proper subclass dispatch
        return cast(RouteTarget, RouteTarget.unpack_attribute(self._packed[5:13], None))

    @classmethod
    def make_rtc(
        cls,
        origin: ASN,
        rt: RouteTarget | None,
    ) -> Self:
        """Factory method to create an RTC NLRI from components.

        Args:
            origin: Origin ASN
            rt: RouteTarget or None for wildcard

        Returns:
            New RTC instance

        Note: nexthop is stored in Route, not NLRI. Pass nexthop to Route constructor.
        """
        if rt is not None:
            packed_rt = rt._packed
            # Length in bits: (4 bytes origin + 8 bytes RT) * 8 = 96
            packed = pack('!BL', 96, int(origin)) + bytes([RTC.resetFlags(packed_rt[0])]) + packed_rt[1:]
        else:
            packed = pack('!B', 0)

        instance = cls(packed)
        return instance

    @classmethod
    def from_settings(cls, settings: 'RTCSettings') -> Self:
        """Create an RTC NLRI from validated settings.

        Raises:
            ValueError: If settings validation fails
        """
        error = settings.validate()
        if error:
            raise ValueError(error)
        if settings.default:
            return cls.make_rtc(ASN(0), None)
        assert settings.origin_as is not None, 'validate() requires origin-as without default'
        assert settings.route_target is not None, 'validate() requires route-target without default'
        return cls.make_rtc(settings.origin_as, settings.route_target)

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def __len__(self) -> int:
        # Length in bits: for wildcard (single 0 byte), return 1
        # For full RTC: length is stored at byte 0 (96 bits = (4+8)*8)
        return self._packed[0] if self._packed[0] != 0 else 1

    def _target_prefix(self) -> str:
        """The octets of a partial route target, as hex."""
        return '0x' + bytes(self._packed[RTC_ROUTE_TARGET_OFFSET:]).hex().upper()

    def __str__(self) -> str:
        if self.prefix_length == RTC_PREFIX_MAX_BITS:
            return 'rtc {}:{}'.format(self.origin, self.rt)
        if self.prefix_length:
            return 'rtc {}:{}/{}'.format(self.origin, self._target_prefix(), self.prefix_length)
        return 'rtc wildcard'

    def __repr__(self) -> str:
        return str(self)

    def json(self, announced: bool = True, compact: bool = False) -> str:
        rt = self.rt
        if rt is not None:
            return '{{ "origin": {}, "route-target": "{}" }}'.format(self.origin, rt)
        if self.prefix_length:
            return '{{ "origin": {}, "route-target": null, "prefix-length": {}, "route-target-prefix": "{}" }}'.format(
                self.origin, self.prefix_length, self._target_prefix()
            )
        return '{ "origin": 0, "route-target": null }'

    def __copy__(self) -> Self:
        new = self.__class__.__new__(self.__class__)
        self._copy_nlri_slots(new)
        new._packed = self._packed  # bytes - immutable
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> Self:
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        self._deepcopy_nlri_slots(new, memo)
        new._packed = self._packed  # bytes - immutable
        return new

    @staticmethod
    def resetFlags(char: int) -> int:
        return char & ~(Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL)

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        """Pack NLRI - returns stored wire bytes directly (zero-copy)."""
        assert len(self._packed) == 1 + (self.prefix_length + 7) // 8, (
            'an RTC NLRI carries the octets its prefix length needs, no more and no less'
        )
        return self._packed

    def index(self) -> bytes:
        """Return unique index for this RTC NLRI."""
        return Family.index(self) + self._packed

    @classmethod
    def unpack_nlri(
        cls: Type[T], afi: AFI, safi: SAFI, bgp: Buffer, action: Action, addpath: bool, negotiated: Negotiated
    ) -> tuple[T, Buffer]:
        # RFC 7911 3: with ADD-PATH negotiated the peer puts a four byte Path
        # Identifier in front of every NLRI of this family, and it has to come off
        # before the NLRI is read.
        path_info, bgp = NLRI.consume_path_information(bgp, addpath)
        data = memoryview(bgp) if not isinstance(bgp, memoryview) else bgp
        # Note: afi/safi parameters are ignored - RTC is always ipv4/rtc
        if not data:
            raise Notify(3, 10, 'not enough data to extract the length of the RTC NLRI')

        length = data[0]

        if length == 0:
            nlri = cls(bytes(data[0:1]))
            nlri.addpath = path_info
            return nlri, data[1:]

        # RFC 4684 section 4: the prefix is 32 to 96 bits, the origin AS and then as much of
        # the route target as the sender chose to carry. The message has always advertised
        # the upper bound; it was never checked, so a length of 200 got past it.
        if not RTC_PREFIX_MIN_BITS <= length <= RTC_PREFIX_MAX_BITS:
            raise Notify(
                3,
                10,
                'incorrect RTC length: %d (should be >=%d,<=%d)' % (length, RTC_PREFIX_MIN_BITS, RTC_PREFIX_MAX_BITS),
            )

        # RFC 4760 section 4: the prefix takes the octets its length needs, rounded up, so a
        # prefix shorter than 96 bits is shorter than 13 octets and the next NLRI follows it
        size = 1 + (length + 7) // 8
        if len(data) < size:
            raise Notify(
                3,
                10,
                'RTC NLRI truncated: need %d bytes, got %d' % (size, len(data)),
            )

        # Store the wire format with the flags reset on the first octet of the route target,
        # when the prefix reaches it: [length(1)][origin(4)][rt(0 to 8)]
        packed = bytes(data[0:size])
        if size > RTC_ROUTE_TARGET_OFFSET:
            offset = RTC_ROUTE_TARGET_OFFSET
            packed = packed[:offset] + bytes([RTC.resetFlags(packed[offset])]) + packed[offset + 1 :]

        nlri = cls(packed)
        nlri.addpath = path_info
        return nlri, data[size:]


@NLRI.register(AFI.ipv4, SAFI.rtc)
class RTC(RTCBase):
    """The registered form of RTCBase, which holds the code.

    The split is not architectural: mutmut does not mutate the methods of a decorated class,
    and every decoder here carries a register decorator, so the code which parses what a
    peer sends was the one part of this tree mutation testing could not see. Keeping the
    body in an undecorated base and registering an empty subclass puts it back in reach.

    __slots__ is empty on purpose. Without it every instance would grow a __dict__,
    which is the memory the packed-bytes-first work went to some trouble to avoid.
    """

    __slots__ = ()
