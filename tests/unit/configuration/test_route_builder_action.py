#!/usr/bin/env python3
"""
Tests for RouteBuilderValidator action handling.

The RouteBuilderValidator creates Route objects and passes action to
check functions as an explicit parameter. Action is NOT stored on Route.

This tests the integration between configuration parsing and check functions.
"""

from unittest.mock import Mock

from exabgp.bgp.message import Action
from exabgp.rib.route import Route
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.configuration.announce.ip import AnnounceIP


class TestAnnounceIPCheck:
    """Test AnnounceIP.check() with explicit action parameter."""

    def _create_mock_route(
        self,
        has_nexthop: bool = True,
        afi: AFI = AFI.ipv4,
        safi: SAFI = SAFI.unicast,
    ) -> Mock:
        """Create a mock Route for testing check()."""
        route = Mock(spec=Route)

        # Create mock NLRI
        nlri = Mock()
        nlri.afi = afi
        nlri.safi = safi
        if has_nexthop:
            nexthop = IP.pton('1.2.3.4')
        else:
            nexthop = IP.NoNextHop
        nlri.nexthop = nexthop
        route.nlri = nlri
        # Route.nexthop property
        route.nexthop = nexthop

        return route

    def test_announce_with_nexthop_passes(self):
        """ANNOUNCE + nexthop → check passes."""
        route = self._create_mock_route(has_nexthop=True)

        result = AnnounceIP.check(route, AFI.ipv4, Action.ANNOUNCE)
        assert result is True

    def test_announce_without_nexthop_fails(self):
        """ANNOUNCE + no nexthop → check fails (for unicast/multicast)."""
        route = self._create_mock_route(has_nexthop=False)

        result = AnnounceIP.check(route, AFI.ipv4, Action.ANNOUNCE)
        assert result is False

    def test_withdraw_without_nexthop_passes(self):
        """WITHDRAW + no nexthop → check passes."""
        route = self._create_mock_route(has_nexthop=False)

        result = AnnounceIP.check(route, AFI.ipv4, Action.WITHDRAW)
        assert result is True

    def test_withdraw_with_nexthop_passes(self):
        """WITHDRAW + nexthop → check passes (nexthop is optional for withdraws)."""
        route = self._create_mock_route(has_nexthop=True)

        result = AnnounceIP.check(route, AFI.ipv4, Action.WITHDRAW)
        assert result is True

    def test_check_default_action_is_announce(self):
        """check() defaults to ANNOUNCE action."""
        route = self._create_mock_route(has_nexthop=False)

        # Without explicit action, should default to ANNOUNCE and fail for no nexthop
        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is False


# NOTE: TestRouteActionFromConfiguration was removed in Phase 2
# Route no longer stores _action - action is determined by which RIB method is called
# (add_to_rib for announces, del_from_rib for withdraws)
