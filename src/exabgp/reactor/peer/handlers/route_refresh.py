"""RouteRefreshHandler for processing received ROUTE-REFRESH messages.

This handler processes ROUTE_REFRESH messages and triggers route resend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Generator, cast

from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.refresh import Reserved, RouteRefresh
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import FamilyTuple
from exabgp.reactor.peer.handlers.base import MessageHandler

if TYPE_CHECKING:
    from exabgp.reactor.peer.context import PeerContext


class RouteRefreshHandler(MessageHandler):
    """Handles received ROUTE-REFRESH messages.

    Triggers route resend for the requested AFI/SAFI combination.
    Supports both standard and enhanced route refresh.
    """

    def __init__(self, resend_callback: Callable[[bool, FamilyTuple], None]) -> None:
        """Initialize the handler.

        Args:
            resend_callback: Function to call for route resend (typically peer.resend)
        """
        self._resend = resend_callback

    def can_handle(self, message: Message) -> bool:
        """Check if this is a ROUTE-REFRESH message."""
        return message.ID == Message.CODE.ROUTE_REFRESH

    def handle(self, ctx: PeerContext, message: Message) -> Generator[Message, None, None]:
        """Process the ROUTE-REFRESH message synchronously.

        Triggers resend of routes for the requested address family.
        """
        self._refresh(ctx, cast(RouteRefresh, message))

        return
        yield  # Make this a generator

    async def handle_async(self, ctx: PeerContext, message: Message) -> None:
        """Process the ROUTE-REFRESH message asynchronously.

        Same logic as sync - no async I/O needed.
        """
        self._refresh(ctx, cast(RouteRefresh, message))

    def _refresh(self, ctx: PeerContext, rr: RouteRefresh) -> None:
        family = (rr.afi, rr.safi)
        # RFC 2918 4: a ROUTE-REFRESH for a family "the speaker didn't advertise to the peer
        # at the session establishment time" is ignored, whatever its subtype: a BoRR or an
        # EoRR for any family the peer named marked or purged stale routes, and grew the
        # stale record with families the session does not have
        if family not in ctx.negotiated.families:
            log.warning(
                lazymsg(
                    'route-refresh.ignored reason=family-not-negotiated subtype={s} family={a}/{f}',
                    s=int(rr.reserved),
                    a=rr.afi,
                    f=rr.safi,
                ),
                ctx.peer_id,
            )
            return
        # Without the capability the octet is RFC 2918's Reserved field, which the
        # receiver ignores, so every ROUTE-REFRESH is a plain request
        if not ctx.refresh_enhanced:
            self._resend(False, family)
            return
        # RFC 7313 4: the receiver "MUST examine the message subtype field".  A BoRR and an
        # EoRR are the peer refreshing its own routes, not asking for ours
        if rr.reserved == Reserved.ROUTE_REFRESH_QUERY:
            self._resend(True, family)
        elif rr.reserved == Reserved.ROUTE_REFRESH_BEGIN:
            self._begin(ctx, family)
        elif rr.reserved == Reserved.ROUTE_REFRESH_END:
            self._end(ctx, family)
        else:
            # RFC 7313 5: any other subtype "MUST ignore the received ROUTE-REFRESH message.
            # It SHOULD log an error"
            log.warning(
                lazymsg('route-refresh.ignored subtype={s} family={a}/{f}', s=int(rr.reserved), a=rr.afi, f=rr.safi),
                ctx.peer_id,
            )

    def _begin(self, ctx: PeerContext, family: FamilyTuple) -> None:
        incoming = ctx.neighbor.rib.incoming
        # RFC 7313 4: with Graceful Restart from the peer, a BoRR before its End-of-RIB for
        # the family "MUST" be ignored and "SHOULD" be logged, so the two stale sweeps
        # cannot run into each other
        assert ctx.negotiated.received_open is not None, 'a ROUTE-REFRESH only arrives on an established session'
        graceful = ctx.negotiated.received_open.capabilities.announced(Capability.CODE.GRACEFUL_RESTART)
        if graceful and not incoming.has_end_of_rib(family):
            log.warning(
                lazymsg('route-refresh.borr.before-eor family={a}/{f}', a=family[0], f=family[1]),
                ctx.peer_id,
            )
            return
        incoming.mark_stale(family)

    def _end(self, ctx: PeerContext, family: FamilyTuple) -> None:
        # Only what the BoRR marked: routes a Graceful Restart retained wait for the
        # peer's End-of-RIB (RFC 4724 4.2), and are not this EoRR's to remove
        purged = ctx.neighbor.rib.incoming.purge_stale(family)
        if purged is None:
            # RFC 7313 4: an EoRR with no BoRR before it "MAY" be ignored and logged
            log.warning(
                lazymsg('route-refresh.eorr.without-borr family={a}/{f}', a=family[0], f=family[1]),
                ctx.peer_id,
            )
            return
        log.info(
            lazymsg('route-refresh.eorr family={a}/{f} purged={n}', a=family[0], f=family[1], n=len(purged)),
            ctx.peer_id,
        )
        # RFC 7313 4: the routes are removed, from the adj-rib-in and from the view of the
        # API processes, which are told as if the peer had withdrawn them
        ctx.proto.peer.tell_api_withdrawn(purged, ctx.negotiated)
