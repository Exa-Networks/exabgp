#!/usr/bin/env python3
"""
Tests for Route.action property fallback behavior.

The Route class has an action property that:
1. Returns Route._action if set (not UNSET)
2. Falls back to nlri.action during transition period

This tests the migration from nlri.action to Route._action.
"""

import sys
import os
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# Mock logger before importing
from exabgp.logger.option import option

mock_logger = Mock()
mock_logger.debug = Mock()
mock_logger.info = Mock()
mock_logger.warning = Mock()
mock_logger.error = Mock()
option.logger = mock_logger

from exabgp.rib.route import Route  # noqa: E402
from exabgp.bgp.message import Action  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402


def create_nlri(prefix: str = '10.0.0.0/24', action: int = Action.ANNOUNCE) -> INET:
    """Create an INET NLRI for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    cidr = CIDR.make_cidr(IP.pton(ip_str), mask)
    return INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, action)


def create_route(
    prefix: str = '10.0.0.0/24',
    nlri_action: int = Action.ANNOUNCE,
    route_action: int = Action.UNSET,
) -> Route:
    """Create a Route for testing with specific action values."""
    nlri = create_nlri(prefix, nlri_action)
    attrs = AttributeCollection()
    return Route(nlri, attrs, route_action)


class TestRouteActionProperty:
    """Test Route.action property with fallback to nlri.action."""

    def test_action_returns_explicit_announce(self):
        """Route._action=ANNOUNCE → route.action returns ANNOUNCE."""
        route = create_route(route_action=Action.ANNOUNCE, nlri_action=Action.WITHDRAW)

        assert route.action == Action.ANNOUNCE
        assert route._action == Action.ANNOUNCE

    def test_action_returns_explicit_withdraw(self):
        """Route._action=WITHDRAW → route.action returns WITHDRAW."""
        route = create_route(route_action=Action.WITHDRAW, nlri_action=Action.ANNOUNCE)

        assert route.action == Action.WITHDRAW
        assert route._action == Action.WITHDRAW

    def test_action_falls_back_to_nlri_action_when_unset(self):
        """Route._action=UNSET → route.action returns nlri.action."""
        route = create_route(route_action=Action.UNSET, nlri_action=Action.ANNOUNCE)

        assert route._action == Action.UNSET
        assert route.action == Action.ANNOUNCE  # Falls back to nlri.action

    def test_action_fallback_with_nlri_announce(self):
        """Route._action=UNSET + nlri.action=ANNOUNCE → returns ANNOUNCE."""
        route = create_route(route_action=Action.UNSET, nlri_action=Action.ANNOUNCE)

        assert route.action == Action.ANNOUNCE

    def test_action_fallback_with_nlri_withdraw(self):
        """Route._action=UNSET + nlri.action=WITHDRAW → returns WITHDRAW."""
        route = create_route(route_action=Action.UNSET, nlri_action=Action.WITHDRAW)

        assert route.action == Action.WITHDRAW

    def test_with_action_returns_new_route(self):
        """route.with_action(X) → returns new Route with updated action."""
        route = create_route(route_action=Action.UNSET)

        route2 = route.with_action(Action.WITHDRAW)
        assert route2._action == Action.WITHDRAW
        assert route2.action == Action.WITHDRAW

        route3 = route2.with_action(Action.ANNOUNCE)
        assert route3._action == Action.ANNOUNCE
        assert route3.action == Action.ANNOUNCE

        # Original route unchanged
        assert route._action == Action.UNSET

    def test_explicit_action_takes_precedence(self):
        """Route._action != UNSET → nlri.action ignored."""
        # Create route where nlri says ANNOUNCE but route says WITHDRAW
        route = create_route(nlri_action=Action.ANNOUNCE, route_action=Action.WITHDRAW)

        # Route._action takes precedence
        assert route.action == Action.WITHDRAW

        # Change nlri.action - should still be ignored
        route.nlri.action = Action.ANNOUNCE
        assert route.action == Action.WITHDRAW

    def test_default_action_is_unset(self):
        """Route created without explicit action defaults to UNSET."""
        nlri = create_nlri(action=Action.ANNOUNCE)
        attrs = AttributeCollection()
        route = Route(nlri, attrs)  # No explicit action

        assert route._action == Action.UNSET
        # Falls back to nlri.action
        assert route.action == Action.ANNOUNCE

    def test_route_created_with_explicit_action(self):
        """Route created with explicit action stores it in _action."""
        nlri = create_nlri(action=Action.ANNOUNCE)
        attrs = AttributeCollection()
        route = Route(nlri, attrs, Action.WITHDRAW)

        assert route._action == Action.WITHDRAW
        assert route.action == Action.WITHDRAW


class TestRouteActionIntegration:
    """Integration tests for route.action usage patterns."""

    def test_feedback_uses_route_action(self):
        """Route.feedback() uses route.action, not nlri.action."""
        # Create route where nlri says ANNOUNCE but route says WITHDRAW
        route = create_route(nlri_action=Action.ANNOUNCE, route_action=Action.WITHDRAW)

        # The feedback method should use route.action (WITHDRAW)
        feedback = route.feedback()
        # Should not raise an error - feedback should work with WITHDRAW action
        assert isinstance(feedback, str)

    def test_route_equality_ignores_action(self):
        """Route equality compares nlri and attributes, not action."""
        route1 = create_route(route_action=Action.ANNOUNCE)
        route2 = create_route(route_action=Action.WITHDRAW)

        # Same NLRI and attributes, different action
        assert route1 == route2  # Action is not part of equality

    def test_route_index_independent_of_action(self):
        """Route.index() is independent of action."""
        route1 = create_route(route_action=Action.ANNOUNCE)
        route2 = create_route(route_action=Action.WITHDRAW)

        # Index should be the same regardless of action
        assert route1.index() == route2.index()


class TestRouteImmutability:
    """Test that Route is immutable after creation."""

    def test_action_has_no_setter(self):
        """Route.action cannot be set directly - raises AttributeError."""
        route = create_route()

        with __import__('pytest').raises(AttributeError):
            route.action = Action.WITHDRAW

    def test_nexthop_has_no_setter(self):
        """Route.nexthop cannot be set directly - raises AttributeError."""
        route = create_route()
        nexthop = IP.from_string('1.2.3.4')

        with __import__('pytest').raises(AttributeError):
            route.nexthop = nexthop

    def test_with_action_returns_new_instance(self):
        """with_action() returns a new Route, doesn't modify original."""
        route1 = create_route(route_action=Action.ANNOUNCE)
        route2 = route1.with_action(Action.WITHDRAW)

        # Different instances
        assert route1 is not route2
        # Original unchanged
        assert route1.action == Action.ANNOUNCE
        # New route has new action
        assert route2.action == Action.WITHDRAW
        # Same NLRI
        assert route1.nlri is route2.nlri

    def test_with_nexthop_returns_new_instance(self):
        """with_nexthop() returns a new Route, doesn't modify original."""
        route1 = create_route()
        nexthop1 = IP.from_string('1.2.3.4')
        nexthop2 = IP.from_string('5.6.7.8')

        # Set initial nexthop via constructor
        route1 = Route(route1.nlri, route1.attributes, nexthop=nexthop1)
        route2 = route1.with_nexthop(nexthop2)

        # Different instances
        assert route1 is not route2
        # Original Route._nexthop unchanged
        assert route1._nexthop == nexthop1
        # New route has new nexthop
        assert route2._nexthop == nexthop2
        assert route2.nexthop == nexthop2

    def test_with_nexthop_preserves_action(self):
        """with_nexthop() preserves the route action."""
        route1 = create_route(route_action=Action.WITHDRAW)
        nexthop = IP.from_string('1.2.3.4')

        route2 = route1.with_nexthop(nexthop)

        assert route2.action == Action.WITHDRAW
        assert route2.nexthop == nexthop

    def test_with_action_preserves_nexthop(self):
        """with_action() preserves the route nexthop."""
        nexthop = IP.from_string('1.2.3.4')
        nlri = create_nlri()
        attrs = AttributeCollection()
        route1 = Route(nlri, attrs, action=Action.ANNOUNCE, nexthop=nexthop)

        route2 = route1.with_action(Action.WITHDRAW)

        assert route2.action == Action.WITHDRAW
        assert route2.nexthop == nexthop


class TestRouteNexthopProperty:
    """Test Route.nexthop property with fallback to nlri.nexthop."""

    def test_nexthop_returns_explicit_value(self):
        """Route._nexthop set → route.nexthop returns it."""
        nexthop = IP.from_string('1.2.3.4')
        nlri = create_nlri()
        attrs = AttributeCollection()
        route = Route(nlri, attrs, nexthop=nexthop)

        assert route._nexthop == nexthop
        assert route.nexthop == nexthop

    def test_nexthop_no_fallback_to_nlri(self):
        """Route.nexthop returns _nexthop directly, no fallback to nlri.nexthop."""
        nlri = create_nlri()
        nlri.nexthop = IP.from_string('9.9.9.9')  # Set on NLRI but not Route
        attrs = AttributeCollection()
        route = Route(nlri, attrs)  # No explicit nexthop

        # Route._nexthop is NoNextHop, and that's what nexthop returns (no fallback)
        assert route._nexthop is IP.NoNextHop
        assert route.nexthop is IP.NoNextHop  # No fallback to nlri.nexthop

    def test_explicit_nexthop_takes_precedence(self):
        """Route._nexthop set → nlri.nexthop ignored."""
        nexthop = IP.from_string('1.2.3.4')
        nlri = create_nlri()
        nlri.nexthop = IP.from_string('9.9.9.9')
        attrs = AttributeCollection()
        route = Route(nlri, attrs, nexthop=nexthop)

        # Route._nexthop takes precedence
        assert route.nexthop == nexthop

    def test_default_nexthop_is_no_nexthop(self):
        """Route created without explicit nexthop defaults to NoNextHop."""
        nlri = create_nlri()
        attrs = AttributeCollection()
        route = Route(nlri, attrs)

        assert route._nexthop is IP.NoNextHop
