#!/usr/bin/env python3
"""
Tests for RIB replace_restart() and replace_reload() operations.

These methods are critical for:
- replace_restart(): Re-establishing BGP session (graceful restart)
- replace_reload(): Configuration reload without session restart

Both methods handle the transition between previous and new route sets.
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


def create_route(prefix: str, afi: AFI = AFI.ipv4) -> Route:
    """Create a Route for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, afi, SAFI.unicast)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(Origin.IGP)

    return Route(nlri, attrs, nexthop=IP.NoNextHop)


def create_rib(cache: bool = True) -> OutgoingRIB:
    """Create a standard test RIB."""
    return OutgoingRIB(cache=cache, families={(AFI.ipv4, SAFI.unicast)})


def consume_updates(rib: OutgoingRIB) -> List:
    """Consume all pending updates from the RIB."""
    return list(rib.updates(grouped=False))


def count_announces_withdraws(updates: list) -> tuple[int, int]:
    """Count total announces and withdraws across all updates."""
    announces = sum(len(u.announces) for u in updates)
    withdraws = sum(len(u.withdraws) for u in updates)
    return announces, withdraws


def get_cached_prefixes(rib: OutgoingRIB) -> set[str]:
    """Get set of prefixes currently cached."""
    prefixes = set()
    for route in rib.cached_routes(None):
        # Extract prefix from NLRI string representation
        prefixes.add(str(route.nlri))
    return prefixes


# ==============================================================================
# Test replace_restart()
# ==============================================================================


class TestReplaceRestart:
    """Tests for replace_restart() - used after connection re-established.

    replace_restart() is called when:
    - BGP session is re-established after failure
    - Graceful restart completes

    Behavior:
    - All cached routes are re-added to pending queue
    - Routes in 'previous' but not in 'new' are withdrawn
    """

    def test_replace_restart_readds_cached_routes(self):
        """replace_restart() re-adds all cached routes to pending."""
        rib = create_rib()

        # Add and cache routes
        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # Verify cached
        assert len(list(rib.cached_routes(None))) == 2

        # Call replace_restart with empty previous/new (simulates session restart)
        rib.replace_restart(previous=[], new=[])

        # Should have pending updates (cached routes re-added)
        assert rib.pending()

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Both cached routes should be re-announced
        assert announces == 2

    def test_replace_restart_withdraws_routes_not_in_new(self):
        """Routes in previous but not in new are withdrawn.

        Implementation:
        1. Re-add all cached routes (force=True)
        2. Withdraw routes in (previous - new)

        del_from_rib cancels pending announces for same route,
        so only routes NOT withdrawn get announced.
        """
        rib = create_rib()

        # Create routes
        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')
        route3 = create_route('10.0.3.0/24')

        # Add all routes and cache
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        rib.add_to_rib(route3)
        consume_updates(rib)

        # previous has all 3, new only has route1
        previous = [route1, route2, route3]
        new = [route1]

        rib.replace_restart(previous=previous, new=new)
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route2 and route3 withdrawn (in previous, not in new)
        assert withdraws == 2
        # Only route1 announced (route2/3 announces cancelled by withdrawals)
        assert announces == 1

    def test_replace_restart_with_empty_previous(self):
        """Empty previous list - just re-announce cached routes."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        rib.add_to_rib(route1)
        consume_updates(rib)

        rib.replace_restart(previous=[], new=[])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # No withdrawals (nothing in previous)
        assert withdraws == 0
        # Cached route re-announced
        assert announces == 1

    def test_replace_restart_with_empty_new(self):
        """Empty new list - withdraw all routes from previous.

        Since all cached routes are also in previous (and new is empty),
        all announces get cancelled by withdrawals.
        """
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # previous has both, new is empty
        rib.replace_restart(previous=[route1, route2], new=[])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Both should be withdrawn
        assert withdraws == 2
        # Announces cancelled by withdrawals (same routes)
        assert announces == 0

    def test_replace_restart_disjoint_sets(self):
        """Previous and new have no overlap.

        Cache has 3 routes. Previous={route1}, New={route2}.
        route1 gets withdrawn (cancels its announce).
        route2 and route3 get announced (not in withdrawal set).
        """
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')
        route3 = create_route('10.0.3.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        rib.add_to_rib(route3)
        consume_updates(rib)

        # previous has route1, new has route2 (disjoint)
        rib.replace_restart(previous=[route1], new=[route2])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route1 withdrawn (in previous, not in new)
        assert withdraws == 1
        # route2 and route3 announced (route1's announce cancelled)
        assert announces == 2

    def test_replace_restart_identical_sets(self):
        """Previous and new are identical - no withdrawals."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # previous and new are the same
        rib.replace_restart(previous=[route1, route2], new=[route1, route2])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # No withdrawals (all in new)
        assert withdraws == 0
        # Both cached routes re-announced
        assert announces == 2

    def test_replace_restart_disabled_rib(self):
        """replace_restart on disabled RIB is no-op."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        route = create_route('10.0.1.0/24')

        # Should not crash
        rib.replace_restart(previous=[route], new=[])

        assert not rib.pending()


# ==============================================================================
# Test replace_reload()
# ==============================================================================


class TestReplaceReload:
    """Tests for replace_reload() - used after config reload.

    replace_reload() is called when:
    - Configuration is reloaded without session restart
    - Incremental route updates are needed

    Behavior:
    - Routes in previous but not in new are withdrawn
    - Routes in new but not in previous are added
    - Routes in both are left unchanged
    """

    def test_replace_reload_adds_new_routes(self):
        """Routes in new but not in previous are added."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        # Add route1, cache it
        rib.add_to_rib(route1)
        consume_updates(rib)

        # Reload: previous has route1, new has both
        rib.replace_reload(previous=[route1], new=[route1, route2])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route2 is new - should be announced
        assert announces == 1
        assert withdraws == 0

    def test_replace_reload_withdraws_removed_routes(self):
        """Routes in previous but not in new are withdrawn."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        # Add both, cache them
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # Reload: previous has both, new only has route1
        rib.replace_reload(previous=[route1, route2], new=[route1])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route2 removed - should be withdrawn
        assert withdraws == 1
        assert announces == 0

    def test_replace_reload_ignores_unchanged_routes(self):
        """Routes in both previous and new are not re-announced."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')

        # Add and cache
        rib.add_to_rib(route1)
        consume_updates(rib)

        # Reload with same route in both
        rib.replace_reload(previous=[route1], new=[route1])

        # Nothing should be pending
        assert not rib.pending()

    def test_replace_reload_with_empty_previous(self):
        """Empty previous - all routes in new are added."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        # No previous routes, new has 2
        rib.replace_reload(previous=[], new=[route1, route2])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Both should be announced
        assert announces == 2
        assert withdraws == 0

    def test_replace_reload_with_empty_new(self):
        """Empty new - all routes in previous are withdrawn."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        # Add and cache
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # Reload: previous has both, new is empty
        rib.replace_reload(previous=[route1, route2], new=[])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Both should be withdrawn
        assert withdraws == 2
        assert announces == 0

    def test_replace_reload_mixed_add_remove(self):
        """Mix of adds and removes."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')
        route3 = create_route('10.0.3.0/24')

        # Add route1 and route2, cache them
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # Reload: remove route2, add route3, keep route1
        rib.replace_reload(previous=[route1, route2], new=[route1, route3])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route3 added, route2 withdrawn
        assert announces == 1
        assert withdraws == 1

    def test_replace_reload_disjoint_sets(self):
        """Previous and new have no overlap - full replacement."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        # Add route1, cache it
        rib.add_to_rib(route1)
        consume_updates(rib)

        # Reload: completely different route
        rib.replace_reload(previous=[route1], new=[route2])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route1 withdrawn, route2 added
        assert announces == 1
        assert withdraws == 1

    def test_replace_reload_disabled_rib(self):
        """replace_reload on disabled RIB is no-op."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        route = create_route('10.0.1.0/24')

        # Should not crash
        rib.replace_reload(previous=[route], new=[])

        assert not rib.pending()


# ==============================================================================
# Edge Cases
# ==============================================================================


class TestReplaceEdgeCases:
    """Edge cases for replace operations."""

    def test_replace_restart_on_empty_rib(self):
        """replace_restart on RIB with no cached routes."""
        rib = create_rib()

        route = create_route('10.0.1.0/24')

        # RIB is empty (no cached routes)
        rib.replace_restart(previous=[route], new=[])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route should be withdrawn
        assert withdraws == 1
        # No cached routes to re-announce
        assert announces == 0

    def test_replace_reload_on_empty_rib(self):
        """replace_reload on RIB with no cached routes."""
        rib = create_rib()

        route = create_route('10.0.1.0/24')

        # RIB is empty, new has one route
        rib.replace_reload(previous=[], new=[route])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Route should be announced
        assert announces == 1
        assert withdraws == 0

    def test_replace_with_duplicate_routes_in_list(self):
        """Duplicate routes in new list cause extra adds.

        Implementation iterates new list - first route1 pops from indexed,
        second route1 finds nothing to pop and adds it.
        This is arguably a bug but documents current behavior.
        """
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # new has duplicates of route1
        rib.replace_reload(previous=[route1, route2], new=[route1, route1])
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # route2 withdrawn
        assert withdraws == 1
        # Duplicate route1 causes extra add (2nd iteration finds nothing to pop)
        assert announces == 1

    def test_replace_restart_cache_state(self):
        """Verify cache state after replace_restart."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        consume_updates(rib)

        # Cache should have 2 routes
        assert len(list(rib.cached_routes(None))) == 2

        # Restart - cache should still have routes
        rib.replace_restart(previous=[route1], new=[])
        consume_updates(rib)

        # Cache should still have routes (restart re-announces, doesn't clear)
        cached = list(rib.cached_routes(None))
        assert len(cached) >= 1  # May be modified by withdrawals

    def test_replace_reload_cache_state(self):
        """Verify cache state after replace_reload."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        consume_updates(rib)

        # Add route2 via reload
        rib.replace_reload(previous=[route1], new=[route1, route2])
        consume_updates(rib)

        # Cache should now have both routes
        cached = list(rib.cached_routes(None))
        assert len(cached) == 2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
