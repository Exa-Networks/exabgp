"""Refresh snapshots must reflect the latest queued route without replaying it twice."""

from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action, Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.change import Change
from exabgp.rib.outgoing import OutgoingRIB


FAMILY = (AFI.ipv4, SAFI.unicast)
PREFIX = '192.0.2.0/24'
OTHER_PREFIX = '198.51.100.0/24'


@pytest.fixture(params=[False, True], ids=['ungrouped', 'grouped'])
def grouped(request):
    return request.param


@pytest.fixture
def rib(monkeypatch):
    monkeypatch.setattr(log, 'debug', Mock())
    return OutgoingRIB(cache=True, families={FAMILY})


def route(med=0, prefix=PREFIX):
    address, mask = prefix.split('/')
    nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    nlri.cidr = CIDR(IP.pton(address), int(mask))
    nlri.nexthop = IP.create('192.0.2.1')
    attributes = Attributes()
    attributes.add(MED(med))
    return Change(nlri, attributes)


def events(messages):
    result = []
    for message in messages:
        if isinstance(message, RouteRefresh):
            result.append((message.reserved, message.afi, message.safi))
        else:
            assert isinstance(message, Update)
            result.extend((nlri.cidr.prefix(), nlri.action, message.attributes[MED.ID].med) for nlri in message.nlris)
    return result


def seed(rib, grouped):
    change = route()
    rib.add_to_rib(change)
    assert events(rib.updates(grouped)) == [(PREFIX, Action.ANNOUNCE, 0)]
    return change


def cached(rib):
    return [(change.nlri.cidr.prefix(), change.attributes[MED.ID].med) for change in rib.cached_changes()]


def test_refresh_folds_latest_replacement_from_all_attribute_buckets(rib, grouped):
    seed(rib, grouped)
    rib.resend(False)
    rib.resend(False)
    for med in (10, 20, 10):
        rib.add_to_rib(route(med))

    assert events(rib.updates(grouped)) == [(PREFIX, Action.ANNOUNCE, 10)]
    assert cached(rib) == [(PREFIX, 10)]
    assert not rib.pending()
    assert events(rib.updates(grouped)) == []


def test_repeated_resend_replays_each_identity_once(rib, grouped):
    seed(rib, grouped)
    rib.resend(False)
    rib.resend(False)

    assert events(rib.updates(grouped)) == [(PREFIX, Action.ANNOUNCE, 0)]
    assert cached(rib) == [(PREFIX, 0)]


def test_latest_explicit_refresh_snapshot_wins(rib, grouped):
    rib.add_to_resend(route(10))
    rib.add_to_resend(route(20))

    assert events(rib.updates(grouped)) == [(PREFIX, Action.ANNOUNCE, 20)]


def test_refresh_does_not_reannounce_pending_withdrawal(rib, grouped):
    original = seed(rib, grouped)
    rib.resend(False)
    rib.del_from_rib(original)

    assert events(rib.updates(grouped)) == [(PREFIX, Action.WITHDRAW, 0)]
    assert cached(rib) == []


def test_refresh_withdrawal_discards_older_announcement_buckets(rib, grouped):
    seed(rib, grouped)
    rib.resend(False)
    rib.add_to_rib(route(10))
    replacement = route(20)
    rib.add_to_rib(replacement)
    rib.del_from_rib(replacement)

    assert events(rib.updates(grouped)) == [(PREFIX, Action.WITHDRAW, 20)]
    assert cached(rib) == []


def test_refresh_preserves_withdrawal_before_reannouncement(rib, grouped):
    original = seed(rib, grouped)
    rib.resend(False)
    rib.del_from_rib(original)
    rib.add_to_rib(route(10))

    assert events(rib.updates(grouped)) == [
        (PREFIX, Action.WITHDRAW, 0),
        (PREFIX, Action.ANNOUNCE, 10),
    ]
    assert cached(rib) == [(PREFIX, 10)]


def test_enhanced_refresh_wraps_only_folded_routes(rib, grouped):
    seed(rib, grouped)
    rib.resend(True)
    rib.resend(True)
    rib.add_to_rib(route(10))
    rib.add_to_rib(route(30, OTHER_PREFIX))

    assert events(rib.updates(grouped)) == [
        (RouteRefresh.start, *FAMILY),
        (PREFIX, Action.ANNOUNCE, 10),
        (RouteRefresh.end, *FAMILY),
        (OTHER_PREFIX, Action.ANNOUNCE, 30),
    ]


@pytest.mark.parametrize('withdraw', [False, True], ids=['announce', 'withdraw'])
def test_mutations_after_borr_belong_to_next_batch(rib, grouped, withdraw):
    seed(rib, grouped)
    rib.resend(True)
    replacement = route(10)
    rib.add_to_rib(replacement)
    batch = rib.updates(grouped)
    assert events([next(batch)]) == [(RouteRefresh.start, *FAMILY)]

    if withdraw:
        rib.del_from_rib(replacement)
    else:
        rib.add_to_rib(route(20))
    rib.resend(True)
    rib.resend(True)

    assert events(batch) == [(PREFIX, Action.ANNOUNCE, 10), (RouteRefresh.end, *FAMILY)]
    expected = [(RouteRefresh.start, *FAMILY)]
    if not withdraw:
        expected.append((PREFIX, Action.ANNOUNCE, 20))
    expected.append((RouteRefresh.end, *FAMILY))
    if withdraw:
        expected.append((PREFIX, Action.WITHDRAW, 10))
    assert events(rib.updates(grouped)) == expected
    assert cached(rib) == ([] if withdraw else [(PREFIX, 20)])


def test_mutations_after_refresh_update_do_not_change_snapshot(rib, grouped):
    seed(rib, grouped)
    rib.add_to_rib(route(0, OTHER_PREFIX))
    list(rib.updates(grouped))
    rib.resend(False)
    batch = rib.updates(grouped)
    assert events([next(batch)]) == [(PREFIX, Action.ANNOUNCE, 0)]

    rib.add_to_rib(route(20, OTHER_PREFIX))
    rib.resend(False)
    assert events(batch) == [(OTHER_PREFIX, Action.ANNOUNCE, 0)]
    assert events(rib.updates(grouped)) == [
        (PREFIX, Action.ANNOUNCE, 0),
        (OTHER_PREFIX, Action.ANNOUNCE, 20),
    ]


def test_refresh_does_not_consume_other_route_redefinitions(rib, grouped):
    seed(rib, grouped)
    rib.resend(False)
    rib.add_to_rib(route(10))
    for med in (10, 20):
        rib.add_to_rib(route(med, OTHER_PREFIX))

    assert events(rib.updates(grouped)) == [
        (PREFIX, Action.ANNOUNCE, 10),
        (OTHER_PREFIX, Action.ANNOUNCE, 10),
        (OTHER_PREFIX, Action.ANNOUNCE, 20),
    ]


def test_cache_disabled_resend_does_not_invent_routes(rib, grouped):
    rib.cache = False
    seed(rib, grouped)
    rib.resend(False)
    rib.resend(False)
    assert events(rib.updates(grouped)) == []
    assert cached(rib) == []

    rib.resend(True)
    assert events(rib.updates(grouped)) == [
        (RouteRefresh.start, *FAMILY),
        (RouteRefresh.end, *FAMILY),
    ]
    for med in (10, 20):
        rib.add_to_rib(route(med))
    rib.resend(False)
    assert events(rib.updates(grouped)) == [
        (PREFIX, Action.ANNOUNCE, 10),
        (PREFIX, Action.ANNOUNCE, 20),
    ]
    assert cached(rib) == []
