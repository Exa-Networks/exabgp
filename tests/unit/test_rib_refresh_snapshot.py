"""A refresh replays the latest route the RIB holds, once, and never a withdrawn one.

`OutgoingRIB.resend()` copies the adj-rib-out into `_refresh_routes`, and `add_to_resend()`
appends one route to it directly. `_generate_updates` then folds that list into what goes
on the wire. Four decisions live in that fold and each of them is written down only as a
comment beside the code which makes it:

  - `{route.index(): route for route in self._refresh_routes}` deduplicates by route
    identity, so two `resend()` calls in one reactor cycle replay each prefix once rather
    than twice, and the last snapshot of a prefix is the one which is used.

  - `latest_routes.pop(route.index(), None)` replaces the cached route with whatever the
    operator queued for it since, whichever attribute bucket that landed in, and takes it
    out of the announce pass so it is not sent a second time.

  - a prefix with a pending withdraw is skipped, so a refresh cannot re-announce a route
    the operator has just taken away.

  - everything is taken and replaced in one go, so an `add_to_rib` or a `resend` arriving
    from the reactor between two yields belongs to the next batch and cannot change the
    collections being walked.

`add_to_resend` has no other test in this tree, and none of the four properties above did.
Ported from the 5.0 branch's `test_rib_refresh.py` and adapted: main's RIB stores `Route`
and yields `UpdateCollection`, where 5.0 stores `Change` and yields `Update`.
"""

from __future__ import annotations

from typing import Iterator
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import UpdateCollection
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route

FAMILY = (AFI.ipv4, SAFI.unicast)
PREFIX = '192.0.2.0/24'
OTHER_PREFIX = '198.51.100.0/24'
NEXT_HOP = '192.0.2.1'

ANNOUNCE = 'announce'
WITHDRAW = 'withdraw'


@pytest.fixture(autouse=True)
def _logger() -> Iterator[None]:
    """The RIB logs every insert and the logger is not initialised under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


@pytest.fixture(params=[False, True], ids=['ungrouped', 'grouped'])
def grouped(request: pytest.FixtureRequest) -> bool:
    grouping: bool = request.param
    return grouping


@pytest.fixture
def rib() -> OutgoingRIB:
    return OutgoingRIB(cache=True, families={FAMILY})


def route(med: int = 0, prefix: str = PREFIX) -> Route:
    address, mask = prefix.split('/')
    nlri = INET.from_cidr(CIDR.create_cidr(IP.pton(address), int(mask)), AFI.ipv4, SAFI.unicast)
    attributes = AttributeCollection()
    attributes.add(MED.from_int(med))
    return Route(nlri, attributes, nexthop=IP.from_string(NEXT_HOP))


def events(messages: Iterator[UpdateCollection | RouteRefresh]) -> list[tuple]:
    """One tuple per thing which reaches the wire, in the order it reaches it."""
    result: list[tuple] = []
    for message in messages:
        if isinstance(message, RouteRefresh):
            result.append((message.reserved, message.afi, message.safi))
            continue
        assert isinstance(message, UpdateCollection)
        med = message.attributes[MED.ID].med
        for routed in message.announces:
            result.append((str(routed.nlri), ANNOUNCE, med))
        for nlri in message.withdraws:
            result.append((str(nlri), WITHDRAW, med))
    return result


def cached(rib: OutgoingRIB) -> list[tuple[str, int]]:
    return [(str(entry.nlri), entry.attributes[MED.ID].med) for entry in rib.cached_routes([FAMILY])]


def seed(rib: OutgoingRIB, grouped: bool) -> Route:
    """One announced prefix, already flushed, so the adj-rib-out has something to replay."""
    queued = route()
    rib.add_to_rib(queued)
    assert events(rib.updates(grouped)) == [(PREFIX, ANNOUNCE, 0)]
    return queued


# ======================================================= the fold over _refresh_routes


def test_a_refresh_replays_the_latest_route_and_not_the_cached_one(rib: OutgoingRIB, grouped: bool) -> None:
    """Three attribute buckets for one prefix, and the wire sees the last of them once."""
    seed(rib, grouped)
    rib.resend(False)
    rib.resend(False)
    for med in (10, 20, 10):
        rib.add_to_rib(route(med))

    assert events(rib.updates(grouped)) == [(PREFIX, ANNOUNCE, 10)]
    assert cached(rib) == [(PREFIX, 10)]
    assert not rib.pending()
    assert events(rib.updates(grouped)) == []


def test_repeated_resend_replays_each_prefix_once(rib: OutgoingRIB, grouped: bool) -> None:
    """Two resends in one cycle are one replay: _refresh_routes is keyed on identity."""
    seed(rib, grouped)
    rib.resend(False)
    rib.resend(False)

    assert events(rib.updates(grouped)) == [(PREFIX, ANNOUNCE, 0)]
    assert cached(rib) == [(PREFIX, 0)]


def test_the_latest_explicit_snapshot_wins(rib: OutgoingRIB, grouped: bool) -> None:
    """add_to_resend has no other test: two snapshots of one prefix send the second."""
    rib.add_to_resend(route(10))
    rib.add_to_resend(route(20))

    assert events(rib.updates(grouped)) == [(PREFIX, ANNOUNCE, 20)]


def test_a_refresh_does_not_reannounce_a_pending_withdrawal(rib: OutgoingRIB, grouped: bool) -> None:
    original = seed(rib, grouped)
    rib.resend(False)
    rib.del_from_rib(original)

    assert events(rib.updates(grouped)) == [(PREFIX, WITHDRAW, 0)]
    assert cached(rib) == []


def test_a_withdrawal_discards_the_announcement_buckets_before_it(rib: OutgoingRIB, grouped: bool) -> None:
    seed(rib, grouped)
    rib.resend(False)
    rib.add_to_rib(route(10))
    replacement = route(20)
    rib.add_to_rib(replacement)
    rib.del_from_rib(replacement)

    assert events(rib.updates(grouped)) == [(PREFIX, WITHDRAW, 20)]
    assert cached(rib) == []


def test_a_withdrawal_is_kept_in_front_of_a_reannouncement(rib: OutgoingRIB, grouped: bool) -> None:
    """The order the operator asked for, which is also what frees a paths-limit slot."""
    original = seed(rib, grouped)
    rib.resend(False)
    rib.del_from_rib(original)
    rib.add_to_rib(route(10))

    assert events(rib.updates(grouped)) == [(PREFIX, WITHDRAW, 0), (PREFIX, ANNOUNCE, 10)]
    assert cached(rib) == [(PREFIX, 10)]


def test_a_refresh_does_not_consume_another_prefix_redefinition(rib: OutgoingRIB, grouped: bool) -> None:
    """Only the replayed prefix is folded; a prefix the refresh did not touch is untouched."""
    seed(rib, grouped)
    rib.resend(False)
    rib.add_to_rib(route(10))
    for med in (10, 20):
        rib.add_to_rib(route(med, OTHER_PREFIX))

    sent = events(rib.updates(grouped))

    assert sent[0] == (PREFIX, ANNOUNCE, 10)
    assert sorted(sent[1:]) == [(OTHER_PREFIX, ANNOUNCE, 10), (OTHER_PREFIX, ANNOUNCE, 20)]


# ============================================= the enhanced refresh markers around it


def test_the_markers_wrap_only_the_replayed_routes(rib: OutgoingRIB, grouped: bool) -> None:
    """RFC 7313: a route announced in the same cycle belongs outside the BoRR/EoRR pair."""
    seed(rib, grouped)
    rib.resend(True)
    rib.resend(True)
    rib.add_to_rib(route(10))
    rib.add_to_rib(route(30, OTHER_PREFIX))

    assert events(rib.updates(grouped)) == [
        (RouteRefresh.start, *FAMILY),
        (PREFIX, ANNOUNCE, 10),
        (RouteRefresh.end, *FAMILY),
        (OTHER_PREFIX, ANNOUNCE, 30),
    ]


# ============================================ the snapshot is taken in one go


@pytest.mark.parametrize('withdraw', [False, True], ids=[ANNOUNCE, WITHDRAW])
def test_a_mutation_after_the_first_yield_belongs_to_the_next_batch(
    rib: OutgoingRIB, grouped: bool, withdraw: bool
) -> None:
    """The reactor keeps feeding the RIB while the consumer is sending the batch."""
    seed(rib, grouped)
    rib.resend(True)
    replacement = route(10)
    rib.add_to_rib(replacement)
    batch = rib.updates(grouped)
    assert events(iter([next(batch)])) == [(RouteRefresh.start, *FAMILY)]

    if withdraw:
        rib.del_from_rib(replacement)
    else:
        rib.add_to_rib(route(20))
    rib.resend(True)
    rib.resend(True)

    assert events(batch) == [(PREFIX, ANNOUNCE, 10), (RouteRefresh.end, *FAMILY)]

    expected = [(RouteRefresh.start, *FAMILY)]
    if not withdraw:
        expected.append((PREFIX, ANNOUNCE, 20))
    expected.append((RouteRefresh.end, *FAMILY))
    if withdraw:
        expected.append((PREFIX, WITHDRAW, 10))

    assert events(rib.updates(grouped)) == expected
    assert cached(rib) == ([] if withdraw else [(PREFIX, 20)])


def test_a_mutation_after_a_replayed_update_does_not_change_the_snapshot(rib: OutgoingRIB, grouped: bool) -> None:
    seed(rib, grouped)
    rib.add_to_rib(route(0, OTHER_PREFIX))
    list(rib.updates(grouped))
    rib.resend(False)
    batch = rib.updates(grouped)
    first = events(iter([next(batch)]))

    rib.add_to_rib(route(20, OTHER_PREFIX))
    rib.resend(False)
    rest = events(batch)

    assert sorted(first + rest) == [(PREFIX, ANNOUNCE, 0), (OTHER_PREFIX, ANNOUNCE, 0)]
    assert sorted(events(rib.updates(grouped))) == [(PREFIX, ANNOUNCE, 0), (OTHER_PREFIX, ANNOUNCE, 20)]


# ================================================ with no adj-rib-out there is nothing


def test_a_resend_without_a_cache_invents_no_route(rib: OutgoingRIB, grouped: bool) -> None:
    """A refresh replays the adj-rib-out. With none, it replays nothing, markers aside."""
    rib.cache = False
    seed(rib, grouped)
    rib.resend(False)
    rib.resend(False)
    assert events(rib.updates(grouped)) == []
    assert cached(rib) == []

    rib.resend(True)
    assert events(rib.updates(grouped)) == [(RouteRefresh.start, *FAMILY), (RouteRefresh.end, *FAMILY)]

    for med in (10, 20):
        rib.add_to_rib(route(med))
    rib.resend(False)

    assert sorted(events(rib.updates(grouped))) == [(PREFIX, ANNOUNCE, 10), (PREFIX, ANNOUNCE, 20)]
    assert cached(rib) == []
