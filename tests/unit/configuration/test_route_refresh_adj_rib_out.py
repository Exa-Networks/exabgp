"""Test route-refresh capability auto-enables adj-rib-out.

When route-refresh is enabled, adj-rib-out must be enabled for it to function.
ParseNeighbor._post_capa_rr auto-enables adj-rib-out when route-refresh is configured.

See: https://github.com/Exa-Networks/exabgp/issues/1151
"""

from exabgp.bgp.neighbor.neighbor import Neighbor
from exabgp.protocol.ip import IP


class TestRouteRefreshAdjRibOut:
    """Test that route-refresh capability auto-enables adj-rib-out."""

    def _create_neighbor(self) -> Neighbor:
        """Create a minimal Neighbor for testing."""
        neighbor = Neighbor()
        neighbor.session.peer_address = IP.from_string('192.168.1.1')
        return neighbor

    def test_adj_rib_out_auto_enabled_when_route_refresh_enabled(self) -> None:
        """When route-refresh is enabled and adj-rib-out is False, auto-enable it."""
        from exabgp.configuration.neighbor import ParseNeighbor

        neighbor = self._create_neighbor()
        neighbor.capability.route_refresh = 2  # REFRESH.NORMAL
        neighbor.adj_rib_out = False

        # Simulate what ParseNeighbor.post() does
        parser = ParseNeighbor.__new__(ParseNeighbor)
        parser._post_capa_rr(neighbor)

        assert neighbor.adj_rib_out is True

    def test_adj_rib_out_unchanged_when_already_enabled(self) -> None:
        """When adj-rib-out is already True, it stays True."""
        from exabgp.configuration.neighbor import ParseNeighbor

        neighbor = self._create_neighbor()
        neighbor.capability.route_refresh = 2  # REFRESH.NORMAL
        neighbor.adj_rib_out = True

        parser = ParseNeighbor.__new__(ParseNeighbor)
        parser._post_capa_rr(neighbor)

        assert neighbor.adj_rib_out is True

    def test_adj_rib_out_unchanged_when_route_refresh_disabled(self) -> None:
        """When route-refresh is disabled, adj-rib-out is not changed."""
        from exabgp.configuration.neighbor import ParseNeighbor

        neighbor = self._create_neighbor()
        neighbor.capability.route_refresh = 0  # Disabled
        neighbor.adj_rib_out = False

        parser = ParseNeighbor.__new__(ParseNeighbor)
        parser._post_capa_rr(neighbor)

        assert neighbor.adj_rib_out is False

    def test_enhanced_route_refresh_also_enables_adj_rib_out(self) -> None:
        """Enhanced route-refresh (value 4) also auto-enables adj-rib-out."""
        from exabgp.configuration.neighbor import ParseNeighbor

        neighbor = self._create_neighbor()
        neighbor.capability.route_refresh = 4  # REFRESH.ENHANCED
        neighbor.adj_rib_out = False

        parser = ParseNeighbor.__new__(ParseNeighbor)
        parser._post_capa_rr(neighbor)

        assert neighbor.adj_rib_out is True
