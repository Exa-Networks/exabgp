"""UpdateHandler for processing received BGP UPDATE messages.

This handler processes UPDATE messages and stores NLRIs in the incoming RIB.
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Generator, cast

from exabgp.bgp.message import Message, Update
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.eor import EOR
from exabgp.environment import getenv
from exabgp.logger import lazyformat, lazymsg, log
from exabgp.reactor.peer.handlers.base import MessageHandler
from exabgp.protocol.family import SAFI
from exabgp.rib.route import Route

if TYPE_CHECKING:
    from exabgp.bgp.message.update.collection import UpdateCollection
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
        return message.ID == Message.CODE.UPDATE

    def _audit_announce(self, ctx: PeerContext, nlri: NLRI) -> None:
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
        path_index = nlri.index()
        count = ctx.neighbor.rib.incoming.track_path(family, prefix_index, path_index, limit)
        if count > limit and ctx.neighbor.rib.incoming.mark_warned(family, prefix_index):
            log.warning(
                lazymsg(
                    'rib.paths_limit.peer_violation peer={peer} family={family} prefix={prefix} limit={limit} received={count} tracking=capped',
                    peer=ctx.neighbor.session.peer_address,
                    family=family,
                    prefix=nlri,
                    limit=limit,
                    count=count,
                ),
                'rib',
            )

    def _limit_announce(self, ctx: PeerContext, nlri: NLRI) -> None:
        """RFC 4486 4: past the family's prefix-limit, end the session with Cease (6, 1)."""
        limits = ctx.neighbor.prefix_limit
        if not limits:
            return
        family = nlri.family().afi_safi()
        limit = limits.get(family)
        if limit is None:
            return
        count = ctx.neighbor.rib.incoming.count_prefix(nlri)
        # Not only one past: a reload applies a lower limit live, to a peer already over it
        if count <= limit:
            return
        raise Notify(
            *Notify.MAXIMUM_NUMBER_OF_PREFIXES_REACHED,
            f'more than {limit} routes received for {family[0]} {family[1]}',
            # the MAY of section 4: <AFI, SAFI> and the upper bound, as in its Figure 1
            data=pack('!HBI', family[0].value, family[1].value, limit),
        )

    def _limit_withdraw(self, ctx: PeerContext, nlri: NLRI) -> None:
        if ctx.neighbor.prefix_limit:
            ctx.neighbor.rib.incoming.uncount_prefix(nlri)

    def _audit_withdraw(self, ctx: PeerContext, nlri: NLRI) -> None:
        if not ctx.negotiated.advertised_paths_limit:
            return
        incoming = ctx.neighbor.rib.incoming
        if not incoming.auditing():
            return
        family = nlri.family().afi_safi()
        incoming.untrack_path(family, nlri.prefix_index(), nlri.index())

    def _end_of_rib(self, ctx: PeerContext, eor: EOR) -> None:
        # RFC 7313 section 4 needs to know an End-of-RIB was received, per family, for the
        # Graceful Restart rule on BoRR
        family = (eor.afi, eor.safi)
        # EOR.from_body accepts an End-of-RIB for any family: one the session did not
        # negotiate means nothing, and recording it let a peer grow the record without bound
        if family not in ctx.negotiated.families:
            log.warning(
                lazymsg('eor.ignored reason=family-not-negotiated afi={a} safi={s}', a=family[0], s=family[1]),
                ctx.peer_id,
            )
            return
        ctx.neighbor.rib.incoming.record_end_of_rib(family)
        # RFC 4724 4.2: what a restarted peer did not send again goes with its End-of-RIB
        stale = ctx.neighbor.rib.incoming.end_restart(family)
        if stale:
            log.info(lazymsg('graceful-restart.end-of-rib removed={n}', n=len(stale)), ctx.peer_id)
            ctx.proto.peer.tell_api_withdrawn(stale, ctx.negotiated)
        log.debug(lazymsg('eor.received afi={a} safi={s}', a=family[0], s=family[1]), ctx.peer_id)

    @staticmethod
    def _membership(ctx: PeerContext, parsed: UpdateCollection) -> None:
        # RFC 4684 5: the Route Target membership of the peer decides which VPN routes it is
        # sent, so a change of it offers the peer those routes again
        if not ctx.neighbor.route_target_filter:
            return
        changed = [routed.nlri for routed in parsed.announces] + list(parsed.withdraws)
        if any(nlri.safi == SAFI.rtc for nlri in changed):
            ctx.neighbor.rib.outgoing.membership_changed()

    def handle(self, ctx: PeerContext, message: Message) -> Generator[Message, None, None]:
        """Process the UPDATE message synchronously.

        Stores all NLRIs in the incoming RIB cache.
        """
        assert self.can_handle(message), 'the peer loop only hands over what can_handle accepted'
        # the one decoder registered for UPDATE is Update's, and it returns an Update
        update = cast(Update, message)
        if update.IS_EOR:
            self._end_of_rib(ctx, cast(EOR, update))
            return
        parsed = update.data  # Already parsed by unpack_message
        self._number += 1

        log.debug(lazymsg('update.received number={number}', number=self._number), ctx.peer_id)

        # Process announces - create Route objects for cache
        # parsed.announces contains RoutedNLRI objects; extract the bare NLRI for RIB
        for routed in parsed.announces:
            nlri = routed.nlri
            self._limit_announce(ctx, nlri)
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
            self._limit_withdraw(ctx, nlri)
            ctx.stats['receive-withdraws'] += 1
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )

        self._membership(ctx, parsed)

        return
        yield  # Make this a generator

    async def handle_async(self, ctx: PeerContext, message: Message) -> None:
        """Process the UPDATE message asynchronously.

        Same logic as sync - no async I/O needed for inbound processing.
        """
        assert self.can_handle(message), 'the peer loop only hands over what can_handle accepted'
        # the one decoder registered for UPDATE is Update's, and it returns an Update
        update = cast(Update, message)
        if update.IS_EOR:
            self._end_of_rib(ctx, cast(EOR, update))
            return
        parsed = update.data  # Already parsed by unpack_message
        self._number += 1

        log.debug(lazymsg('update.received number={number}', number=self._number), ctx.peer_id)

        # Process announces - create Route objects for cache
        # parsed.announces contains RoutedNLRI objects; extract the bare NLRI for RIB
        for routed in parsed.announces:
            nlri = routed.nlri
            self._limit_announce(ctx, nlri)
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
            self._limit_withdraw(ctx, nlri)
            ctx.stats['receive-withdraws'] += 1
            log.debug(
                lazyformat('update.nlri number=%d nlri=' % self._number, nlri, str),
                ctx.peer_id,
            )

        self._membership(ctx, parsed)
