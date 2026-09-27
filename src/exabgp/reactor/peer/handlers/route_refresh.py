"""RouteRefreshHandler for processing received ROUTE-REFRESH messages.

This handler processes ROUTE_REFRESH messages and triggers route resend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Generator, cast

from exabgp.bgp.message import Message
from exabgp.bgp.message.refresh import Reserved, RouteRefresh
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import FamilyTuple
from exabgp.reactor.peer.handlers.base import MessageHandler

if TYPE_CHECKING:
    from exabgp.reactor.peer.context import PeerContext


_SUBTYPES = (Reserved.ROUTE_REFRESH_QUERY, Reserved.ROUTE_REFRESH_BEGIN, Reserved.ROUTE_REFRESH_END)


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
        return message.TYPE == RouteRefresh.TYPE

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
        # RFC 7313 5: once the capability was received, a Message Subtype other than 0, 1
        # or 2 "MUST ignore the received ROUTE-REFRESH message.  It SHOULD log an error".
        # Without the capability the octet is RFC 2918's Reserved field, which the
        # receiver ignores, so the message is still a plain request
        if ctx.refresh_enhanced and rr.reserved not in _SUBTYPES:
            log.warning(
                lazymsg('route-refresh.ignored subtype={s} family={a}/{f}', s=int(rr.reserved), a=rr.afi, f=rr.safi),
                ctx.peer_id,
            )
            return
        enhanced = rr.reserved == RouteRefresh.request and ctx.refresh_enhanced
        self._resend(enhanced, (rr.afi, rr.safi))
