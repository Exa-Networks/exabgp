"""store.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.protocol.family import FamilyTuple
from exabgp.rib.cache import Cache

if TYPE_CHECKING:
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.rib.route import Route


class IncomingRIB(Cache):
    # The audit asks one question of each prefix: did the peer send more paths than the
    # limit we advertised. One path beyond the limit answers it, so that is as far as the
    # set has to grow. Without this a peer which ignores the limit, the only peer the audit
    # exists to catch, is also the one which decides how much memory the audit costs.
    AUDIT_PATHS_HEADROOM = 1
    # RFC 8955 6: the flow specifications a peer sent which are not feasible yet, held
    # until a unicast route makes them so. A peer decides how many it sends, so they are
    # capped per family; one past the cap is dropped, and the peer must send it again
    PENDING_FLOWS_MAX = 65536

    _path_sets: dict[FamilyTuple, dict[bytes, set[bytes]]]
    _path_warned: set[tuple[FamilyTuple, bytes]]
    _end_of_rib: set[FamilyTuple]
    # RFC 7313 4: per family, the routes a BoRR marked stale and nothing has re-sent since.
    # A subset of what the cache and the prefix-limit count hold, so they bound it
    _stale: dict[FamilyTuple, set[bytes]]
    # RFC 4486 4: per limited family, the routes the peer holds with us.  Kept apart from
    # the cache, which adj-rib-in can turn off, and bounded by the limit: the route which
    # takes a family past it ends the session
    _prefixes: dict[FamilyTuple, set[bytes]]
    _pending_flows: dict[FamilyTuple, dict[bytes, Route]]
    # RFC 4724 4.2: the families whose routes are stale because the peer's Graceful Restart
    # session was lost, until its End-of-RIB, its new OPEN or its Restart Time ends them
    _restarting: set[FamilyTuple]

    def __init__(self, cache: bool, families: set[FamilyTuple], enabled: bool = True) -> None:
        Cache.__init__(self, cache, families, enabled)
        self._path_sets = {}
        self._path_warned = set()
        self._end_of_rib = set()
        self._stale = {}
        self._prefixes = {}
        self._pending_flows = {}
        self._restarting = set()

    # back to square one, all the routes are removed
    def clear(self) -> None:
        self.clear_cache()
        self._pending_flows = {}
        self._restarting = set()
        self._path_sets = {}
        self._path_warned = set()
        self._end_of_rib = set()
        self._stale = {}
        self._prefixes = {}

    def update_cache(self, route: Route) -> None:
        Cache.update_cache(self, route)
        stale = self._stale.get(route.nlri.family().afi_safi())
        if stale:
            stale.discard(route.index())

    def update_cache_withdraw(self, nlri: NLRI) -> None:
        Cache.update_cache_withdraw(self, nlri)
        stale = self._stale.get(nlri.family().afi_safi())
        if stale:
            stale.discard(self._make_index(nlri))

    def mark_stale(self, family: FamilyTuple) -> None:
        """A BoRR: every route of the family held now is stale until the peer sends it again.

        "Held" is the cache and the prefix-limit count together: the count is kept with
        adj-rib-in off, when the cache is empty, and the EoRR has to release it too.
        """
        self._stale[family] = set(self._seen.get(family, {})) | self._prefixes.get(family, set())

    def purge_stale(self, family: FamilyTuple) -> list[Route] | None:
        """An EoRR: remove what is still stale, or None when no BoRR came before it."""
        stale = self._stale.pop(family, None)
        if stale is None:
            return None
        held = self._seen.get(family, {})
        purged = [held.pop(index) for index in stale if index in held]
        assert len(purged) <= len(stale)
        # the peer no longer holds these with us, so the prefix-limit stops counting them
        counted = self._prefixes.get(family)
        if counted:
            counted.difference_update(stale)
        return purged

    def record_end_of_rib(self, family: FamilyTuple) -> None:
        # bounded by the families negotiated, a peer cannot grow it past those
        self._end_of_rib.add(family)

    def has_end_of_rib(self, family: FamilyTuple) -> bool:
        return family in self._end_of_rib

    def reset(self) -> None:
        pass

    def auditing(self) -> bool:
        """True when a path has been tracked, so a withdrawal has something to release.

        Announces are tracked only while the audit is enabled, withdrawals release what
        was tracked whether it still is or not: turning the audit off has to drain the
        state rather than strand it. Asking what is held answers both, and costs a dict
        truthiness test instead of packing a prefix and a path index for every withdrawn
        NLRI on a neighbour which never audited anything.
        """
        return bool(self._path_sets)

    def track_path(self, family: FamilyTuple, prefix_index: bytes, path_index: bytes, limit: int) -> int:
        """Record one received path and return how many this prefix now holds.

        The count saturates at one past `limit`. Past that point the audit has already
        warned about the prefix and the exact number would only cost memory, so a peer
        which keeps sending paths stops being able to grow this set. The trade is that
        once a prefix has saturated, withdrawals can take the count below what the peer
        actually holds, and a later violation on that prefix may go unreported.
        """
        assert limit > 0, 'a prefix is only audited against a limit we advertised'

        per_family = self._path_sets.setdefault(family, {})
        paths = per_family.setdefault(prefix_index, set())
        capacity = limit + self.AUDIT_PATHS_HEADROOM
        if len(paths) >= capacity and path_index not in paths:
            return len(paths)
        paths.add(path_index)
        assert len(paths) <= capacity, 'the audit set is bounded by the limit'
        return len(paths)

    def untrack_path(self, family: FamilyTuple, prefix_index: bytes, path_index: bytes) -> None:
        per_family = self._path_sets.get(family)
        if per_family is None:
            return
        paths = per_family.get(prefix_index)
        if paths is None:
            return
        paths.discard(path_index)
        if not paths:
            per_family.pop(prefix_index, None)
            self._path_warned.discard((family, prefix_index))

    def path_count(self, family: FamilyTuple, prefix_index: bytes) -> int:
        per_family = self._path_sets.get(family)
        if per_family is None:
            return 0
        paths = per_family.get(prefix_index)
        return len(paths) if paths else 0

    def mark_warned(self, family: FamilyTuple, prefix_index: bytes) -> bool:
        key = (family, prefix_index)
        if key in self._path_warned:
            return False
        self._path_warned.add(key)
        return True

    def count_prefix(self, nlri: NLRI) -> int:
        """Record a route the peer announced, and return how many its family now holds."""
        prefixes = self._prefixes.setdefault(nlri.family().afi_safi(), set())
        prefixes.add(self._make_index(nlri))
        return len(prefixes)

    def uncount_prefix(self, nlri: NLRI) -> None:
        prefixes = self._prefixes.get(nlri.family().afi_safi())
        if prefixes:
            prefixes.discard(self._make_index(nlri))

    def hold_pending_flow(self, route: Route) -> bool:
        """Keep a flow specification which is not feasible yet, False when the cap is reached."""
        family = route.nlri.family().afi_safi()
        pending = self._pending_flows.setdefault(family, {})
        index = route.index()
        if index not in pending and len(pending) >= self.PENDING_FLOWS_MAX:
            return False
        pending[index] = route
        assert len(pending) <= self.PENDING_FLOWS_MAX, 'the pending flows of a family are capped'
        return True

    def discard_pending_flow(self, nlri: NLRI) -> Route | None:
        """Forget a pending flow specification, the peer withdrew it or it became feasible."""
        family = nlri.family().afi_safi()
        return self._pending_flows.get(family, {}).pop(self._make_index(nlri), None)

    def pending_flows(self, family: FamilyTuple) -> list[Route]:
        """The flow specifications of the family held back as not feasible, a snapshot."""
        return list(self._pending_flows.get(family, {}).values())

    def retain_for_restart(self, families: list[FamilyTuple]) -> list[Route]:
        """RFC 4724 4.2: the peer's session was lost, keep its routes of these families as stale.

        A route still stale from before, the peer restarting again without having sent it,
        is deleted rather than retained once more ("to deal with possible consecutive
        restarts"), and returned so the caller can say it is gone.
        """
        deleted: list[Route] = []
        for family in families:
            deleted.extend(self.purge_stale(family) or [])
            self.mark_stale(family)
            self._restarting.add(family)
        assert self._restarting.issubset(self._stale.keys()), 'a restarting family is a stale one'
        return deleted

    def restarting_families(self) -> set[FamilyTuple]:
        return set(self._restarting)

    def end_restart(self, family: FamilyTuple) -> list[Route]:
        """The stale routes of a restarting family go: its End-of-RIB, or its new OPEN said so."""
        if family not in self._restarting:
            return []
        self._restarting.discard(family)
        return self.purge_stale(family) or []

    def expire_restart(self) -> list[Route]:
        """RFC 4724 4.2: the Restart Time passed with no new session, every stale route goes."""
        expired: list[Route] = []
        for family in list(self._restarting):
            expired.extend(self.end_restart(family))
        assert not self._restarting, 'every restarting family was ended'
        return expired

    def start_session(self, kept: set[FamilyTuple]) -> None:
        """A new session: forget what the last one held, except the families a restart retains."""
        assert kept.issubset(self._restarting), 'only a restarting family is kept into a new session'
        self._seen = {family: routes for family, routes in self._seen.items() if family in kept}
        self._stale = {family: stale for family, stale in self._stale.items() if family in kept}
        self._prefixes = {family: counted for family, counted in self._prefixes.items() if family in kept}
        self._restarting = set(kept)
        self._pending_flows = {}
        self._path_sets = {}
        self._path_warned = set()
        self._end_of_rib = set()
