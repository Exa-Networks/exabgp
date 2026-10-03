"""A withdrawal is not refused for a `next-hop self` this session can not resolve.

`withdraw route 2001:db8::/32 next-hop self` on an IPv4 session raised TypeError resolving
self, so the helper was answered an error and the route stayed announced. A withdrawal
sends no next-hop: 5.0 withdrew it. Found by qa/bin/test_old_commands.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api import API
from exabgp.rib import RIB

NEIGHBOR = """
neighbor 127.0.0.1 {
    router-id 10.0.0.2;
    local-address 127.0.0.1;
    local-as 65533;
    peer-as 65533;
    family { ipv4 unicast; ipv6 unicast; }
}
"""


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def test_an_ipv6_withdrawal_with_next_hop_self_on_an_ipv4_session_is_withdrawn() -> None:
    configuration = Configuration([NEIGHBOR], text=True)
    assert configuration.reload(), str(configuration.error)
    name = next(iter(configuration.neighbors))
    (route,) = API(MagicMock()).api_route('withdraw route 2001:db8::/32 next-hop self')

    assert configuration.withdraw_route([name], route)
