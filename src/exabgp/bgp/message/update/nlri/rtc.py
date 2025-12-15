"""rtc.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Any, ClassVar, Type, TypeVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import RouteTarget
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family

T = TypeVar('T', bound='RTC')


@NLRI.register(AFI.ipv4, SAFI.rtc)
class RTC(NLRI):
    """RTC (Route Target Constraint) NLRI using packed-bytes-first pattern.

    Wire format (13 bytes for full RTC, 1 byte for wildcard):
    [length(1)] [origin(4)] [rt(8)]
     0:1         1:5         5:13

    - length: Length in bits (96 for full RTC, 0 for wildcard)
    - origin: Origin ASN (4 bytes, big-endian)
    - rt: RouteTarget with flags reset (8 bytes)

    Limitation: RFC 4684 prefix-based RTC filtering (variable length with partial RT)
    is not yet implemented - only full RTC constraints are supported.
    """

    __slots__ = ()  # Only _packed needed, inherited from NLRI

    # Wire format constants
    PACKED_LENGTH_FULL = 13  # 1 + 4 + 8
    PACKED_LENGTH_WILDCARD = 1

    # Fixed AFI/SAFI for this single-family NLRI type (class attributes shadow slots)
    afi: ClassVar[AFI] = AFI.ipv4
    safi: ClassVar[SAFI] = SAFI.rtc

    def __init__(self, packed: Buffer) -> None:
        """Create an RTC NLRI from packed wire-format bytes.

        Args:
            packed: Wire format bytes (13 bytes for full RTC, 1 byte for wildcard)
        """
        NLRI.__init__(self, AFI.ipv4, SAFI.rtc)
        self._packed: Buffer = packed

    @property
    def origin(self) -> ASN:
        """Origin ASN - unpacked from wire bytes on access."""
        if len(self._packed) < 5:
            return ASN(0)
        return ASN(unpack('!L', self._packed[1:5])[0])

    @property
    def rt(self) -> RouteTarget | None:
        """RouteTarget - lazily unpacked from wire bytes on access."""
        if len(self._packed) < 13:
            return None
        # RT is stored with flags already reset, use unpack_attribute for proper subclass dispatch
        return RouteTarget.unpack_attribute(self._packed[5:13], None)  # type: ignore[return-value]

    @classmethod
    def make_rtc(
        cls,
        origin: ASN,
        rt: RouteTarget | None,
    ) -> 'RTC':
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

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def __len__(self) -> int:
        # Length in bits: for wildcard (single 0 byte), return 1
        # For full RTC: length is stored at byte 0 (96 bits = (4+8)*8)
        return self._packed[0] if self._packed[0] != 0 else 1

    def __str__(self) -> str:
        if len(self._packed) >= 13:
            return 'rtc {}:{}'.format(self.origin, self.rt)
        return 'rtc wildcard'

    def __repr__(self) -> str:
        return str(self)

    def __copy__(self) -> 'RTC':
        new = self.__class__.__new__(self.__class__)
        self._copy_nlri_slots(new)
        new._packed = self._packed  # bytes - immutable
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'RTC':
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
        return self._packed

    def index(self) -> bytes:
        """Return unique index for this RTC NLRI."""
        return Family.index(self) + self._packed

    @classmethod
    def unpack_nlri(
        cls: Type[T], afi: AFI, safi: SAFI, bgp: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[T, Buffer]:
        data = memoryview(bgp) if not isinstance(bgp, memoryview) else bgp
        # Note: afi/safi parameters are ignored - RTC is always ipv4/rtc
        length = data[0]

        if length == 0:
            nlri = cls(bytes(data[0:1]))
            return nlri, data[1:]

        if length < 8 * 4:
            raise Exception('incorrect RT length: %d (should be >=32,<=96)' % length)

        # Store complete wire format with flags reset on RT
        # Wire format: [length(1)][origin(4)][rt(8)]
        packed = (
            bytes(data[0:5])  # length + origin
            + bytes([RTC.resetFlags(data[5])])  # RT first byte with flags reset
            + bytes(data[6:13])  # RT remaining bytes
        )

        nlri = cls(packed)
        return nlri, data[13:]
