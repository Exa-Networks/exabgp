#!/usr/bin/env python3
"""
Tests for Cache operations.

The Cache class stores announced routes for deduplication:
- in_cache(): Check if route already announced (for dedup)
- update_cache(): Add route to cache (announces only)
- update_cache_withdraw(): Remove route from cache (for withdraws)

Action is implicit in which method is called:
- add_to_rib() -> update_cache() -> announces
- del_from_rib() -> update_cache_withdraw() -> withdraws
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

from exabgp.rib.cache import Cache  # noqa: E402
from exabgp.rib.route import Route  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402


def create_nlri(prefix: str = '10.0.0.0/24') -> INET:
    """Create an INET NLRI for testing.

    Note: Action is no longer stored in NLRI - it's determined by which RIB method is called.
    """
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    return INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)


def create_route(prefix: str = '10.0.0.0/24') -> Route:
    """Create a Route for testing.

    Note: Action is no longer stored in Route - it's determined by which RIB method is called.
    """
    from exabgp.protocol.ip import IP

    nlri = create_nlri(prefix)
    attrs = AttributeCollection()
    return Route(nlri, attrs, nexthop=IP.NoNextHop)


def create_cache() -> Cache:
    """Create a Cache instance for testing."""
    return Cache(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=True)


class TestCacheInCache:
    """Test Cache.in_cache() for announce deduplication."""

    def test_in_cache_returns_false_when_not_cached(self):
        """Route not in cache returns False."""
        cache = create_cache()
        route = create_route()

        assert cache.in_cache(route) is False

    def test_in_cache_returns_true_when_cached(self):
        """Route in cache returns True."""
        cache = create_cache()
        route = create_route()

        cache.update_cache(route)

        assert cache.in_cache(route) is True

    def test_in_cache_returns_false_for_different_prefix(self):
        """Different prefix not in cache."""
        cache = create_cache()
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.1.0/24')

        cache.update_cache(route1)

        assert cache.in_cache(route2) is False


class TestCacheUpdateCache:
    """Test Cache.update_cache() stores routes."""

    def test_update_cache_stores_route(self):
        """update_cache() stores route in cache."""
        cache = create_cache()
        route = create_route()

        cache.update_cache(route)

        family = route.nlri.family().afi_safi()
        assert route.index() in cache._seen.get(family, {})

    def test_update_cache_replaces_existing(self):
        """update_cache() replaces existing route with same index."""
        cache = create_cache()
        route1 = create_route()
        route2 = create_route()  # Same prefix

        cache.update_cache(route1)
        cache.update_cache(route2)

        family = route1.nlri.family().afi_safi()
        # Only one entry for same prefix
        assert len(cache._seen.get(family, {})) == 1


class TestCacheUpdateCacheWithdraw:
    """Test Cache.update_cache_withdraw() removes routes."""

    def test_update_cache_withdraw_removes_route(self):
        """update_cache_withdraw(nlri) removes route from cache."""
        cache = create_cache()
        route = create_route()

        cache.update_cache(route)

        family = route.nlri.family().afi_safi()
        assert route.index() in cache._seen.get(family, {})

        # Now withdraw using NLRI
        cache.update_cache_withdraw(route.nlri)

        assert route.index() not in cache._seen.get(family, {})

    def test_update_cache_withdraw_noop_if_not_present(self):
        """update_cache_withdraw() is safe when route not in cache."""
        cache = create_cache()
        nlri = create_nlri()

        # Should not raise
        cache.update_cache_withdraw(nlri)


class TestCachedRoutes:
    """Test Cache.cached_routes() iteration."""

    def test_cached_routes_returns_stored_routes(self):
        """cached_routes() returns all stored routes."""
        cache = create_cache()

        route = create_route('10.0.0.0/24')
        cache.update_cache(route)

        routes = list(cache.cached_routes())
        assert len(routes) == 1

    def test_cached_routes_empty_after_withdraw(self):
        """cached_routes() is empty after all routes withdrawn."""
        cache = create_cache()

        route = create_route()
        cache.update_cache(route)
        cache.update_cache_withdraw(route.nlri)

        routes = list(cache.cached_routes())
        assert len(routes) == 0


class TestCacheDisabled:
    """Test Cache behavior when disabled."""

    def test_in_cache_returns_false_when_disabled(self):
        """in_cache() returns False when cache=False."""
        cache = Cache(cache=False, families={(AFI.ipv4, SAFI.unicast)}, enabled=True)

        route = create_route()

        assert cache.in_cache(route) is False

    def test_update_cache_noop_when_disabled(self):
        """update_cache() is a no-op when cache=False."""
        cache = Cache(cache=False, families={(AFI.ipv4, SAFI.unicast)}, enabled=True)

        route = create_route()
        cache.update_cache(route)

        # _seen should remain empty
        assert len(cache._seen) == 0
