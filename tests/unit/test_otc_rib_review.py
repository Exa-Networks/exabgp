"""OTC policy regressions for refresh replacements."""

import pytest

from exabgp.rib import RIB
from test_otc_routes import configured, route, sent
from test_paths_limit_rib import IPV4


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})


@pytest.mark.parametrize('limit', [0, 1])
def test_duplicate_refresh_does_not_reannounce_otc_blocked_replacement(limit):
    neighbor, negotiated = configured('customer')
    rib = neighbor.rib.outgoing
    original = route()
    rib.add_to_rib(original)
    assert [item.nlri for update in sent(rib, negotiated, {IPV4: limit}) for item in update.announces] == [
        original.nlri
    ]

    rib.resend(False)
    rib.resend(False)
    rib.add_to_rib(route('65009'))
    updates = sent(rib, negotiated, {IPV4: limit})

    assert [(update.announces, update.withdraws) for update in updates] == [([], [original.nlri])]
    rib.resend(False)
    assert sent(rib, negotiated, {IPV4: limit}) == []
