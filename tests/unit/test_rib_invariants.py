#!/usr/bin/env python3
"""
Property-based invariant tests for RIB.

These tests verify that certain properties (invariants) hold after any valid
sequence of RIB operations. Invariants are fundamental guarantees that the
RIB implementation must maintain.

Invariants tested:
1. After updates(), pending() is False
2. cached_routes() returns exactly what's in _seen
3. Added routes are eventually yielded by updates()
4. Withdrawn routes are removed from cache after consume
5. _new_nlri count matches total count in _new_attr_af_nlri
6. Cache state is consistent with operations performed
"""

import sys
import os
from typing import List
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

from exabgp.rib.outgoing import OutgoingRIB  # noqa: E402
from exabgp.rib.route import Route  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.attribute.origin import Origin  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_route(prefix: str, afi: AFI = AFI.ipv4, origin: int = Origin.IGP) -> Route:
    """Create a Route for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, afi, SAFI.unicast)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(origin)

    return Route(nlri, attrs, nexthop=IP.NoNextHop)


def create_rib(cache: bool = True) -> OutgoingRIB:
    """Create a standard test RIB."""
    return OutgoingRIB(cache=cache, families={(AFI.ipv4, SAFI.unicast)})


def consume_updates(rib: OutgoingRIB, grouped: bool = False) -> List:
    """Consume all pending updates from the RIB."""
    return list(rib.updates(grouped=grouped))


def count_announces_withdraws(updates: list) -> tuple[int, int]:
    """Count total announces and withdraws across all updates."""
    announces = sum(len(u.announces) for u in updates)
    withdraws = sum(len(u.withdraws) for u in updates)
    return announces, withdraws


def count_new_nlri(rib: OutgoingRIB) -> int:
    """Count entries in _new_nlri."""
    return len(rib._new_nlri)


def count_attr_af_nlri(rib: OutgoingRIB) -> int:
    """Count total routes in _new_attr_af_nlri (nested structure)."""
    total = 0
    for attr_dict in rib._new_attr_af_nlri.values():
        for family_dict in attr_dict.values():
            total += len(family_dict)
    return total


def count_cached_routes(rib: OutgoingRIB) -> int:
    """Count routes via cached_routes() iterator."""
    return sum(1 for _ in rib.cached_routes(None))


def count_seen_routes(rib: OutgoingRIB) -> int:
    """Count routes directly from _seen dict."""
    total = 0
    for family_dict in rib._seen.values():
        total += len(family_dict)
    return total


# ==============================================================================
# Test RIB Invariants
# ==============================================================================


class TestRIBInvariants:
    """Property-based invariants for OutgoingRIB."""

    def test_after_updates_pending_is_false(self):
        """Invariant: After consuming updates(), pending() returns False.

        This is a fundamental guarantee - once updates are consumed,
        the RIB should have no pending work.
        """
        rib = create_rib()

        # Add several routes
        for i in range(5):
            rib.add_to_rib(create_route(f'10.0.{i}.0/24'))

        assert rib.pending(), 'Should be pending before consume'

        # Consume updates
        consume_updates(rib)

        assert not rib.pending(), 'INVARIANT: pending() must be False after updates()'

    def test_after_updates_with_withdraws_pending_is_false(self):
        """Invariant holds for withdraws as well as announces."""
        rib = create_rib()

        # Add and cache routes
        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for route in routes:
            rib.add_to_rib(route)
        consume_updates(rib)

        # Now withdraw them
        for route in routes:
            rib.del_from_rib(route)

        assert rib.pending(), 'Should be pending with withdraws'

        consume_updates(rib)

        assert not rib.pending(), 'INVARIANT: pending() must be False after updates()'

    def test_after_updates_with_mixed_ops_pending_is_false(self):
        """Invariant holds for mixed announce/withdraw operations."""
        rib = create_rib()

        # Add and cache some routes
        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # Mixed operations
        rib.del_from_rib(route1)  # withdraw
        rib.add_to_rib(create_route('10.0.3.0/24'))  # new announce

        consume_updates(rib)

        assert not rib.pending(), 'INVARIANT: pending() must be False after updates()'

    def test_cached_routes_matches_seen_contents(self):
        """Invariant: cached_routes() returns exactly what's in _seen.

        This ensures the iterator correctly reflects internal state.
        """
        rib = create_rib()

        # Add several routes and cache
        for i in range(5):
            rib.add_to_rib(create_route(f'10.0.{i}.0/24'))
        consume_updates(rib)

        # Count via iterator
        cached_count = count_cached_routes(rib)
        # Count directly from _seen
        seen_count = count_seen_routes(rib)

        assert cached_count == seen_count, 'INVARIANT: cached_routes() must match _seen contents'
        assert cached_count == 5, 'Should have 5 cached routes'

    def test_cached_routes_matches_after_withdraws(self):
        """Invariant holds after some routes are withdrawn."""
        rib = create_rib()

        # Add routes and cache
        routes = [create_route(f'10.0.{i}.0/24') for i in range(5)]
        for route in routes:
            rib.add_to_rib(route)
        consume_updates(rib)

        # Withdraw some
        rib.del_from_rib(routes[0])
        rib.del_from_rib(routes[2])
        consume_updates(rib)

        cached_count = count_cached_routes(rib)
        seen_count = count_seen_routes(rib)

        assert cached_count == seen_count, 'INVARIANT: cached_routes() must match _seen contents'
        assert cached_count == 3, 'Should have 3 cached routes after withdrawing 2'

    def test_added_route_eventually_yielded(self):
        """Invariant: Every route added to RIB is eventually yielded by updates().

        Routes added via add_to_rib() must appear in updates() output.
        """
        rib = create_rib()

        # Add multiple routes
        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for route in routes:
            rib.add_to_rib(route)

        updates = consume_updates(rib)
        announces, _ = count_announces_withdraws(updates)

        assert announces == 3, 'INVARIANT: All added routes must be yielded by updates()'

    def test_added_route_with_force_eventually_yielded(self):
        """Invariant holds for force=True adds as well."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)
        consume_updates(rib)

        # Force re-add
        rib.add_to_rib(route, force=True)

        updates = consume_updates(rib)
        announces, _ = count_announces_withdraws(updates)

        assert announces == 1, 'INVARIANT: Force-added route must be yielded'

    def test_withdrawn_route_not_in_cache_after_consume(self):
        """Invariant: Withdrawn routes are removed from cache after consume.

        Once a withdraw update is consumed, the route must not be in cache.
        """
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)
        consume_updates(rib)

        assert rib.in_cache(route), 'Route should be in cache after add'

        rib.del_from_rib(route)
        consume_updates(rib)

        assert not rib.in_cache(route), 'INVARIANT: Withdrawn route must not be in cache'

    def test_multiple_withdraws_all_remove_from_cache(self):
        """Invariant holds for multiple withdraws."""
        rib = create_rib()

        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for route in routes:
            rib.add_to_rib(route)
        consume_updates(rib)

        # Withdraw all
        for route in routes:
            rib.del_from_rib(route)
        consume_updates(rib)

        for route in routes:
            assert not rib.in_cache(route), f'INVARIANT: Withdrawn route {route.nlri} must not be in cache'

    def test_new_nlri_count_matches_attr_af_nlri_count(self):
        """Invariant: _new_nlri count equals total count in _new_attr_af_nlri.

        These two structures must stay synchronized.
        """
        rib = create_rib()

        # Add routes with different attributes
        route1 = create_route('10.0.1.0/24', origin=Origin.IGP)
        route2 = create_route('10.0.2.0/24', origin=Origin.EGP)
        route3 = create_route('10.0.3.0/24', origin=Origin.IGP)

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        rib.add_to_rib(route3)

        nlri_count = count_new_nlri(rib)
        attr_af_count = count_attr_af_nlri(rib)

        assert nlri_count == attr_af_count, 'INVARIANT: _new_nlri count must match _new_attr_af_nlri count'
        assert nlri_count == 3, 'Should have 3 pending routes'

    def test_counts_match_after_del_from_rib(self):
        """Invariant holds when del_from_rib cancels pending announce."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)

        # Cancel one
        rib.del_from_rib(route1)

        nlri_count = count_new_nlri(rib)
        attr_af_count = count_attr_af_nlri(rib)

        assert nlri_count == attr_af_count, 'INVARIANT: counts must match after del_from_rib'
        assert nlri_count == 1, 'Should have 1 pending route after cancellation'

    def test_disabled_rib_never_pending(self):
        """Invariant: Disabled RIB never reports pending."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)

        assert not rib.pending(), 'INVARIANT: Disabled RIB must never be pending'

    def test_disabled_rib_yields_nothing(self):
        """Invariant: Disabled RIB yields no updates."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)

        updates = consume_updates(rib)

        assert len(updates) == 0, 'INVARIANT: Disabled RIB must yield no updates'


# ==============================================================================
# Test Cache Invariants
# ==============================================================================


class TestCacheInvariants:
    """Property-based invariants for Cache behavior."""

    def test_update_cache_makes_in_cache_true(self):
        """Invariant: update_cache() makes in_cache() return True.

        After updating cache with a route, it must be findable.
        """
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.update_cache(route)

        assert rib.in_cache(route), 'INVARIANT: update_cache() must make in_cache() return True'

    def test_update_cache_with_multiple_routes(self):
        """Invariant holds for multiple routes."""
        rib = create_rib()

        routes = [create_route(f'10.0.{i}.0/24') for i in range(5)]
        for route in routes:
            rib.update_cache(route)

        for route in routes:
            assert rib.in_cache(route), f'INVARIANT: {route.nlri} must be in cache'

    def test_update_cache_withdraw_makes_in_cache_false(self):
        """Invariant: update_cache_withdraw() makes in_cache() return False.

        After withdrawing from cache, route must not be findable.
        """
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.update_cache(route)

        assert rib.in_cache(route), 'Should be in cache before withdraw'

        rib.update_cache_withdraw(route.nlri)

        assert not rib.in_cache(route), 'INVARIANT: update_cache_withdraw() must make in_cache() return False'

    def test_update_cache_withdraw_with_multiple_routes(self):
        """Invariant holds when withdrawing some routes but not all."""
        rib = create_rib()

        routes = [create_route(f'10.0.{i}.0/24') for i in range(5)]
        for route in routes:
            rib.update_cache(route)

        # Withdraw routes 0, 2, 4
        rib.update_cache_withdraw(routes[0].nlri)
        rib.update_cache_withdraw(routes[2].nlri)
        rib.update_cache_withdraw(routes[4].nlri)

        # Check withdrawn routes
        assert not rib.in_cache(routes[0]), 'Route 0 must not be in cache'
        assert not rib.in_cache(routes[2]), 'Route 2 must not be in cache'
        assert not rib.in_cache(routes[4]), 'Route 4 must not be in cache'

        # Check remaining routes
        assert rib.in_cache(routes[1]), 'Route 1 must still be in cache'
        assert rib.in_cache(routes[3]), 'Route 3 must still be in cache'

    def test_clear_cache_empties_seen(self):
        """Invariant: clear_cache() empties _seen dict.

        After clearing, no routes should be cached.
        """
        rib = create_rib()

        # Add several routes
        routes = [create_route(f'10.0.{i}.0/24') for i in range(5)]
        for route in routes:
            rib.update_cache(route)

        assert count_cached_routes(rib) == 5, 'Should have 5 cached routes'

        rib.clear_cache()

        assert count_cached_routes(rib) == 0, 'INVARIANT: clear_cache() must empty _seen'
        assert len(rib._seen) == 0, '_seen dict must be empty'

    def test_clear_cache_makes_in_cache_false_for_all(self):
        """Invariant: After clear_cache(), in_cache() returns False for all routes."""
        rib = create_rib()

        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for route in routes:
            rib.update_cache(route)

        rib.clear_cache()

        for route in routes:
            assert not rib.in_cache(route), f'INVARIANT: {route.nlri} must not be in cache after clear'


# ==============================================================================
# Test Consistency Invariants
# ==============================================================================


class TestConsistencyInvariants:
    """Invariants about consistency between operations and state."""

    def test_announce_then_withdraw_leaves_no_cache(self):
        """Invariant: Announce followed by withdraw leaves route uncached."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)
        consume_updates(rib)

        assert rib.in_cache(route), 'Route should be cached after announce'

        rib.del_from_rib(route)
        consume_updates(rib)

        assert not rib.in_cache(route), 'INVARIANT: Route must not be cached after withdraw'

    def test_withdraw_without_announce_not_in_cache(self):
        """Invariant: Withdraw of non-cached route doesn't add it to cache."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')

        # Withdraw without ever announcing
        rib.del_from_rib(route)
        consume_updates(rib)

        assert not rib.in_cache(route), 'INVARIANT: Withdraw-only route must not be in cache'

    def test_cached_routes_snapshot_consistency(self):
        """Invariant: cached_routes() provides consistent snapshot.

        The iterator should yield consistent data even if called twice.
        """
        rib = create_rib()

        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for route in routes:
            rib.add_to_rib(route)
        consume_updates(rib)

        # Get snapshots twice
        snapshot1 = set(r.index() for r in rib.cached_routes(None))
        snapshot2 = set(r.index() for r in rib.cached_routes(None))

        assert snapshot1 == snapshot2, 'INVARIANT: cached_routes() must be consistent across calls'

    def test_pending_state_consistency(self):
        """Invariant: pending() state is consistent with internal structures.

        If _new_nlri or _pending_withdraws is non-empty, pending() must be True.
        """
        rib = create_rib()

        # Initially not pending
        assert not rib.pending()
        assert len(rib._new_nlri) == 0

        # Add route
        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)

        assert rib.pending() == (len(rib._new_nlri) > 0 or len(rib._pending_withdraws) > 0), (
            'INVARIANT: pending() must reflect internal state'
        )

    def test_clear_resets_all_pending_state(self):
        """Invariant: clear() resets all pending state."""
        rib = create_rib()

        # Add routes
        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for route in routes:
            rib.add_to_rib(route)

        assert rib.pending(), 'Should be pending before clear'

        rib.clear()

        assert not rib.pending(), 'INVARIANT: clear() must reset pending state'
        assert len(rib._new_nlri) == 0, '_new_nlri must be empty'
        assert len(rib._new_attr_af_nlri) == 0, '_new_attr_af_nlri must be empty'
        assert len(rib._pending_withdraws) == 0, '_pending_withdraws must be empty'

    def test_reset_clears_pending_but_keeps_cache(self):
        """Invariant: reset() clears pending state but preserves cache."""
        rib = create_rib()

        # Add and cache routes
        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for route in routes:
            rib.add_to_rib(route)
        consume_updates(rib)

        # Add more (pending but not cached yet)
        new_route = create_route('10.0.99.0/24')
        rib.add_to_rib(new_route)

        assert rib.pending(), 'Should be pending'
        cached_before = count_cached_routes(rib)

        rib.reset()

        assert not rib.pending(), 'INVARIANT: reset() must clear pending'
        cached_after = count_cached_routes(rib)
        assert cached_after == cached_before, 'INVARIANT: reset() must preserve cache'


# ==============================================================================
# Test Index Invariants
# ==============================================================================


class TestIndexInvariants:
    """Invariants about route indexing."""

    def test_same_route_same_index(self):
        """Invariant: Same route always produces same index."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.0.0/24')

        assert route1.index() == route2.index(), 'INVARIANT: Same route must produce same index'

    def test_different_prefix_different_index(self):
        """Invariant: Different prefixes produce different indices."""
        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        assert route1.index() != route2.index(), 'INVARIANT: Different prefixes must have different indices'

    def test_same_prefix_different_mask_different_index(self):
        """Invariant: Same prefix with different mask produces different index."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.0.0/25')

        assert route1.index() != route2.index(), 'INVARIANT: Different masks must produce different indices'

    def test_cache_uses_consistent_indexing(self):
        """Invariant: Cache lookup uses same indexing as storage.

        A route stored in cache must be findable by any route with same prefix.
        """
        rib = create_rib()

        route1 = create_route('10.0.0.0/24')
        rib.update_cache(route1)

        # Create "same" route separately
        route2 = create_route('10.0.0.0/24')

        # Both should have same index
        assert route1.index() == route2.index(), 'Same routes must have same index'

        # Route2 should find route1 in cache
        assert rib.in_cache(route2), 'INVARIANT: Cache lookup must use consistent indexing'


# ==============================================================================
# Test Idempotency Invariants
# ==============================================================================


class TestIdempotencyInvariants:
    """Invariants about idempotent operations."""

    def test_double_consume_is_empty(self):
        """Invariant: Consuming updates twice yields empty on second call.

        Once updates are consumed, they're gone.
        """
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)

        updates1 = consume_updates(rib)
        updates2 = consume_updates(rib)

        assert len(updates1) > 0, 'First consume should have updates'
        assert len(updates2) == 0, 'INVARIANT: Second consume must be empty'

    def test_clear_cache_is_idempotent(self):
        """Invariant: Calling clear_cache() twice has same effect as once."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.update_cache(route)

        rib.clear_cache()
        rib.clear_cache()

        assert count_cached_routes(rib) == 0, 'INVARIANT: clear_cache() must be idempotent'

    def test_withdraw_same_route_twice_one_update(self):
        """Invariant: Withdrawing same route twice yields one withdraw."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)
        consume_updates(rib)

        # Withdraw twice
        rib.del_from_rib(route)
        rib.del_from_rib(route)

        updates = consume_updates(rib)
        _, withdraws = count_announces_withdraws(updates)

        assert withdraws == 1, 'INVARIANT: Duplicate withdraws must be deduplicated'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
