#!/usr/bin/env python3
"""
Tests for RIB index correctness.

Index is critical for:
- Route deduplication in cache
- Route lookup and replacement
- Correct announce/withdraw matching

Tests verify:
- Route.index() format and consistency
- Cache._make_index() matches Route.index()
- Index uniqueness across different NLRIs
- Index stability (same route → same index)
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

from exabgp.rib.route import Route  # noqa: E402
from exabgp.rib.cache import Cache  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.attribute.origin import Origin  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_nlri(prefix: str, afi: AFI = AFI.ipv4) -> INET:
    """Create an INET NLRI for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    cidr = CIDR.make_cidr(IP.pton(ip_str), mask)
    return INET.from_cidr(cidr, afi, SAFI.unicast)


def create_route(prefix: str, afi: AFI = AFI.ipv4, origin: int = Origin.IGP) -> Route:
    """Create a Route for testing."""
    nlri = create_nlri(prefix, afi)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(origin)
    return Route(nlri, attrs, nexthop=IP.NoNextHop)


# ==============================================================================
# Test Route.index() Format
# ==============================================================================


class TestRouteIndexFormat:
    """Tests for Route.index() format and structure."""

    def test_index_is_bytes(self):
        """Route.index() returns bytes."""
        route = create_route('10.0.0.0/24')

        idx = route.index()

        assert isinstance(idx, bytes)

    def test_index_starts_with_family_prefix(self):
        """Index starts with AFI/SAFI family prefix."""
        route = create_route('10.0.0.0/24', afi=AFI.ipv4)

        idx = route.index()

        # IPv4 unicast: AFI=1, SAFI=1 -> b'0101'
        assert idx.startswith(b'0101')

    def test_index_ipv6_family_prefix(self):
        """IPv6 index has correct family prefix."""
        route = create_route('2001:db8::1/128', afi=AFI.ipv6)

        idx = route.index()

        # IPv6 unicast: AFI=2, SAFI=1 -> b'0201'
        assert idx.startswith(b'0201')

    def test_index_contains_nlri_index(self):
        """Index contains NLRI-specific index after family prefix."""
        route = create_route('10.0.0.0/24')

        idx = route.index()
        nlri_idx = route.nlri.index()

        # Family prefix (4 bytes) + NLRI index
        assert idx[4:] == nlri_idx

    def test_index_length_reasonable(self):
        """Index has reasonable length for IPv4."""
        route = create_route('10.0.0.0/24')

        idx = route.index()

        # Family prefix (4) + NLRI index (varies, includes path-id info)
        # Should be at least family prefix + some NLRI data
        assert len(idx) > 4
        assert len(idx) < 100  # Sanity upper bound


# ==============================================================================
# Test Route.family_prefix()
# ==============================================================================


class TestRouteFamilyPrefix:
    """Tests for Route.family_prefix() static method."""

    def test_family_prefix_ipv4_unicast(self):
        """IPv4 unicast family prefix."""
        prefix = Route.family_prefix((AFI.ipv4, SAFI.unicast))

        assert prefix == b'0101'

    def test_family_prefix_ipv6_unicast(self):
        """IPv6 unicast family prefix."""
        prefix = Route.family_prefix((AFI.ipv6, SAFI.unicast))

        assert prefix == b'0201'

    def test_family_prefix_ipv4_multicast(self):
        """IPv4 multicast family prefix."""
        prefix = Route.family_prefix((AFI.ipv4, SAFI.multicast))

        assert prefix == b'0102'

    def test_family_prefix_format_two_hex_per_component(self):
        """Family prefix uses 2 hex chars per AFI/SAFI component."""
        prefix = Route.family_prefix((AFI.ipv4, SAFI.unicast))

        # 4 characters total: 2 for AFI + 2 for SAFI
        assert len(prefix) == 4


# ==============================================================================
# Test Cache._make_index()
# ==============================================================================


class TestCacheMakeIndex:
    """Tests for Cache._make_index() static method."""

    def test_make_index_matches_route_index(self):
        """Cache._make_index(nlri) produces same index as Route.index()."""
        route = create_route('10.0.0.0/24')

        cache_idx = Cache._make_index(route.nlri)
        route_idx = route.index()

        assert cache_idx == route_idx

    def test_make_index_ipv6_matches_route_index(self):
        """Cache._make_index() works for IPv6."""
        route = create_route('2001:db8::1/128', afi=AFI.ipv6)

        cache_idx = Cache._make_index(route.nlri)
        route_idx = route.index()

        assert cache_idx == route_idx

    def test_make_index_format(self):
        """_make_index produces correct format."""
        nlri = create_nlri('10.0.0.0/24')

        idx = Cache._make_index(nlri)

        # Should be family prefix + nlri.index()
        expected = b'0101' + nlri.index()
        assert idx == expected


# ==============================================================================
# Test Index Uniqueness
# ==============================================================================


class TestIndexUniqueness:
    """Tests that different NLRIs produce different indexes."""

    def test_different_prefixes_different_index(self):
        """Different IP prefixes have different indexes."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.1.0/24')

        assert route1.index() != route2.index()

    def test_same_prefix_different_mask_different_index(self):
        """Same IP prefix with different mask has different index."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.0.0/25')

        assert route1.index() != route2.index()

    def test_same_prefix_different_family_different_index(self):
        """Same prefix in different families has different index."""
        # Note: Can't have same prefix in IPv4 and IPv6, so use family prefix test
        route_v4 = create_route('10.0.0.0/24', afi=AFI.ipv4)
        route_v6 = create_route('2001:db8::1/128', afi=AFI.ipv6)

        # Indexes are different (different families)
        assert route_v4.index() != route_v6.index()

        # Family prefixes are different
        assert route_v4.index()[:4] != route_v6.index()[:4]

    def test_adjacent_prefixes_different_index(self):
        """Adjacent prefixes have different indexes."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.0.128/25')

        assert route1.index() != route2.index()

    def test_host_routes_different_index(self):
        """Different host routes (/32) have different indexes."""
        route1 = create_route('10.0.0.1/32')
        route2 = create_route('10.0.0.2/32')

        assert route1.index() != route2.index()

    def test_many_prefixes_all_unique(self):
        """Many prefixes all produce unique indexes."""
        indexes = set()

        for i in range(256):
            route = create_route(f'10.0.{i}.0/24')
            indexes.add(route.index())

        assert len(indexes) == 256


# ==============================================================================
# Test Index Stability
# ==============================================================================


class TestIndexStability:
    """Tests that index is stable and consistent."""

    def test_index_cached_after_first_call(self):
        """Index is cached after first computation."""
        route = create_route('10.0.0.0/24')

        idx1 = route.index()
        idx2 = route.index()

        # Same object (cached), not just equal
        assert idx1 is idx2

    def test_index_same_for_recreated_route(self):
        """Same NLRI produces same index even for new Route instance."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.0.0/24')

        assert route1.index() == route2.index()

    def test_index_independent_of_attributes(self):
        """Index is same regardless of attributes."""
        route1 = create_route('10.0.0.0/24', origin=Origin.IGP)
        route2 = create_route('10.0.0.0/24', origin=Origin.EGP)

        assert route1.index() == route2.index()

    def test_index_independent_of_nexthop(self):
        """Index is same regardless of nexthop."""
        from exabgp.protocol.ip import IPv4

        nlri = create_nlri('10.0.0.0/24')
        attrs = AttributeCollection()

        route1 = Route(nlri, attrs, nexthop=IP.NoNextHop)
        route2 = Route(nlri, attrs, nexthop=IPv4(IPv4.pton('192.168.1.1')))

        assert route1.index() == route2.index()


# ==============================================================================
# Test Index Consistency Between Route and Cache
# ==============================================================================


class TestIndexConsistency:
    """Tests that Route and Cache use consistent indexing."""

    def test_route_index_used_for_cache_lookup(self):
        """Route.index() is used for cache storage and lookup."""
        from exabgp.rib.incoming import IncomingRIB

        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
        route = create_route('10.0.0.0/24')

        rib.update_cache(route)

        # Route should be findable by its index
        family = route.nlri.family().afi_safi()
        assert route.index() in rib._seen.get(family, {})

    def test_cache_make_index_finds_stored_route(self):
        """Cache._make_index(nlri) can find routes stored by Route.index()."""
        from exabgp.rib.incoming import IncomingRIB

        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
        route = create_route('10.0.0.0/24')

        rib.update_cache(route)

        # _make_index should produce same key
        nlri_index = Cache._make_index(route.nlri)
        family = route.nlri.family().afi_safi()

        assert nlri_index in rib._seen.get(family, {})

    def test_withdraw_uses_consistent_index(self):
        """Withdraw finds route by consistent index."""
        from exabgp.rib.incoming import IncomingRIB

        rib = IncomingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
        route = create_route('10.0.0.0/24')

        rib.update_cache(route)
        assert rib.in_cache(route)

        # Withdraw by NLRI
        rib.update_cache_withdraw(route.nlri)

        # Should be removed
        assert not rib.in_cache(route)


# ==============================================================================
# Test Edge Cases
# ==============================================================================


class TestIndexEdgeCases:
    """Edge case tests for index computation."""

    def test_index_min_prefix_length(self):
        """Index works for minimum prefix length (/0)."""
        route = create_route('0.0.0.0/0')

        idx = route.index()

        assert isinstance(idx, bytes)
        assert len(idx) > 4  # At least family prefix

    def test_index_max_prefix_length_ipv4(self):
        """Index works for maximum IPv4 prefix length (/32)."""
        route = create_route('10.0.0.1/32')

        idx = route.index()

        assert isinstance(idx, bytes)

    def test_index_max_prefix_length_ipv6(self):
        """Index works for maximum IPv6 prefix length (/128)."""
        route = create_route('2001:db8::1/128', afi=AFI.ipv6)

        idx = route.index()

        assert isinstance(idx, bytes)

    def test_index_all_zeros_prefix(self):
        """Index works for all-zeros prefix."""
        route = create_route('0.0.0.0/32')

        idx = route.index()

        assert isinstance(idx, bytes)

    def test_index_all_ones_prefix(self):
        """Index works for all-ones (broadcast) prefix."""
        route = create_route('255.255.255.255/32')

        idx = route.index()

        assert isinstance(idx, bytes)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
