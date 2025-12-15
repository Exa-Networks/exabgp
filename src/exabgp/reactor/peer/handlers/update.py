"""UpdateHandler for processing received BGP UPDATE messages.

This handler processes UPDATE messages and stores NLRIs in the incoming RIB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator, cast

from exabgp.bgp.message import Action, Message, Update
from exabgp.logger import lazyformat, lazymsg, log
from exabgp.reactor.peer.handlers.base import MessageHandler

if TYPE_CHECKING:
    from exabgp.reactor.peer.context import PeerContext


class UpdateHandler(MessageHandler):
    """Handles received BGP UPDATE messages.

    Processes NLRI announcements/withdrawals and stores changes in incoming RIB.
    Maintains count of received updates for logging.
    """

    def __init__(self) -> None:
        self._number: int = 0

    def reset(self) -> None:
        """Reset counter for new session."""
        self._number = 0

    def can_handle(self, message: Message) -> bool:
        """Check if this is an UPDATE message."""
        return message.TYPE == Update.TYPE

    def handle(self, ctx: PeerContext, message: Message) -> Generator[Message, None, None]:
        """Process the UPDATE message synchronously.

        Stores all NLRIs in the incoming RIB cache.
        """
        update = cast(Update, message)
        parsed = update.data  # Already parsed by unpack_message
        self._number += 1

        log.debug(lazymsg('update.received number={number}', number=self._number), ctx.peer_id)

        # Process announces - pass action and nexthop explicitly
        # parsed.announces contains RoutedNLRI objects; extract the bare NLRI for RIB
        for routed in parsed.announces:
            nlri = routed.nlri
            ctx.neighbor.rib.incoming.update_cache(nlri, parsed.attributes, Action.ANNOUNCE, routed.nexthop)
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )

        # Process withdraws - use dedicated method
        for nlri in parsed.withdraws:
            ctx.neighbor.rib.incoming.update_cache_withdraw(nlri)
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )

        return
        yield  # Make this a generator

    async def handle_async(self, ctx: PeerContext, message: Message) -> None:
        """Process the UPDATE message asynchronously.

        Same logic as sync - no async I/O needed for inbound processing.
        """
        update = cast(Update, message)
        parsed = update.data  # Already parsed by unpack_message
        self._number += 1

        log.debug(lazymsg('update.received number={number}', number=self._number), ctx.peer_id)

        # Process announces - pass action and nexthop explicitly
        # parsed.announces contains RoutedNLRI objects; extract the bare NLRI for RIB
        for routed in parsed.announces:
            nlri = routed.nlri
            ctx.neighbor.rib.incoming.update_cache(nlri, parsed.attributes, Action.ANNOUNCE, routed.nexthop)
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )

        # Process withdraws - use dedicated method
        for nlri in parsed.withdraws:
            ctx.neighbor.rib.incoming.update_cache_withdraw(nlri)
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )
