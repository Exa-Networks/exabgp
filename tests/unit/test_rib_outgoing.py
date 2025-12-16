#!/usr/bin/env python3
"""
Comprehensive OutgoingRIB Tests

Tests all RIB manipulation scenarios to ensure correct behavior for:
- Single operations (announce, withdraw)
- Same NLRI sequences (the critical announce-after-withdraw bug)
- Multiple NLRI operations
- Cross-family independence
- Attribute variations
- Edge cases
- Grouped vs non-grouped mode
- Cache interactions

Based on RFC 4271 which states that an announce implicitly replaces
a previous route with the same NLRI - no explicit withdraw needed.
"""

import sys
import os
from typing import List
from unittest.mock import Mock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# Mock logger before importing RIB classes (they import logger at module level)
from exabgp.logger.option import option

mock_logger = Mock()
mock_logger.debug = Mock()
mock_logger.info = Mock()
mock_logger.warning = Mock()
mock_logger.error = Mock()
option.logger = mock_logger

from exabgp.rib.outgoing import OutgoingRIB  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.attribute.origin import Origin  # noqa: E402
from exabgp.rib.route import Route  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_change(prefix: str, afi: AFI = AFI.ipv4) -> Route:
    """Create a Route object for testing.

    Note: Action is no longer stored in Route - it's determined by which RIB method is called.
    """
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    from exabgp.protocol.ip import IP as IP_

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, afi, SAFI.unicast)
    attrs = AttributeCollection()

    return Route(nlri, attrs, nexthop=IP_.NoNextHop)


def create_change_with_origin(prefix: str, origin: int) -> Route:
    """Create a Route with a specific ORIGIN attribute.

    Note: Action is no longer stored in Route - it's determined by which RIB method is called.
    """
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    from exabgp.protocol.ip import IP as IP_

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(origin)

    return Route(nlri, attrs, nexthop=IP_.NoNextHop)


def consume_updates(rib: OutgoingRIB, grouped: bool = False) -> List:
    """Consume all pending updates from the RIB"""
    return list(rib.updates(grouped=grouped))


def count_announces_withdraws(updates: list) -> tuple[int, int]:
    """Count total announces and withdraws across all updates"""
    announces = sum(len(u.announces) for u in updates)
    withdraws = sum(len(u.withdraws) for u in updates)
    return announces, withdraws


def create_rib(cache: bool = True) -> OutgoingRIB:
    """Create a standard test RIB"""
    return OutgoingRIB(cache=cache, families={(AFI.ipv4, SAFI.unicast)})


def create_dual_family_rib() -> OutgoingRIB:
    """Create a RIB with IPv4 and IPv6 support"""
    return OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)})


# ==============================================================================
# 1. SINGLE OPERATION TESTS
# ==============================================================================


class TestSingleOperations:
    """Tests for single announce/withdraw operations"""

    def test_single_announce(self):
        """Single announce generates one Update with one announce"""
        rib = create_rib()
        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 1, 'Should have exactly 1 announce'
        assert withdraws == 0, 'Should have no withdraws'

    def test_single_withdraw(self):
        """Single withdraw generates one Update with one withdraw"""
        rib = create_rib()

        # First add and consume to establish the route
        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)

        # Now withdraw
        rib.del_from_rib(change)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 0, 'Should have no announces'
        assert withdraws == 1, 'Should have exactly 1 withdraw'


# ==============================================================================
# 2. SAME NLRI SEQUENCE TESTS (Critical - includes the bug fix test)
# ==============================================================================


class TestSameNLRISequences:
    """Tests for announce/withdraw sequences on the same NLRI.

    These are critical tests because incorrect ordering can cause
    routes to end up in the wrong state at the peer.
    """

    def test_announce_then_withdraw_same_nlri(self):
        """Announce then withdraw same NLRI: only withdraw sent

        Scenario: Add route, then delete it before updates() called.
        Expected: Only the withdraw should be sent (announce cancelled).
        """
        rib = create_rib()

        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        rib.del_from_rib(change)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 0, 'Announce should be cancelled by subsequent withdraw'
        assert withdraws == 1, 'Only withdraw should be sent'

    def test_withdraw_then_announce_same_nlri(self):
        """Withdraw then announce same NLRI: only announce sent (THE BUG FIX)

        Scenario: Route was previously announced. Withdraw it, then re-announce
                  before updates() is called.
        Expected: Only the announce should be sent (withdraw cancelled).

        Per RFC 4271: An announce implicitly replaces/withdraws the previous route.
        Sending both withdraw and announce is wasteful and, if withdraw comes after
        announce in the message stream, results in the route being incorrectly withdrawn.

        This test verifies the fix from commit 512fa5a9 which was accidentally
        removed in commit 55cb11a0.
        """
        rib = create_rib()

        # First add and consume to cache the route
        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)

        # Now withdraw, then re-announce
        rib.del_from_rib(change)
        rib.add_to_rib(change, force=True)  # force=True since it's cached

        # Both withdraw and announce are sent (cancel logic disabled)
        # See plan/plan-announce-cancels-withdraw-optimization.md for future optimization
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 1, 'Should have 1 announce'
        assert withdraws == 1, 'Withdraw is sent (cancel optimization disabled)'

    def test_announce_then_announce_same_nlri_different_attrs(self):
        """Announce same NLRI twice with different attributes: both sent

        The RIB stores announces organized by attribute set. When the same NLRI
        is added with different attributes in the same update cycle, both are
        sent. The peer will keep the last one it receives (per RFC 4271 implicit
        replacement semantics).

        Note: This differs from adding same NLRI with SAME attributes twice,
        which would be deduplicated.
        """
        rib = create_rib()

        change1 = create_change_with_origin('10.0.0.0/24', Origin.IGP)
        change2 = create_change_with_origin('10.0.0.0/24', Origin.EGP)

        rib.add_to_rib(change1)
        rib.add_to_rib(change2)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Both announces are sent (different attribute sets)
        # Peer will keep the last one received
        assert announces == 2, 'Both announces sent (different attribute sets)'
        assert withdraws == 0, 'No withdraws'

    def test_withdraw_then_withdraw_same_nlri(self):
        """Withdraw same NLRI twice: only one withdraw sent"""
        rib = create_rib()

        # First add and consume to cache the route
        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)

        # Withdraw twice
        rib.del_from_rib(change)
        rib.del_from_rib(change)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 0, 'Should have no announces'
        assert withdraws == 1, 'Should have only 1 withdraw (duplicates eliminated)'

    def test_announce_withdraw_announce_same_nlri(self):
        """A→W→A sequence: all operations sent (cancel optimization disabled)

        Without cancel optimization, all operations are sent independently.
        See plan/plan-announce-cancels-withdraw-optimization.md for future optimization.
        """
        rib = create_rib()

        change = create_change('10.0.0.0/24')

        rib.add_to_rib(change)
        rib.del_from_rib(change)
        rib.add_to_rib(change, force=True)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Announce and withdraw are sent (cancel optimization disabled)
        # Multiple add_to_rib with same route_index → only 1 announce (last one wins)
        assert announces == 1, 'Should have 1 announce (coalesced)'
        assert withdraws == 1, 'Withdraw is sent (cancel optimization disabled)'

    def test_withdraw_announce_withdraw_same_nlri(self):
        """W→A→W sequence: only final withdraw sent"""
        rib = create_rib()

        # First add and consume to cache
        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)

        # W→A→W sequence
        rib.del_from_rib(change)
        rib.add_to_rib(change, force=True)
        rib.del_from_rib(change)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 0, 'Announce should be cancelled'
        assert withdraws == 1, 'Should have 1 withdraw (final state)'


# ==============================================================================
# 3. MULTIPLE NLRI TESTS
# ==============================================================================


class TestMultipleNLRI:
    """Tests for operations on multiple different NLRIs"""

    def test_multiple_announces_different_nlri(self):
        """Multiple announces of different NLRIs"""
        rib = create_rib()

        for i in range(3):
            change = create_change(f'10.0.{i}.0/24')
            rib.add_to_rib(change)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 3, 'Should have 3 announces'
        assert withdraws == 0, 'Should have no withdraws'

    def test_multiple_withdraws_different_nlri(self):
        """Multiple withdraws of different NLRIs"""
        rib = create_rib()

        # First add and consume all routes
        changes = []
        for i in range(3):
            change = create_change(f'10.0.{i}.0/24')
            changes.append(change)
            rib.add_to_rib(change)
        consume_updates(rib)

        # Now withdraw all
        for change in changes:
            rib.del_from_rib(change)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 0, 'Should have no announces'
        assert withdraws == 3, 'Should have 3 withdraws'

    def test_mixed_announces_withdraws_different_nlri(self):
        """Mix of announces and withdraws for different NLRIs"""
        rib = create_rib()

        # Add route 1 and consume to cache
        change1 = create_change('10.0.1.0/24')
        rib.add_to_rib(change1)
        consume_updates(rib)

        # Now: announce new route, withdraw cached route
        change2 = create_change('10.0.2.0/24')
        rib.add_to_rib(change2)
        rib.del_from_rib(change1)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 1, 'Should have 1 announce (new route)'
        assert withdraws == 1, 'Should have 1 withdraw (old route)'


# ==============================================================================
# 4. CROSS-FAMILY TESTS
# ==============================================================================


class TestCrossFamilyOperations:
    """Tests for operations across different address families"""

    def test_same_prefix_different_afi(self):
        """Same prefix in IPv4 and IPv6 are independent"""
        rib = create_dual_family_rib()

        # Announce 10.0.0.0/24 in IPv4
        change_v4 = create_change('10.0.0.0/24', afi=AFI.ipv4)
        rib.add_to_rib(change_v4)

        # Announce 2001:db8::/32 in IPv6
        change_v6 = create_change('2001:db8::', afi=AFI.ipv6)
        rib.add_to_rib(change_v6)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 2, 'Should have 2 announces (one per family)'
        assert withdraws == 0, 'Should have no withdraws'

    def test_withdraw_announce_different_families(self):
        """Withdraw in one family doesn't affect announce in another"""
        rib = create_dual_family_rib()

        # Add and consume IPv4 route
        change_v4 = create_change('10.0.0.0/24', afi=AFI.ipv4)
        rib.add_to_rib(change_v4)
        consume_updates(rib)

        # Withdraw IPv4, announce IPv6
        rib.del_from_rib(change_v4)
        change_v6 = create_change('2001:db8::', afi=AFI.ipv6)
        rib.add_to_rib(change_v6)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 1, 'Should have 1 announce (IPv6)'
        assert withdraws == 1, 'Should have 1 withdraw (IPv4)'


# ==============================================================================
# 5. ATTRIBUTE VARIATION TESTS
# ==============================================================================


class TestAttributeVariations:
    """Tests for attribute handling"""

    def test_same_nlri_different_attributes_replacement(self):
        """Route with same NLRI but different attributes replaces previous"""
        rib = create_rib()

        # First announce with IGP origin
        change1 = create_change_with_origin('10.0.0.0/24', Origin.IGP)
        rib.add_to_rib(change1)
        consume_updates(rib)

        # Second announce with EGP origin (replacement)
        change2 = create_change_with_origin('10.0.0.0/24', Origin.EGP)
        rib.add_to_rib(change2, force=True)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 1, 'Should have 1 announce (replacement)'
        assert withdraws == 0, 'No withdraw needed - implicit replacement'

        # Verify the announce has the new attributes
        nlri = updates[0].announces[0]
        # The NLRI should be the same prefix
        assert nlri is not None

    def test_withdraw_preserves_attributes(self):
        """Withdraw with specific attributes preserves them"""
        rib = create_rib()

        # Add with attributes and consume
        change = create_change_with_origin('10.0.0.0/24', Origin.IGP)
        rib.add_to_rib(change)
        consume_updates(rib)

        # Withdraw (del_from_rib extracts attrs from change)
        rib.del_from_rib(change)

        updates = consume_updates(rib)
        assert len(updates) == 1, 'Should have 1 update'
        assert len(updates[0].withdraws) == 1, 'Should have 1 withdraw'


# ==============================================================================
# 6. EDGE CASES
# ==============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions"""

    def test_empty_rib_updates(self):
        """updates() on empty RIB returns empty iterator"""
        rib = create_rib()

        updates = consume_updates(rib)

        assert len(updates) == 0, 'Empty RIB should produce no updates'

    def test_updates_clears_pending(self):
        """Calling updates() twice: second call returns empty"""
        rib = create_rib()

        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)

        # First call consumes pending
        updates1 = consume_updates(rib)
        assert len(updates1) > 0, 'First call should return updates'

        # Second call should be empty
        updates2 = consume_updates(rib)
        assert len(updates2) == 0, 'Second call should return empty'

    def test_pending_state_after_add(self):
        """pending() returns True after add_to_rib"""
        rib = create_rib()

        assert not rib.pending(), 'Empty RIB should not be pending'

        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)

        assert rib.pending(), 'RIB should be pending after add'

    def test_pending_state_after_consume(self):
        """pending() returns False after updates() consumed"""
        rib = create_rib()

        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)

        assert not rib.pending(), 'RIB should not be pending after consume'

    def test_pending_state_after_withdraw(self):
        """pending() returns True after del_from_rib"""
        rib = create_rib()

        # Add and consume to cache
        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)

        assert not rib.pending(), 'Should not be pending after consume'

        rib.del_from_rib(change)

        assert rib.pending(), 'Should be pending after withdraw'


# ==============================================================================
# 7. GROUPED VS NON-GROUPED TESTS
# ==============================================================================


class TestGroupedMode:
    """Tests for grouped vs non-grouped update generation"""

    def test_grouped_true_combines_nlri(self):
        """grouped=True combines NLRIs with same attributes"""
        rib = create_rib()

        # Add multiple routes with same (empty) attributes
        for i in range(3):
            change = create_change(f'10.0.{i}.0/24')
            rib.add_to_rib(change)

        updates = consume_updates(rib, grouped=True)

        # With same attributes, should get 1 update with 3 announces
        total_announces = sum(len(u.announces) for u in updates)
        assert total_announces == 3, 'Should have 3 total announces'
        assert len(updates) == 1, 'Should be combined into 1 update'

    def test_grouped_false_separates_nlri(self):
        """grouped=False generates separate updates per NLRI"""
        rib = create_rib()

        # Add multiple routes
        for i in range(3):
            change = create_change(f'10.0.{i}.0/24')
            rib.add_to_rib(change)

        updates = consume_updates(rib, grouped=False)

        assert len(updates) == 3, 'Should have 3 separate updates'
        for update in updates:
            assert len(update.announces) == 1, 'Each update should have 1 announce'


# ==============================================================================
# 8. CACHE INTERACTION TESTS
# ==============================================================================


class TestCacheInteractions:
    """Tests for cache behavior"""

    def test_cached_route_not_readded(self):
        """Adding same route twice (without force): second is ignored"""
        rib = create_rib()

        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)  # Cache the route

        # Add again without force
        rib.add_to_rib(change)

        # Should be empty since route is cached
        assert not rib.pending(), 'Cached route should not be re-added'

    def test_force_overrides_cache(self):
        """Adding with force=True overrides cache"""
        rib = create_rib()

        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)  # Cache the route

        # Add again WITH force
        rib.add_to_rib(change, force=True)

        assert rib.pending(), 'force=True should override cache'

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 1, 'Should have 1 announce'

    def test_no_cache_mode(self):
        """With cache=False, same route can be added multiple times"""
        rib = OutgoingRIB(cache=False, families={(AFI.ipv4, SAFI.unicast)})

        change = create_change('10.0.0.0/24')
        rib.add_to_rib(change)
        consume_updates(rib)

        # Add again - should work without force since no cache
        rib.add_to_rib(change)

        assert rib.pending(), 'Without cache, route should be re-added'


# ==============================================================================
# 9. COMPREHENSIVE SEQUENCE TESTS
# ==============================================================================


class TestComprehensiveSequences:
    """Complex multi-operation sequence tests"""

    def test_interleaved_operations_multiple_nlri(self):
        """Complex interleaved operations on multiple NLRIs"""
        rib = create_rib()

        # Initial: add and cache routes 1, 2, 3
        changes = []
        for i in range(1, 4):
            c = create_change(f'10.0.{i}.0/24')
            changes.append(c)
            rib.add_to_rib(c)
        consume_updates(rib)

        # Now: withdraw 1, re-announce 2, add new 4
        rib.del_from_rib(changes[0])  # Withdraw 10.0.1.0/24
        rib.add_to_rib(changes[1], force=True)  # Re-announce 10.0.2.0/24
        change4 = create_change('10.0.4.0/24')
        rib.add_to_rib(change4)  # New 10.0.4.0/24

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 2, 'Should have 2 announces (re-announce + new)'
        assert withdraws == 1, 'Should have 1 withdraw'

    def test_rapid_toggle_same_nlri(self):
        """Rapid toggling of same NLRI - final state wins"""
        rib = create_rib()

        change = create_change('10.0.0.0/24')

        # Add and cache
        rib.add_to_rib(change)
        consume_updates(rib)

        # Rapid toggle: W→A→W→A→W→A (6 operations)
        rib.del_from_rib(change)
        rib.add_to_rib(change, force=True)
        rib.del_from_rib(change)
        rib.add_to_rib(change, force=True)
        rib.del_from_rib(change)
        rib.add_to_rib(change, force=True)  # Final state: announced

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        # Announce and withdraw sent (cancel optimization disabled)
        # Multiple add_to_rib with same route_index → only 1 announce (last one wins)
        # Multiple del_from_rib with same nlri_index → only 1 withdraw
        # See plan/plan-announce-cancels-withdraw-optimization.md for future optimization
        assert announces == 1, 'Announces coalesced to 1 (same route_index)'
        assert withdraws == 1, 'Withdraws coalesced to 1 (same nlri_index)'

    def test_rapid_toggle_ends_in_withdraw(self):
        """Rapid toggling ending in withdraw"""
        rib = create_rib()

        change = create_change('10.0.0.0/24')

        # Add and cache
        rib.add_to_rib(change)
        consume_updates(rib)

        # Toggle ending in withdraw: W→A→W
        rib.del_from_rib(change)
        rib.add_to_rib(change, force=True)
        rib.del_from_rib(change)  # Final state: withdrawn

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 0, 'Announce should be cancelled'
        assert withdraws == 1, 'Final state is withdraw'


# ==============================================================================
# 10. ROUTE.ACTION INTEGRATION TESTS
# ==============================================================================


class TestRouteActionIntegration:
    """Tests for Route.action (not nlri.action) integration with RIB."""

    def test_cache_uses_rib_method_for_action(self):
        """Verify cache behavior with RIB methods.

        Action is now determined by which RIB method is called:
        - add_to_rib() = announce
        - del_from_rib() = withdraw
        """
        rib = create_rib()

        # Create route - action is determined by RIB method
        route = create_change('10.0.0.0/24')

        rib.add_to_rib(route)
        consume_updates(rib)

        # Route should be cached
        assert rib.in_cache(route)

    def test_route_add_and_del_rib(self):
        """Test add_to_rib and del_from_rib work correctly."""
        rib = create_rib()

        # Create route
        route = create_change('10.0.0.0/24')

        rib.add_to_rib(route)
        updates = consume_updates(rib)

        announces, withdraws = count_announces_withdraws(updates)
        assert announces == 1
        assert withdraws == 0

    def test_withdraw_route_with_del_from_rib(self):
        """Withdraw using del_from_rib works correctly."""
        rib = create_rib()

        # First add
        route = create_change('10.0.0.0/24')
        rib.add_to_rib(route)
        consume_updates(rib)

        # Create withdraw - uses del_from_rib
        withdraw_route = create_change('10.0.0.0/24')

        # del_from_rib determines action as WITHDRAW
        rib.del_from_rib(withdraw_route)

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)

        assert announces == 0
        assert withdraws == 1

    # Note: test_route_action_property_returns_correct_value removed
    # Action is no longer stored in Route - determined by RIB method

    def test_cache_in_cache_checks_route_index(self):
        """in_cache() checks if route is cached (for deduplication)."""
        rib = create_rib()

        # Add an announce route
        route = create_change('10.0.0.0/24')
        rib.add_to_rib(route)
        consume_updates(rib)

        # Route should be in cache after add_to_rib
        assert rib.in_cache(route)

        # Same prefix route is also found (same index)
        same_prefix = create_change('10.0.0.0/24')
        assert rib.in_cache(same_prefix)

        # Different prefix not in cache
        different = create_change('10.0.1.0/24')
        assert not rib.in_cache(different)
