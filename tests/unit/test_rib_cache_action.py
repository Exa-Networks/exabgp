#!/usr/bin/env python3
"""
Tests for Cache action handling.

The Cache class uses route.action (not nlri.action) to determine:
- in_cache(): Whether to check the cache (withdraws are never cached)
- update_cache(): Whether to add or remove from cache

This tests the migration from nlri.action to route.action.
"""

import sys
import os
from unittest.mock import Mock
import pytest

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

from exabgp.rib.cache import Cache  # noqa: E402
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


def create_cache() -> Cache:
    """Create a Cache instance for testing."""
    return Cache(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=True)


class TestCacheInCache:
    """Test Cache.in_cache() uses route.action correctly."""

    def test_in_cache_uses_route_action_not_nlri_action(self):
        """in_cache() checks route.action, not route.nlri.action."""
        cache = create_cache()

        # Create route with nlri.action=WITHDRAW but route._action=ANNOUNCE
        route = create_route(nlri_action=Action.WITHDRAW, route_action=Action.ANNOUNCE)

        # Add to cache (uses route.action=ANNOUNCE)
        cache.update_cache(route)

        # Check: route.action is ANNOUNCE, so should check cache
        # (Not return False just because nlri.action is WITHDRAW)
        assert cache.in_cache(route) is True

    def test_in_cache_withdraw_returns_false(self):
        """Withdraw routes (route.action=WITHDRAW) return False."""
        cache = create_cache()

        # First add an announce route
        announce_route = create_route(route_action=Action.ANNOUNCE)
        cache.update_cache(announce_route)

        # Create withdraw version of same route
        withdraw_route = create_route(route_action=Action.WITHDRAW)

        # Withdraws always return False - not cached
        assert cache.in_cache(withdraw_route) is False

    def test_in_cache_with_route_action_fallback(self):
        """route._action=UNSET falls back to nlri.action correctly."""
        cache = create_cache()

        # Create route with _action=UNSET, nlri.action=ANNOUNCE
        route = create_route(nlri_action=Action.ANNOUNCE, route_action=Action.UNSET)

        # Verify fallback works
        assert route.action == Action.ANNOUNCE

        # Add to cache
        cache.update_cache(route)

        # Should be found in cache (falls back to nlri.action=ANNOUNCE)
        assert cache.in_cache(route) is True

    def test_in_cache_raises_on_unset_action(self):
        """route.action=UNSET (after fallback) raises RuntimeError."""
        cache = create_cache()

        # Create route with both _action and nlri.action as UNSET
        route = create_route(nlri_action=Action.UNSET, route_action=Action.UNSET)

        # Should raise because action is UNSET even after fallback
        with pytest.raises(RuntimeError, match='NLRI action is UNSET'):
            cache.in_cache(route)


class TestCacheUpdateCache:
    """Test Cache.update_cache() uses route.action correctly."""

    def test_update_cache_uses_route_action_not_nlri_action(self):
        """update_cache() checks route.action, not route.nlri.action."""
        cache = create_cache()

        # Create route with nlri.action=WITHDRAW but route._action=ANNOUNCE
        route = create_route(nlri_action=Action.WITHDRAW, route_action=Action.ANNOUNCE)

        # Should store in cache because route.action=ANNOUNCE
        cache.update_cache(route)

        family = route.nlri.family().afi_safi()
        assert route.index() in cache._seen.get(family, {})

    def test_update_cache_announce_stores_route(self):
        """route.action=ANNOUNCE → stored in cache."""
        cache = create_cache()

        route = create_route(route_action=Action.ANNOUNCE)
        cache.update_cache(route)

        family = route.nlri.family().afi_safi()
        assert route.index() in cache._seen.get(family, {})

    def test_update_cache_withdraw_removes_route(self):
        """route.action=WITHDRAW → removed from cache."""
        cache = create_cache()

        # First add the route
        route = create_route(route_action=Action.ANNOUNCE)
        cache.update_cache(route)

        family = route.nlri.family().afi_safi()
        assert route.index() in cache._seen.get(family, {})

        # Now update with withdraw action
        withdraw_route = create_route(route_action=Action.WITHDRAW)
        cache.update_cache(withdraw_route)

        # Should be removed
        assert route.index() not in cache._seen.get(family, {})

    def test_update_cache_unset_raises_error(self):
        """route.action=UNSET → raises RuntimeError."""
        cache = create_cache()

        # Create route with both actions as UNSET
        route = create_route(nlri_action=Action.UNSET, route_action=Action.UNSET)

        with pytest.raises(RuntimeError, match='NLRI action is UNSET'):
            cache.update_cache(route)

    def test_update_cache_with_fallback_to_nlri_action(self):
        """update_cache() correctly falls back to nlri.action when _action=UNSET."""
        cache = create_cache()

        # Create route with _action=UNSET, nlri.action=ANNOUNCE
        route = create_route(nlri_action=Action.ANNOUNCE, route_action=Action.UNSET)

        # Should store because fallback gives ANNOUNCE
        cache.update_cache(route)

        family = route.nlri.family().afi_safi()
        assert route.index() in cache._seen.get(family, {})

    def test_update_cache_nlri_attributes_action_signature(self):
        """update_cache(nlri, attributes, action) uses explicit action."""
        cache = create_cache()

        nlri = create_nlri(action=Action.WITHDRAW)  # NLRI says WITHDRAW
        attrs = AttributeCollection()

        # But explicit action says ANNOUNCE
        cache.update_cache(nlri, attrs, Action.ANNOUNCE)

        family = nlri.family().afi_safi()
        index = cache._make_index(nlri)
        assert index in cache._seen.get(family, {})


class TestCacheUpdateCacheWithdraw:
    """Test Cache.update_cache_withdraw() removes from cache."""

    def test_update_cache_withdraw_with_route(self):
        """update_cache_withdraw(route) removes route from cache."""
        cache = create_cache()

        # First add
        route = create_route(route_action=Action.ANNOUNCE)
        cache.update_cache(route)

        family = route.nlri.family().afi_safi()
        assert route.index() in cache._seen.get(family, {})

        # Now withdraw
        cache.update_cache_withdraw(route)

        assert route.index() not in cache._seen.get(family, {})

    def test_update_cache_withdraw_with_nlri(self):
        """update_cache_withdraw(nlri, attributes) removes from cache."""
        cache = create_cache()

        nlri = create_nlri()
        attrs = AttributeCollection()

        # First add
        cache.update_cache(nlri, attrs, Action.ANNOUNCE)

        family = nlri.family().afi_safi()
        index = cache._make_index(nlri)
        assert index in cache._seen.get(family, {})

        # Now withdraw
        cache.update_cache_withdraw(nlri, attrs)

        assert index not in cache._seen.get(family, {})


class TestCachedRoutes:
    """Test Cache.cached_routes() iteration."""

    def test_cached_routes_returns_only_announces(self):
        """cached_routes() only returns routes with ANNOUNCE action."""
        cache = create_cache()

        # Add an announce route
        route = create_route('10.0.0.0/24', route_action=Action.ANNOUNCE)
        cache.update_cache(route)

        routes = list(cache.cached_routes())
        assert len(routes) == 1
        assert routes[0].action == Action.ANNOUNCE

    def test_cached_routes_empty_after_withdraw(self):
        """cached_routes() is empty after all routes withdrawn."""
        cache = create_cache()

        # Add then withdraw
        route = create_route(route_action=Action.ANNOUNCE)
        cache.update_cache(route)
        cache.update_cache_withdraw(route)

        routes = list(cache.cached_routes())
        assert len(routes) == 0


class TestCacheDisabled:
    """Test Cache behavior when disabled."""

    def test_in_cache_returns_false_when_disabled(self):
        """in_cache() returns False when cache=False."""
        cache = Cache(cache=False, families={(AFI.ipv4, SAFI.unicast)}, enabled=True)

        route = create_route(route_action=Action.ANNOUNCE)

        assert cache.in_cache(route) is False

    def test_update_cache_noop_when_disabled(self):
        """update_cache() is a no-op when cache=False."""
        cache = Cache(cache=False, families={(AFI.ipv4, SAFI.unicast)}, enabled=True)

        route = create_route(route_action=Action.ANNOUNCE)
        cache.update_cache(route)

        # _seen should remain empty
        assert len(cache._seen) == 0
