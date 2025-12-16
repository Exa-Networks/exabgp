#!/usr/bin/env python3
"""
Comprehensive tests for IncomingRIB and Cache classes.

IncomingRIB stores routes received from BGP peers.
It inherits from Cache which provides the core storage functionality.

Tests cover:
- Basic operations (add, remove, query)
- Multi-family support
- Cache enabled/disabled behavior
- Edge cases and iteration safety
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

from exabgp.rib.incoming import IncomingRIB  # noqa: E402
from exabgp.rib.cache import Cache  # noqa: E402
from exabgp.rib.route import Route  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.attribute.origin import Origin  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP, IPv4  # noqa: E402


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_nlri(prefix: str, afi: AFI = AFI.ipv4) -> INET:
    """Create an INET NLRI for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    return INET.from_cidr(cidr, afi, SAFI.unicast)


def create_route(prefix: str, afi: AFI = AFI.ipv4, origin: int = Origin.IGP) -> Route:
    """Create a Route for testing."""
    nlri = create_nlri(prefix, afi)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(origin)
    return Route(nlri, attrs, nexthop=IP.NoNextHop)


def create_route_with_nexthop(prefix: str, nexthop_str: str = '192.168.1.1') -> Route:
    """Create a Route with a concrete nexthop."""
    nlri = create_nlri(prefix)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(Origin.IGP)
    nexthop = IPv4(IPv4.pton(nexthop_str))
    return Route(nlri, attrs, nexthop=nexthop)


def create_incoming_rib(cache: bool = True, families: set | None = None) -> IncomingRIB:
    """Create an IncomingRIB for testing."""
    if families is None:
        families = {(AFI.ipv4, SAFI.unicast)}
    return IncomingRIB(cache=cache, families=families)


# ==============================================================================
# Test IncomingRIB Basic Operations
# ==============================================================================


class TestIncomingRIBInit:
    """Tests for IncomingRIB initialization."""

    def test_init_with_cache_enabled(self):
        """IncomingRIB initializes with cache enabled."""
        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

        assert rib.cache is True
        assert rib.enabled is True

    def test_init_with_cache_disabled(self):
        """IncomingRIB initializes with cache disabled."""
        rib = IncomingRIB(cache=False, families={(AFI.ipv4, SAFI.unicast)})

        assert rib.cache is False

    def test_init_with_multiple_families(self):
        """IncomingRIB can be initialized with multiple families."""
        families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
        rib = IncomingRIB(cache=True, families=families)

        assert rib.families == families

    def test_init_disabled(self):
        """IncomingRIB can be initialized disabled."""
        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        assert rib.enabled is False


class TestIncomingRIBClear:
    """Tests for IncomingRIB.clear() method."""

    def test_clear_removes_all_routes(self):
        """clear() removes all cached routes."""
        rib = create_incoming_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.update_cache(route1)
        rib.update_cache(route2)

        assert len(list(rib.cached_routes())) == 2

        rib.clear()

        assert len(list(rib.cached_routes())) == 0

    def test_clear_on_empty_rib(self):
        """clear() on empty RIB doesn't crash."""
        rib = create_incoming_rib()

        rib.clear()  # Should not raise

        assert len(list(rib.cached_routes())) == 0


class TestIncomingRIBReset:
    """Tests for IncomingRIB.reset() method."""

    def test_reset_is_noop(self):
        """reset() is a no-op for IncomingRIB."""
        rib = create_incoming_rib()

        route = create_route('10.0.1.0/24')
        rib.update_cache(route)

        rib.reset()

        # Routes should still be there
        assert len(list(rib.cached_routes())) == 1


# ==============================================================================
# Test Cache Operations
# ==============================================================================


class TestCacheUpdateCache:
    """Tests for Cache.update_cache() method."""

    def test_update_cache_stores_route(self):
        """update_cache() stores a route."""
        rib = create_incoming_rib()

        route = create_route('10.0.1.0/24')
        rib.update_cache(route)

        cached = list(rib.cached_routes())
        assert len(cached) == 1
        assert cached[0] is route

    def test_update_cache_replaces_existing_route(self):
        """update_cache() replaces route with same index."""
        rib = create_incoming_rib()

        route1 = create_route('10.0.1.0/24', origin=Origin.IGP)
        route2 = create_route('10.0.1.0/24', origin=Origin.EGP)

        rib.update_cache(route1)
        rib.update_cache(route2)

        cached = list(rib.cached_routes())
        assert len(cached) == 1
        assert cached[0].attributes[Origin.ID].origin == Origin.EGP

    def test_update_cache_disabled_is_noop(self):
        """update_cache() is no-op when cache=False."""
        rib = IncomingRIB(cache=False, families={(AFI.ipv4, SAFI.unicast)})

        route = create_route('10.0.1.0/24')
        rib.update_cache(route)

        assert len(list(rib.cached_routes())) == 0

    def test_update_cache_when_rib_disabled(self):
        """update_cache() is no-op when RIB disabled."""
        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        route = create_route('10.0.1.0/24')
        rib.update_cache(route)

        assert len(list(rib.cached_routes())) == 0


class TestCacheUpdateCacheWithdraw:
    """Tests for Cache.update_cache_withdraw() method."""

    def test_update_cache_withdraw_removes_route(self):
        """update_cache_withdraw() removes route from cache."""
        rib = create_incoming_rib()

        route = create_route('10.0.1.0/24')
        rib.update_cache(route)

        assert len(list(rib.cached_routes())) == 1

        rib.update_cache_withdraw(route.nlri)

        assert len(list(rib.cached_routes())) == 0

    def test_update_cache_withdraw_nonexistent_is_safe(self):
        """update_cache_withdraw() is safe for routes not in cache."""
        rib = create_incoming_rib()

        nlri = create_nlri('10.0.1.0/24')

        rib.update_cache_withdraw(nlri)  # Should not raise

    def test_update_cache_withdraw_disabled_is_noop(self):
        """update_cache_withdraw() is no-op when cache=False."""
        rib = IncomingRIB(cache=False, families={(AFI.ipv4, SAFI.unicast)})

        route = create_route('10.0.1.0/24')
        # Can't add to cache when disabled, but withdraw should not crash
        rib.update_cache_withdraw(route.nlri)


class TestCacheInCache:
    """Tests for Cache.in_cache() method."""

    def test_in_cache_finds_stored_route(self):
        """in_cache() returns True for stored route."""
        rib = create_incoming_rib()

        route = create_route('10.0.1.0/24')
        rib.update_cache(route)

        assert rib.in_cache(route) is True

    def test_in_cache_returns_false_for_missing(self):
        """in_cache() returns False for route not in cache."""
        rib = create_incoming_rib()

        route = create_route('10.0.1.0/24')

        assert rib.in_cache(route) is False

    def test_in_cache_returns_false_different_attributes(self):
        """in_cache() returns False for different attributes."""
        rib = create_incoming_rib()

        route1 = create_route('10.0.1.0/24', origin=Origin.IGP)
        route2 = create_route('10.0.1.0/24', origin=Origin.EGP)

        rib.update_cache(route1)

        # Same NLRI but different attributes
        assert rib.in_cache(route2) is False

    def test_in_cache_returns_false_different_nexthop(self):
        """in_cache() returns False for different nexthop."""
        rib = create_incoming_rib()

        route1 = create_route_with_nexthop('10.0.1.0/24', '192.168.1.1')
        route2 = create_route_with_nexthop('10.0.1.0/24', '192.168.1.2')

        rib.update_cache(route1)

        # Same NLRI but different nexthop
        assert rib.in_cache(route2) is False

    def test_in_cache_disabled_returns_false(self):
        """in_cache() returns False when cache=False."""
        rib = IncomingRIB(cache=False, families={(AFI.ipv4, SAFI.unicast)})

        route = create_route('10.0.1.0/24')

        assert rib.in_cache(route) is False

    def test_in_cache_rib_disabled_returns_false(self):
        """in_cache() returns False when RIB disabled."""
        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        route = create_route('10.0.1.0/24')

        assert rib.in_cache(route) is False


class TestCacheCachedRoutes:
    """Tests for Cache.cached_routes() method."""

    def test_cached_routes_returns_all_routes(self):
        """cached_routes() returns all stored routes."""
        rib = create_incoming_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.update_cache(route1)
        rib.update_cache(route2)

        cached = list(rib.cached_routes())
        assert len(cached) == 2

    def test_cached_routes_empty_when_no_routes(self):
        """cached_routes() returns empty when no routes."""
        rib = create_incoming_rib()

        cached = list(rib.cached_routes())
        assert len(cached) == 0

    def test_cached_routes_filters_by_family(self):
        """cached_routes() can filter by family."""
        families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
        rib = IncomingRIB(cache=True, families=families)

        route_v4 = create_route('10.0.1.0/24', afi=AFI.ipv4)
        route_v6 = create_route('2001:db8::1/128', afi=AFI.ipv6)

        rib.update_cache(route_v4)
        rib.update_cache(route_v6)

        # All routes
        all_cached = list(rib.cached_routes())
        assert len(all_cached) == 2

        # IPv4 only
        v4_cached = list(rib.cached_routes([(AFI.ipv4, SAFI.unicast)]))
        assert len(v4_cached) == 1
        assert str(v4_cached[0].nlri) == '10.0.1.0/24'

        # IPv6 only
        v6_cached = list(rib.cached_routes([(AFI.ipv6, SAFI.unicast)]))
        assert len(v6_cached) == 1
        assert '2001:db8' in str(v6_cached[0].nlri)

    def test_cached_routes_empty_list_returns_nothing(self):
        """cached_routes([]) returns nothing (empty intersection)."""
        rib = create_incoming_rib()

        route = create_route('10.0.1.0/24')
        rib.update_cache(route)

        # Empty list means empty intersection
        cached = list(rib.cached_routes([]))
        assert len(cached) == 0

    def test_cached_routes_disabled_returns_empty(self):
        """cached_routes() returns empty when RIB disabled."""
        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        # Can't add routes when disabled, but should not crash
        cached = list(rib.cached_routes())
        assert len(cached) == 0


class TestCacheDeleteCachedFamily:
    """Tests for Cache.delete_cached_family() method."""

    def test_delete_cached_family_removes_family(self):
        """delete_cached_family() removes routes not in kept families."""
        families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
        rib = IncomingRIB(cache=True, families=families)

        route_v4 = create_route('10.0.1.0/24', afi=AFI.ipv4)
        route_v6 = create_route('2001:db8::1/128', afi=AFI.ipv6)

        rib.update_cache(route_v4)
        rib.update_cache(route_v6)

        # Keep only IPv4
        rib.delete_cached_family({(AFI.ipv4, SAFI.unicast)})

        # IPv4 should remain
        assert (AFI.ipv4, SAFI.unicast) in rib._seen
        # IPv6 should be gone
        assert (AFI.ipv6, SAFI.unicast) not in rib._seen

    def test_delete_cached_family_empty_set_removes_all(self):
        """delete_cached_family({}) removes all families."""
        families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
        rib = IncomingRIB(cache=True, families=families)

        route_v4 = create_route('10.0.1.0/24', afi=AFI.ipv4)
        route_v6 = create_route('2001:db8::1/128', afi=AFI.ipv6)

        rib.update_cache(route_v4)
        rib.update_cache(route_v6)

        # Keep nothing
        rib.delete_cached_family(set())

        assert len(rib._seen) == 0


class TestCacheMakeIndex:
    """Tests for Cache._make_index() static method."""

    def test_make_index_format(self):
        """_make_index() produces correct format."""
        nlri = create_nlri('10.0.1.0/24')

        index = Cache._make_index(nlri)

        # Should start with family prefix (AFI=1, SAFI=1 -> 0101)
        assert index.startswith(b'0101')

    def test_make_index_matches_route_index(self):
        """_make_index(nlri) matches route.index()."""
        route = create_route('10.0.1.0/24')

        nlri_index = Cache._make_index(route.nlri)
        route_index = route.index()

        assert nlri_index == route_index


# ==============================================================================
# Test Iteration Safety
# ==============================================================================


class TestCacheIterationSafety:
    """Tests for iteration safety during modifications."""

    def test_cached_routes_snapshots_values(self):
        """cached_routes() takes a snapshot, safe from modification."""
        rib = create_incoming_rib()

        for i in range(10):
            route = create_route(f'10.0.{i}.0/24')
            rib.update_cache(route)

        # Start iterating
        gen = rib.cached_routes()
        first_five = [next(gen) for _ in range(5)]

        # Modify during iteration
        new_route = create_route('10.0.100.0/24')
        rib.update_cache(new_route)

        # Continue iterating - should not include new route
        remaining = list(gen)

        assert len(first_five) + len(remaining) == 10

    def test_delete_cached_family_iteration_safe(self):
        """delete_cached_family() doesn't crash during iteration."""
        families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
        rib = IncomingRIB(cache=True, families=families)

        route_v4 = create_route('10.0.1.0/24', afi=AFI.ipv4)
        route_v6 = create_route('2001:db8::1/128', afi=AFI.ipv6)

        rib.update_cache(route_v4)
        rib.update_cache(route_v6)

        # This should not raise RuntimeError (dictionary changed size)
        rib.delete_cached_family({(AFI.ipv4, SAFI.unicast)})


# ==============================================================================
# Test Multi-Family Operations
# ==============================================================================


class TestCacheMultiFamily:
    """Tests for multi-family cache operations."""

    def test_multi_family_independent_storage(self):
        """Routes from different families are stored independently."""
        families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
        rib = IncomingRIB(cache=True, families=families)

        route_v4 = create_route('10.0.1.0/24', afi=AFI.ipv4)
        route_v6 = create_route('2001:db8::1/128', afi=AFI.ipv6)

        rib.update_cache(route_v4)
        rib.update_cache(route_v6)

        # Each family has its own storage
        assert len(rib._seen) == 2
        assert (AFI.ipv4, SAFI.unicast) in rib._seen
        assert (AFI.ipv6, SAFI.unicast) in rib._seen

    def test_multi_family_withdraw_affects_correct_family(self):
        """Withdraw only affects the correct family."""
        families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
        rib = IncomingRIB(cache=True, families=families)

        route_v4 = create_route('10.0.1.0/24', afi=AFI.ipv4)
        route_v6 = create_route('2001:db8::1/128', afi=AFI.ipv6)

        rib.update_cache(route_v4)
        rib.update_cache(route_v6)

        # Withdraw IPv4 route
        rib.update_cache_withdraw(route_v4.nlri)

        # IPv6 should still be there
        all_cached = list(rib.cached_routes())
        assert len(all_cached) == 1
        assert '2001:db8' in str(all_cached[0].nlri)


# ==============================================================================
# Test Edge Cases
# ==============================================================================


class TestCacheEdgeCases:
    """Edge case tests for Cache."""

    def test_same_prefix_different_mask_different_routes(self):
        """Same IP but different mask are different routes."""
        rib = create_incoming_rib()

        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.0.0/25')

        rib.update_cache(route1)
        rib.update_cache(route2)

        cached = list(rib.cached_routes())
        assert len(cached) == 2

    def test_large_route_table(self):
        """Cache handles large number of routes."""
        rib = create_incoming_rib()

        # Add 1000 routes
        for i in range(1000):
            octet2 = i // 256
            octet3 = i % 256
            route = create_route(f'10.{octet2}.{octet3}.0/24')
            rib.update_cache(route)

        cached = list(rib.cached_routes())
        assert len(cached) == 1000

    def test_clear_then_add(self):
        """Can add routes after clear."""
        rib = create_incoming_rib()

        route1 = create_route('10.0.1.0/24')
        rib.update_cache(route1)
        rib.clear()

        route2 = create_route('10.0.2.0/24')
        rib.update_cache(route2)

        cached = list(rib.cached_routes())
        assert len(cached) == 1
        assert str(cached[0].nlri) == '10.0.2.0/24'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
