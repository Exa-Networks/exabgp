#!/usr/bin/env python3
"""
Tests for RouteBuilderValidator action handling.

The RouteBuilderValidator creates Route objects with:
1. action_type = Action.ANNOUNCE if tokeniser.announce is True
2. action_type = Action.WITHDRAW if tokeniser.announce is False

The Route is created with Route(nlri, attributes, action_type), storing
the action in Route._action rather than nlri.action.

This tests the integration between configuration parsing and Route.action.
"""

from unittest.mock import Mock

from exabgp.bgp.message import Action
from exabgp.rib.route import Route
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.configuration.announce.ip import AnnounceIP


class TestAnnounceIPCheck:
    """Test AnnounceIP.check() uses route.action correctly."""

    def _create_mock_route(
        self,
        action: int,
        has_nexthop: bool = True,
        afi: AFI = AFI.ipv4,
        safi: SAFI = SAFI.unicast,
    ) -> Mock:
        """Create a mock Route for testing check()."""
        route = Mock(spec=Route)
        route.action = action

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
        # Route.nexthop property (with fallback to nlri.nexthop during transition)
        route.nexthop = nexthop

        return route

    def test_announce_with_nexthop_passes(self):
        """ANNOUNCE + nexthop → check passes."""
        route = self._create_mock_route(action=Action.ANNOUNCE, has_nexthop=True)

        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is True

    def test_announce_without_nexthop_fails(self):
        """ANNOUNCE + no nexthop → check fails (for unicast/multicast)."""
        route = self._create_mock_route(action=Action.ANNOUNCE, has_nexthop=False)

        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is False

    def test_withdraw_without_nexthop_passes(self):
        """WITHDRAW + no nexthop → check passes."""
        route = self._create_mock_route(action=Action.WITHDRAW, has_nexthop=False)

        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is True

    def test_withdraw_with_nexthop_passes(self):
        """WITHDRAW + nexthop → check passes (nexthop is optional for withdraws)."""
        route = self._create_mock_route(action=Action.WITHDRAW, has_nexthop=True)

        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is True

    def test_check_uses_route_action_not_nlri_action(self):
        """Verify check() uses route.action, not nlri.action."""
        route = Mock(spec=Route)
        route.action = Action.WITHDRAW  # Route says WITHDRAW

        # But nlri might say something different (during transition)
        nlri = Mock()
        nlri.afi = AFI.ipv4
        nlri.safi = SAFI.unicast
        nlri.nexthop = IP.NoNextHop
        nlri.action = Action.ANNOUNCE  # NLRI says ANNOUNCE (old style)
        route.nlri = nlri

        # Should pass because route.action is WITHDRAW (not nlri.action)
        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is True


class TestRouteActionFromConfiguration:
    """Test that Route.action is correctly set from configuration.

    These tests verify the full path from tokeniser.announce to Route._action.
    """

    def test_route_created_with_explicit_action(self):
        """Route created with explicit action stores it correctly."""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.cidr import CIDR
        from exabgp.bgp.message.update.attribute.collection import AttributeCollection
        from exabgp.protocol.ip import IP as IP_

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        attrs = AttributeCollection()

        # Create Route with explicit WITHDRAW action
        route = Route(nlri, attrs, Action.WITHDRAW, nexthop=IP_.NoNextHop)

        # Route._action should be WITHDRAW
        assert route._action == Action.WITHDRAW
        # route.action should return _action, not nlri.action
        assert route.action == Action.WITHDRAW

    def test_route_action_precedence_over_nlri_action(self):
        """Route._action takes precedence over nlri.action."""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.cidr import CIDR
        from exabgp.bgp.message.update.attribute.collection import AttributeCollection
        from exabgp.protocol.ip import IP as IP_

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        # NLRI created with ANNOUNCE
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        attrs = AttributeCollection()

        # Route created with WITHDRAW
        route = Route(nlri, attrs, Action.WITHDRAW, nexthop=IP_.NoNextHop)

        # Even though nlri.action is ANNOUNCE, route.action should be WITHDRAW
        assert nlri.action == Action.ANNOUNCE
        assert route.action == Action.WITHDRAW

    def test_route_action_fallback_to_nlri_when_unset(self):
        """Route.action falls back to nlri.action when _action is UNSET."""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.cidr import CIDR
        from exabgp.bgp.message.update.attribute.collection import AttributeCollection
        from exabgp.protocol.ip import IP as IP_

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
        attrs = AttributeCollection()

        # Route created without explicit action (defaults to UNSET)
        route = Route(nlri, attrs, nexthop=IP_.NoNextHop)

        # Should fall back to nlri.action
        assert route._action == Action.UNSET
        assert route.action == Action.WITHDRAW  # From nlri
