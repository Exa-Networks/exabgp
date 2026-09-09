"""Peer-visible ADD-PATH selection across RIB batches and session lifecycle."""

import pytest

from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route


IPV4 = (AFI.ipv4, SAFI.unicast)
IPV6 = (AFI.ipv6, SAFI.unicast)


def route(path_id: int, prefix: str = '192.0.2.0/24', origin: int = Origin.IGP) -> Route:
    address, mask = prefix.split('/')
    afi = AFI.ipv6 if ':' in address else AFI.ipv4
    cidr = CIDR.create_cidr(IP.pton(address), int(mask))
    nlri = INET.from_cidr(cidr, afi, SAFI.unicast, PathInfo.make_from_integer(path_id))
    attributes = AttributeCollection()
    attributes[Origin.ID] = Origin.from_int(origin)
    return Route(nlri, attributes, nexthop=IP.NoNextHop)


def announced(updates: list[UpdateCollection | RouteRefresh]) -> list[bytes]:
    return [
        entry.nlri.index() for update in updates if isinstance(update, UpdateCollection) for entry in update.announces
    ]


def withdrawn(updates: list[UpdateCollection | RouteRefresh]) -> list[bytes]:
    return [nlri.index() for update in updates if isinstance(update, UpdateCollection) for nlri in update.withdraws]


@pytest.mark.parametrize('cache', [True, False])
@pytest.mark.parametrize('grouped', [True, False])
def test_limit_persists_across_batches_and_replacements(cache: bool, grouped: bool) -> None:
    rib = OutgoingRIB(cache=cache, families={IPV4})
    first, second, third = route(1), route(2), route(3)
    rib.add_to_rib(first)
    assert announced(list(rib.updates(grouped, {IPV4: 2}))) == [first.nlri.index()]
    rib.add_to_rib(second)
    rib.add_to_rib(third)
    assert announced(list(rib.updates(grouped, {IPV4: 2}))) == [second.nlri.index()]
    replacement = route(1, origin=Origin.EGP)
    rib.add_to_rib(replacement)
    updates = list(rib.updates(grouped, {IPV4: 2}))
    assert announced(updates) == [first.nlri.index()]
    assert isinstance(updates[0], UpdateCollection)
    assert updates[0].attributes.index() == replacement.attributes.index()


@pytest.mark.parametrize('cache', [True, False])
def test_withdrawal_promotes_latest_suppressed_candidate(cache: bool) -> None:
    rib = OutgoingRIB(cache=cache, families={IPV4})
    first, second, third = route(1), route(2), route(3)
    for candidate in (first, second, third):
        rib.add_to_rib(candidate)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [first.nlri.index()]
    replacement = route(2, origin=Origin.EGP)
    rib.add_to_rib(replacement)
    assert list(rib.updates(True, {IPV4: 1})) == []
    rib.del_from_rib(third)
    assert list(rib.updates(True, {IPV4: 1})) == []
    rib.del_from_rib(first)
    updates = list(rib.updates(True, {IPV4: 1}))
    assert withdrawn(updates) == [first.nlri.index()]
    assert announced(updates) == [second.nlri.index()]
    assert isinstance(updates[0], UpdateCollection) and updates[0].withdraws
    assert isinstance(updates[-1], UpdateCollection)
    assert updates[-1].attributes.index() == replacement.attributes.index()


def test_refresh_retains_admitted_paths_and_honors_limit() -> None:
    """A replay re-sends what the peer already has, and no more of it than before."""
    cache = True
    rib = OutgoingRIB(cache=cache, families={IPV4})
    first, second = route(1), route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(second)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [first.nlri.index()]
    rib.resend(True)
    rib.resend(True)
    updates = list(rib.updates(True, {IPV4: 1}))
    assert set(announced(updates)) == {first.nlri.index()}
    assert isinstance(updates[0], RouteRefresh) and updates[0].reserved == RouteRefresh.start
    assert isinstance(updates[-1], RouteRefresh) and updates[-1].reserved == RouteRefresh.end
    rib.del_from_rib(first)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [second.nlri.index()]
    rib.resend(False)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [second.nlri.index()]


@pytest.mark.parametrize('grouped', [True, False])
def test_promoted_paths_follow_the_grouping_of_announced_ones(grouped: bool) -> None:
    """Backfilled paths are announces like any other and batch the same way."""
    rib = OutgoingRIB(cache=True, families={IPV4})
    first, second, third, fourth, fifth = (route(path_id) for path_id in (1, 2, 3, 4, 5))
    for candidate in (first, second, third, fourth, fifth):
        rib.add_to_rib(candidate)
    assert len(announced(list(rib.updates(grouped, {IPV4: 3})))) == 3

    rib.del_from_rib(first)
    rib.del_from_rib(second)
    updates = list(rib.updates(grouped, {IPV4: 3}))

    assert announced(updates) == [fourth.nlri.index(), fifth.nlri.index()]
    promotions = [update for update in updates if isinstance(update, UpdateCollection) and update.announces]
    assert len(promotions) == (1 if grouped else 2), 'grouped promotions share one UpdateCollection'


def test_promoted_paths_with_different_attributes_are_not_merged() -> None:
    """Grouping batches paths which share an attribute set, and only those."""
    rib = OutgoingRIB(cache=True, families={IPV4})
    advertised = [route(path_id) for path_id in (1, 2, 3)]
    same_attributes = route(4)
    other_attributes = route(5, origin=Origin.EGP)
    for candidate in advertised + [same_attributes, other_attributes]:
        rib.add_to_rib(candidate)
    assert len(announced(list(rib.updates(True, {IPV4: 3})))) == 3

    rib.del_from_rib(advertised[0])
    rib.del_from_rib(advertised[1])
    updates = list(rib.updates(True, {IPV4: 3}))

    assert announced(updates) == [same_attributes.nlri.index(), other_attributes.nlri.index()]
    promotions = [update for update in updates if isinstance(update, UpdateCollection) and update.announces]
    assert len(promotions) == 2, 'two attribute sets cannot share one UpdateCollection'
    assert [update.attributes.index() for update in promotions] == [
        same_attributes.attributes.index(),
        other_attributes.attributes.index(),
    ]


def test_withholding_and_promoting_a_path_are_both_reported(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """A configured route which does not reach the peer has to leave a trace somewhere.

    It is held rather than dropped and `show adj-rib out` still lists it, so the log is the
    only place an operator can find out the peer never received it.
    """
    from exabgp.rib import outgoing as outgoing_module

    reported: list[str] = []
    monkeypatch.setattr(outgoing_module.log, 'debug', lambda message, source: reported.append(str(message())))

    rib = OutgoingRIB(cache=True, families={IPV4})
    first, second = route(1), route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(second)
    list(rib.updates(True, {IPV4: 1}))
    assert [line for line in reported if 'paths_limit.withheld' in line], 'the held back path is not reported'

    reported.clear()
    rib.del_from_rib(first)
    list(rib.updates(True, {IPV4: 1}))
    assert [line for line in reported if 'paths_limit.promoted' in line], 'the promoted path is not reported'


def test_one_prefix_emptying_does_not_stop_another_being_promoted() -> None:
    """Withdrawing a prefix entirely must not abort promotion for the others in the batch.

    _promote_paths walks the prefixes a withdrawal touched. A prefix whose last path has
    gone no longer has a selection, and skipping it has to mean skipping that prefix, not
    leaving the loop: the prefixes after it in the batch still have a slot to fill.
    """
    rib = OutgoingRIB(cache=True, families={IPV4})
    lonely = route(1, '203.0.113.0/24')
    first, second = route(1), route(2)
    for candidate in (lonely, first, second):
        rib.add_to_rib(candidate)
    assert set(announced(list(rib.updates(True, {IPV4: 1})))) == {lonely.nlri.index(), first.nlri.index()}

    rib.del_from_rib(lonely)
    rib.del_from_rib(first)
    updates = list(rib.updates(True, {IPV4: 1}))

    assert announced(updates) == [second.nlri.index()], 'the surviving prefix was not backfilled'


def test_refresh_replays_every_path_when_no_limit_applies() -> None:
    """A family with no limit is not quietly capped when its routes are replayed."""
    rib = OutgoingRIB(cache=True, families={IPV4})
    first, second, third = route(1), route(2), route(3)
    for candidate in (first, second, third):
        rib.add_to_rib(candidate)
    assert len(announced(list(rib.updates(True, {})))) == 3

    rib.resend(False)
    replayed = announced(list(rib.updates(True, {})))

    assert set(replayed) == {first.nlri.index(), second.nlri.index(), third.nlri.index()}


def test_refresh_replays_the_route_not_just_its_nlri() -> None:
    """A replayed route carries the attributes and next-hop it was announced with."""
    rib = OutgoingRIB(cache=True, families={IPV4})
    only = route(1, origin=Origin.EGP)
    rib.add_to_rib(only)
    list(rib.updates(True, {IPV4: 2}))

    rib.resend(False)
    updates = [update for update in rib.updates(True, {IPV4: 2}) if isinstance(update, UpdateCollection)]

    assert len(updates) == 1
    assert updates[0].attributes.index() == only.attributes.index(), 'the replay lost its attributes'
    assert updates[0].announces[0].nexthop == only.nexthop, 'the replay lost its next-hop'


def test_limits_are_independent_per_prefix_and_family() -> None:
    rib = OutgoingRIB(cache=True, families={IPV4, IPV6})
    limits: dict[FamilyTuple, int] = {IPV4: 1, IPV6: 2}
    for path_id in (1, 2, 3):
        for prefix in ('192.0.2.0/24', '198.51.100.0/24', '2001:db8::/32'):
            rib.add_to_rib(route(path_id, prefix))
    updates = list(rib.updates(True, limits))
    expected = [route(1), route(1, '198.51.100.0/24'), route(1, '2001:db8::/32'), route(2, '2001:db8::/32')]
    assert set(announced(updates)) == {candidate.nlri.index() for candidate in expected}


def test_reset_rebuilds_selection_from_cached_candidates() -> None:
    rib = OutgoingRIB(cache=True, families={IPV4})
    first, second = route(1), route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(second)
    assert announced(list(rib.updates(True, {IPV4: 2}))) == [first.nlri.index(), second.nlri.index()]
    rib.reset()
    rib.resend(False)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [first.nlri.index()]
    rib.del_from_rib(first)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [second.nlri.index()]


@pytest.mark.parametrize('cache', [True, False])
def test_clear_discards_admissions_and_candidates(cache: bool) -> None:
    rib = OutgoingRIB(cache=cache, families={IPV4})
    rib.add_to_rib(route(1))
    rib.add_to_rib(route(2))
    list(rib.updates(True, {IPV4: 1}))
    rib.clear()
    third = route(3)
    rib.add_to_rib(third)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [third.nlri.index()]
    rib.del_from_rib(third)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == []


def test_pending_replacement_consumes_one_slot_not_two() -> None:
    """Redefining a path before it is sent is one path to the peer, not two.

    Both attribute sets go out, as they do for any redefinition, but the limit counts
    paths per prefix, so a second candidate must still fit beneath a limit of two.
    """
    rib = OutgoingRIB(cache=True, families={IPV4})
    first = route(1)
    replacement = route(1, origin=Origin.EGP)
    second = route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(replacement)
    rib.add_to_rib(second)
    updates = list(rib.updates(True, {IPV4: 2}))

    assert announced(updates) == [first.nlri.index(), second.nlri.index(), first.nlri.index()]
    attributes = [update.attributes.index() for update in updates if isinstance(update, UpdateCollection)]
    assert attributes == [first.attributes.index(), replacement.attributes.index()]
    assert len(rib._path_selection[IPV4][first.nlri.prefix_index()].advertised) == 2


def test_withdraw_announce_does_not_exceed_limit() -> None:
    rib = OutgoingRIB(cache=True, families={IPV4})
    first, second = route(1), route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(second)
    list(rib.updates(True, {IPV4: 1}))
    rib.del_from_rib(first)
    rib.add_to_rib(first)
    updates = list(rib.updates(True, {IPV4: 1}))
    assert withdrawn(updates) == [first.nlri.index()]
    assert announced(updates) == [first.nlri.index()]


def test_unlimited_family_does_not_suppress_successive_paths() -> None:
    rib = OutgoingRIB(cache=False, families={IPV4})
    for path_id in (1, 2, 3):
        candidate = route(path_id)
        rib.add_to_rib(candidate)
        assert announced(list(rib.updates(True, {IPV4: 0}))) == [candidate.nlri.index()]


def test_reset_stops_inflight_batch_and_discards_cache_disabled_state() -> None:
    rib = OutgoingRIB(cache=False, families={IPV4})
    first, second = route(1), route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(second)
    updates = rib.updates(False, {IPV4: 2})
    assert announced([next(updates)]) == [first.nlri.index()]
    rib.reset()
    assert list(updates) == []
    rib.resend(False)
    assert list(rib.updates(True, {IPV4: 1})) == []
    rib.add_to_rib(second)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [second.nlri.index()]


def test_withdraw_all_removes_suppressed_candidates() -> None:
    """Withdrawing everything takes the held paths with it, not only the sent ones."""
    rib = OutgoingRIB(cache=True, families={IPV4})
    first, second = route(1), route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(second)
    list(rib.updates(True, {IPV4: 1}))
    rib.withdraw()
    updates = list(rib.updates(True, {IPV4: 1}))
    assert withdrawn(updates) == [first.nlri.index()]
    assert announced(updates) == [], 'the held path is dropped, never promoted on the way out'
    rib.resend(False)
    assert list(rib.updates(True, {IPV4: 1})) == []


@pytest.mark.parametrize('limit', [0, 1])
def test_without_a_cache_a_limit_does_not_change_what_refresh_and_withdraw_do(limit: int) -> None:
    """`adj-rib-out false` means the same thing whether or not the family has a limit.

    Enforcement state used to stand in for the missing cache, so a family with a limit
    replayed and withdrew its paths while a family without one, in the same neighbour,
    did neither. The limit decides how many paths go out, not whether ExaBGP keeps a
    copy of them.
    """
    rib = OutgoingRIB(cache=False, families={IPV4})
    limits: dict[FamilyTuple, int] = {IPV4: limit}
    rib.add_to_rib(route(1))
    rib.add_to_rib(route(2))
    list(rib.updates(True, limits))

    rib.resend(True)
    assert announced(list(rib.updates(True, limits))) == [], 'nothing is cached, so nothing replays'
    rib.withdraw()
    assert withdrawn(list(rib.updates(True, limits))) == [], 'nothing is cached, so nothing withdraws'


def test_family_removal_discards_old_admission_state() -> None:
    rib = OutgoingRIB(cache=True, families={IPV4, IPV6})
    rib.add_to_rib(route(1))
    rib.add_to_rib(route(2))
    list(rib.updates(True, {IPV4: 1}))
    rib.delete_cached_family({IPV6})
    third = route(3)
    rib.add_to_rib(third)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == [third.nlri.index()]
    rib.del_from_rib(third)
    assert announced(list(rib.updates(True, {IPV4: 1}))) == []


@pytest.mark.parametrize('cache', [True, False])
def test_refresh_then_withdraw_promotes_only_after_withdrawal(cache: bool) -> None:
    rib = OutgoingRIB(cache=cache, families={IPV4})
    first, second = route(1), route(2)
    rib.add_to_rib(first)
    rib.add_to_rib(second)
    list(rib.updates(True, {IPV4: 1}))
    rib.resend(True)
    rib.del_from_rib(first)
    active = {first.nlri.index()}
    updates = list(rib.updates(True, {IPV4: 1}))
    for update in updates:
        if not isinstance(update, UpdateCollection):
            continue
        active.difference_update(nlri.index() for nlri in update.withdraws)
        active.update(entry.nlri.index() for entry in update.announces)
        assert len(active) <= 1
    assert active == {second.nlri.index()}
    assert withdrawn(updates) == [first.nlri.index()]
