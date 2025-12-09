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

    def test_action_setter_updates_internal_action(self):
        """route.action = X → updates _action."""
        route = create_route(route_action=Action.UNSET)

        route.action = Action.WITHDRAW
        assert route._action == Action.WITHDRAW
        assert route.action == Action.WITHDRAW

        route.action = Action.ANNOUNCE
        assert route._action == Action.ANNOUNCE
        assert route.action == Action.ANNOUNCE

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
