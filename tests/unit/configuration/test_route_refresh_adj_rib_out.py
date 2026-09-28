"""Test route-refresh capability auto-enables adj-rib-out.

When route-refresh is enabled, adj-rib-out must be enabled for it to function.
Reading a neighbor (grammar/tree/resolve.py, neighbor_settings) auto-enables adj-rib-out
when route-refresh is configured.

See: https://github.com/Exa-Networks/exabgp/issues/1151
"""

from __future__ import annotations

from exabgp.bgp.neighbor.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration

NEIGHBOR = """\
neighbor 192.168.1.1 {
    router-id 10.0.0.1;
    local-address 192.168.1.2;
    local-as 65000;
    peer-as 65001;
    adj-rib-out %s;
    capability {
        route-refresh %s;
    }
}
"""


def _neighbor(adj_rib_out: str, route_refresh: str) -> Neighbor:
    configuration = Configuration([NEIGHBOR % (adj_rib_out, route_refresh)], text=True)
    assert configuration.reload(), str(configuration.error)
    (neighbor,) = configuration.neighbors.values()
    return neighbor


class TestRouteRefreshAdjRibOut:
    """Test that route-refresh capability auto-enables adj-rib-out."""

    def test_adj_rib_out_auto_enabled_when_route_refresh_enabled(self) -> None:
        """When route-refresh is enabled and adj-rib-out is False, auto-enable it."""
        neighbor = _neighbor('false', 'enable')

        assert neighbor.capability.route_refresh == 2  # REFRESH.NORMAL
        assert neighbor.adj_rib_out is True

    def test_adj_rib_out_unchanged_when_already_enabled(self) -> None:
        """When adj-rib-out is already True, it stays True."""
        neighbor = _neighbor('true', 'enable')

        assert neighbor.adj_rib_out is True

    def test_adj_rib_out_unchanged_when_route_refresh_disabled(self) -> None:
        """When route-refresh is disabled, adj-rib-out is not changed."""
        neighbor = _neighbor('false', 'disable')

        assert neighbor.capability.route_refresh == 0
        assert neighbor.adj_rib_out is False

    def test_route_refresh_required_also_enables_adj_rib_out(self) -> None:
        """A required route-refresh is enabled too, so it also auto-enables adj-rib-out."""
        neighbor = _neighbor('false', 'require')

        assert neighbor.capability.route_refresh == 2  # REFRESH.NORMAL
        assert neighbor.adj_rib_out is True
