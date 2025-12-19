"""RouteRefreshHandler for processing received ROUTE-REFRESH messages.

This handler processes ROUTE_REFRESH messages and triggers route resend.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Generator, cast

from exabgp.bgp.message import Message
from exabgp.bgp.message.refresh import RouteRefresh
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
        return message.TYPE == RouteRefresh.TYPE

    def handle(self, ctx: PeerContext, message: Message) -> Generator[Message, None, None]:
        """Process the ROUTE-REFRESH message synchronously.

        Triggers resend of routes for the requested address family.
        """
        rr = cast(RouteRefresh, message)
        enhanced = rr.reserved == RouteRefresh.request and ctx.refresh_enhanced
        self._resend(enhanced, (rr.afi, rr.safi))

        return
        yield  # Make this a generator

    async def handle_async(self, ctx: PeerContext, message: Message) -> None:
        """Process the ROUTE-REFRESH message asynchronously.

        Same logic as sync - no async I/O needed.
        """
        rr = cast(RouteRefresh, message)
        enhanced = rr.reserved == RouteRefresh.request and ctx.refresh_enhanced
        self._resend(enhanced, (rr.afi, rr.safi))
