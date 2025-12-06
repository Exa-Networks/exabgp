"""rtc.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Any, ClassVar, Type, TypeVar, final

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import RouteTarget
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP

T = TypeVar('T', bound='RTC')


@NLRI.register(AFI.ipv4, SAFI.rtc)
class RTC(NLRI):
    """RTC (Route Target Constraint) NLRI using partial packed-bytes-first pattern.

    This class uses class-level AFI/SAFI constants to minimize per-instance
    storage, preparing for eventual buffer protocol sharing.

    Note: Full packed-bytes-first pattern cannot be applied because rt (RouteTarget)
    requires 'negotiated' for unpacking. Origin ASN is stored as packed bytes,
    but rt is stored as RouteTarget object.

    Limitation: RFC 4684 prefix-based RTC filtering (variable length with partial RT)
    is not yet implemented - only full RTC constraints are supported.
    """

    # Fixed AFI/SAFI for this single-family NLRI type
    _class_afi: ClassVar[AFI] = AFI.ipv4
    _class_safi: ClassVar[SAFI] = SAFI.rtc

    def __init__(
        self,
        packed_origin: bytes | None,
        rt: RouteTarget | None,
        action: Action = Action.UNSET,
    ) -> None:
        """Create an RTC (Route Target Constraint) NLRI.

        Args:
            packed_origin: 4 bytes packed origin ASN, or None for wildcard
            rt: RouteTarget or None for wildcard
            action: Route action (ANNOUNCE/WITHDRAW)

        Note: We don't call NLRI.__init__ or Family.__init__ because afi/safi are
        class-level properties. We initialize action/addpath/nexthop directly.
        """
        # Skip Family.__init__ - afi/safi are class-level properties
        self.action = action
        self.addpath = PathInfo.DISABLED
        self._packed = b''  # RTC doesn't use _packed for CIDR storage
        self._packed_origin: bytes | None = packed_origin
        self.rt = rt
        self.nexthop = IP.NoNextHop

    @property
    @final
    def afi(self) -> AFI:
        """Return class-level AFI (ipv4) - RTC is always IPv4."""
        return self._class_afi

    @property
    @final
    def safi(self) -> SAFI:
        """Return class-level SAFI (rtc) - RTC is always RTC."""
        return self._class_safi

    @property
    def origin(self) -> ASN:
        """Origin ASN - unpacked from wire bytes."""
        if self._packed_origin is None:
            return ASN(0)
        return ASN(unpack('!L', self._packed_origin)[0])

    @classmethod
    def make_rtc(
        cls,
        origin: ASN,
        rt: RouteTarget | None,
        action: Action = Action.ANNOUNCE,
        nexthop: Any = IP.NoNextHop,
    ) -> 'RTC':
        """Factory method to create an RTC NLRI.

        Args:
            origin: Origin ASN
            rt: RouteTarget or None for wildcard
            action: Route action (ANNOUNCE/WITHDRAW)
            nexthop: Next-hop IP address

        Returns:
            New RTC instance
        """
        packed_origin = pack('!L', int(origin)) if rt is not None else None
        instance = cls(packed_origin, rt, action)
        instance.nexthop = nexthop
        return instance

    def feedback(self, action: Action) -> str:  # type: ignore[override]
        if self.nexthop is IP.NoNextHop and action == Action.ANNOUNCE:
            return 'rtc nlri next-hop missing'
        return ''

    def __len__(self) -> int:
        return (4 + len(self.rt)) * 8 if self.rt else 1

    def __str__(self) -> str:
        return 'rtc {}:{}'.format(self.origin, self.rt) if self.rt else 'rtc wildcard'

    def __repr__(self) -> str:
        return str(self)

    @staticmethod
    def resetFlags(char: int) -> int:
        return char & ~(Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL)

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        # RFC 7911 ADD-PATH is possible for RTC but not yet implemented
        # We reset ext com flag bits from the first byte in the packed RT
        # because in an RTC route these flags never appear.
        if self.rt and self._packed_origin:
            packedRT = self.rt.pack_attribute(negotiated)
            return pack('!B', len(self)) + self._packed_origin + bytes([RTC.resetFlags(packedRT[0])]) + packedRT[1:]
        return pack('!B', 0)

    def index(self) -> bytes:
        # RTC uses negotiated in pack_nlri, so we can't use _pack_nlri_simple
        # Index should be stable regardless of negotiated, so build it directly
        if self.rt and self._packed_origin:
            packedRT = self.rt._pack()  # type: ignore[attr-defined]  # Use internal pack without negotiated
            return (
                Family.index(self)
                + pack('!B', len(self))
                + self._packed_origin
                + bytes([RTC.resetFlags(packedRT[0])])
                + packedRT[1:]
            )  # type: ignore[no-any-return]
        return Family.index(self) + pack('!B', 0)

    @classmethod
    def unpack_nlri(
        cls: Type[T], afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[T, bytes]:
        # Note: afi/safi parameters are ignored - RTC is always ipv4/rtc
        length = bgp[0]

        if length == 0:
            return cls(None, None, action), bgp[1:]

        if length < 8 * 4:
            raise Exception('incorrect RT length: %d (should be >=32,<=96)' % length)

        # We are reseting the flags on the RouteTarget extended
        # community, because they do not make sense for an RTC route
        # Store origin as packed bytes directly from wire
        packed_origin = bgp[1:5]
        rt = RouteTarget.unpack_attribute(bytes([RTC.resetFlags(bgp[5])]) + bgp[6:13], negotiated)  # type: ignore[arg-type]

        return cls(packed_origin, rt, action), bgp[13:]
