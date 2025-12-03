"""rtc.py

Created by Thomas Morin on 2014-06-10.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack, unpack
from typing import TYPE_CHECKING, Any, Type, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import RouteTarget
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP

T = TypeVar('T', bound='RTC')


@NLRI.register(AFI.ipv4, SAFI.rtc)
class RTC(NLRI):
    # XXX: FIXME: no support yet for RTC variable length with prefixing

    def __init__(
        self,
        afi: AFI,
        safi: SAFI,
        action: Action,
        origin: ASN,
        rt: RouteTarget | None,
    ) -> None:
        """Create an RTC (Route Target Constraint) NLRI.

        Args:
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            action: Route action (ANNOUNCE/WITHDRAW)
            origin: Origin ASN
            rt: RouteTarget or None for wildcard
        """
        NLRI.__init__(self, afi, safi)
        self.action = action
        self.origin = origin
        self.rt = rt
        self.nexthop = IP.NoNextHop

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
        instance = cls(AFI.ipv4, SAFI.rtc, action, origin, rt)
        instance.nexthop = nexthop
        return instance

    # Backward compatibility alias
    @classmethod
    def new(
        cls,
        afi: AFI,
        safi: SAFI,
        origin: ASN,
        rt: RouteTarget,
        nexthop: Any = IP.NoNextHop,
        action: Action = Action.UNSET,
    ) -> 'RTC':
        """Legacy factory method for backward compatibility."""
        instance = cls(afi, safi, action, origin, rt)
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
        if self.rt:
            packedRT = self.rt.pack_attribute(negotiated)
            return pack('!BLB', len(self), self.origin, RTC.resetFlags(packedRT[0])) + packedRT[1:]
        return pack('!B', 0)

    def index(self) -> bytes:
        # RTC uses negotiated in pack_nlri, so we can't use _pack_nlri_simple
        # Index should be stable regardless of negotiated, so build it directly
        if self.rt:
            packedRT = self.rt._pack()  # type: ignore[attr-defined]  # Use internal pack without negotiated
            return Family.index(self) + pack('!BLB', len(self), self.origin, RTC.resetFlags(packedRT[0])) + packedRT[1:]  # type: ignore[no-any-return]
        return Family.index(self) + pack('!B', 0)

    @classmethod
    def unpack_nlri(
        cls: Type[T], afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[T, bytes]:
        length = bgp[0]

        if length == 0:
            return cls(afi, safi, action, ASN(0), None), bgp[1:]

        if length < 8 * 4:
            raise Exception('incorrect RT length: %d (should be >=32,<=96)' % length)

        # We are reseting the flags on the RouteTarget extended
        # community, because they do not make sense for an RTC route

        return (
            cls(
                afi,
                safi,
                action,
                ASN(unpack('!L', bgp[1:5])[0]),
                RouteTarget.unpack_attribute(bytes([RTC.resetFlags(bgp[5])]) + bgp[6:13], negotiated),  # type: ignore[arg-type]
            ),
            bgp[13:],
        )
