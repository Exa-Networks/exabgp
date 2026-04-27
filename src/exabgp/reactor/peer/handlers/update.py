"""UpdateHandler for processing received BGP UPDATE messages.

This handler processes UPDATE messages and stores NLRIs in the incoming RIB.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Generator, cast

from exabgp.bgp.message import Message, Update
from exabgp.environment import getenv
from exabgp.logger import lazyformat, lazymsg, log
from exabgp.reactor.peer.handlers.base import MessageHandler
from exabgp.rib.route import Route

if TYPE_CHECKING:
    from exabgp.bgp.message.update.nlri.nlri import NLRI
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

    def _audit_announce(self, ctx: PeerContext, nlri: NLRI) -> None:
        """If PATHS-LIMIT auditing is on, count this path and warn on violation."""
        advertised = ctx.negotiated.advertised_paths_limit
        if not advertised:
            return
        if not getenv().bgp.paths_limit_audit:
            return
        family = nlri.family().afi_safi()
        limit = advertised.get(family, 0)
        if limit <= 0:
            return
        prefix_index = nlri.prefix_index()
        count = ctx.neighbor.rib.incoming.track_path(family, prefix_index)
        if count > limit and ctx.neighbor.rib.incoming.mark_warned(family, prefix_index):
            log.warning(
                lazymsg(
                    'rib.paths_limit.peer_violation peer={peer} family={family} prefix={prefix} limit={limit} received={count}',
                    peer=ctx.neighbor.session.peer_address,
                    family=family,
                    prefix=nlri,
                    limit=limit,
                    count=count,
                ),
                'rib',
            )

    def _audit_withdraw(self, ctx: PeerContext, nlri: NLRI) -> None:
        """Decrement audit counter for a withdrawn NLRI (no-op if untracked)."""
        if not ctx.negotiated.advertised_paths_limit:
            return
        family = nlri.family().afi_safi()
        ctx.neighbor.rib.incoming.untrack_path(family, nlri.prefix_index())

    def handle(self, ctx: PeerContext, message: Message) -> Generator[Message, None, None]:
        """Process the UPDATE message synchronously.

        Stores all NLRIs in the incoming RIB cache.
        """
        update = cast(Update, message)
        parsed = update.data  # Already parsed by unpack_message
        self._number += 1

        log.debug(lazymsg('update.received number={number}', number=self._number), ctx.peer_id)

        # Process announces - create Route objects for cache
        # parsed.announces contains RoutedNLRI objects; extract the bare NLRI for RIB
        for routed in parsed.announces:
            nlri = routed.nlri
            route = Route(nlri, parsed.attributes, nexthop=routed.nexthop)
            ctx.neighbor.rib.incoming.update_cache(route)
            self._audit_announce(ctx, nlri)
            ctx.stats['receive-prefixes'] += 1
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )

        # Process withdraws - use dedicated method
        for nlri in parsed.withdraws:
            ctx.neighbor.rib.incoming.update_cache_withdraw(nlri)
            self._audit_withdraw(ctx, nlri)
            ctx.stats['receive-withdraws'] += 1
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

        # Process announces - create Route objects for cache
        # parsed.announces contains RoutedNLRI objects; extract the bare NLRI for RIB
        for routed in parsed.announces:
            nlri = routed.nlri
            route = Route(nlri, parsed.attributes, nexthop=routed.nexthop)
            ctx.neighbor.rib.incoming.update_cache(route)
            self._audit_announce(ctx, nlri)
            ctx.stats['receive-prefixes'] += 1
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )

        # Process withdraws - use dedicated method
        for nlri in parsed.withdraws:
            ctx.neighbor.rib.incoming.update_cache_withdraw(nlri)
            self._audit_withdraw(ctx, nlri)
            ctx.stats['receive-withdraws'] += 1
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )
