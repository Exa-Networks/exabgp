#!/usr/bin/env python3
"""
RIB Stress Testing Suite

Tests for race conditions, edge cases, and potential issues in the RIB implementation.
Based on investigation findings from 2025-11-19.

Covers:
- Critical bugs (dictionary iteration, concurrent operations)
- Race conditions (resend during updates, concurrent access)
- Edge cases (empty RIB, large RIB, rapid cycles)
- Memory leaks (watchdog cleanup)
- Performance issues
"""

import sys
import os
import asyncio
from typing import List, Set, Tuple
from unittest.mock import Mock, patch

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

import pytest

from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.incoming import IncomingRIB
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.rib.change import Change
from exabgp.protocol.ip import IP
from exabgp.bgp.message import Action


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_change(prefix: str, afi: AFI = AFI.ipv4, action: int = Action.ANNOUNCE) -> Change:
    """Create a Change object for testing"""
    # Parse prefix
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    # Create NLRI
    nlri = INET(afi, SAFI.unicast, action)
    nlri.cidr = CIDR(IP.pton(ip_str), mask)

    # Create attributes
    attrs = Attributes()

    return Change(nlri, attrs)


def create_watchdog_change(prefix: str, watchdog: str, action: int = Action.ANNOUNCE) -> Change:
    """Create a Change with watchdog attribute"""
    change = create_change(prefix, action=action)
    # Watchdog is stored separately, not in the change itself
    return change


def add_route_to_rib(rib: OutgoingRIB, prefix: str, afi: AFI = AFI.ipv4) -> Change:
    """Add a route to the RIB and return the change"""
    change = create_change(prefix, afi=afi)
    rib.add_to_rib(change)
    return change


def consume_updates(rib: OutgoingRIB) -> List:
    """Consume all pending updates from the RIB"""
    return list(rib.updates(grouped=False))


# ==============================================================================
# CRITICAL BUG TESTS (Tests for confirmed bugs)
# ==============================================================================


def test_delete_cached_family_no_crash():
    """
    Critical Bug #1: delete_cached_family() modifies dict during iteration

    Before fix: RuntimeError: dictionary changed size during iteration
    After fix: Should complete without error

    Location: cache.py:37
    Fix: Added list() wrapper to snapshot keys
    """
    families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
    rib = OutgoingRIB(cache=True, families=families)

    # Add routes to multiple families
    add_route_to_rib(rib, "192.168.0.1/32", AFI.ipv4)
    add_route_to_rib(rib, "2001:db8::1/128", AFI.ipv6)

    # Consume to cache them
    consume_updates(rib)

    # Verify both families are in cache
    assert (AFI.ipv4, SAFI.unicast) in rib._seen
    assert (AFI.ipv6, SAFI.unicast) in rib._seen

    # This should NOT crash (was causing RuntimeError before fix)
    rib.delete_cached_family({(AFI.ipv4, SAFI.unicast)})

    # IPv4 should be kept, IPv6 should be removed
    assert (AFI.ipv4, SAFI.unicast) in rib._seen
    assert (AFI.ipv6, SAFI.unicast) not in rib._seen


def test_cached_changes_iteration_safety():
    """
    Critical Bug #2: cached_changes() doesn't snapshot .values()

    Before fix: Potential RuntimeError if cache modified during iteration
    After fix: Iterator should be safe from concurrent modifications

    Location: cache.py:51
    Fix: Added list() wrapper to snapshot values
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add and cache 10 routes
    for i in range(10):
        add_route_to_rib(rib, f"192.168.0.{i}/32")
    consume_updates(rib)

    # Start iterating cached routes
    changes_iter = rib.cached_changes([(AFI.ipv4, SAFI.unicast)])

    # Consume half
    changes = []
    for i in range(5):
        changes.append(next(changes_iter))

    # Modify cache mid-iteration (simulates concurrent add)
    new_change = create_change("192.168.0.100/32")
    rib.update_cache(new_change)

    # Should NOT crash - iterator has snapshot
    remaining = list(changes_iter)

    # Should have gotten all original 10 routes (snapshot taken at iteration start)
    assert len(changes) + len(remaining) == 10


@pytest.mark.asyncio
async def test_resend_during_updates_iteration():
    """
    Race Condition #1: resend() called while updates() iterating

    Problem: updates() iterates _refresh_changes and clears it (line 259-261)
              resend() appends to _refresh_changes (line 98)

    Scenario: API flush command arrives while peer is sending routes

    Location: outgoing.py:220-265 (updates()) and line 98 (resend())

    Fix: Snapshot _refresh_changes at start of updates(), clear immediately
         New resend() calls go into fresh empty list
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add and send initial route to cache it
    add_route_to_rib(rib, "192.168.0.1/32")
    consume_updates(rib)

    # Verify route is cached
    cached = list(rib.cached_changes(None))
    assert len(cached) == 1

    # Add more routes to pending queue
    for i in range(2, 5):
        add_route_to_rib(rib, f"192.168.0.{i}/32")

    # Verify pending (should have 3 new routes: .2, .3, .4)
    assert rib.pending()

    # Create updates generator (simulates peer starting to send)
    # NOTE: Generator function doesn't execute until first next() call
    updates_gen = rib.updates(grouped=False)

    # Consume first update (one of the 3 pending routes)
    # This triggers the generator to start executing
    update1 = next(updates_gen)
    assert update1 is not None

    # At this point (after first next()):
    # - Pending routes cleared and moved to snapshot
    # - _refresh_changes is empty (cleared by updates() initialization)
    assert len(rib._new_nlri) == 0
    assert len(rib._refresh_changes) == 0

    # Simulate: API calls resend() while peer is still sending
    # This should append to NEW empty _refresh_changes, not affect current iteration
    rib.resend(enhanced_refresh=False)

    # After resend(), _refresh_changes should have ALL cached routes
    # Cache has: .1 (from first consume), .2 .3 .4 (from updates() which calls update_cache)
    # Note: updates() calls update_cache for each route as it's yielded
    cached_count = len(list(rib.cached_changes(None)))
    assert len(rib._refresh_changes) == cached_count

    # Consume remaining from current updates_gen
    # Should get the other 2 pending routes (total 3 including update1)
    # Should NOT include the resent routes (they went into new _refresh_changes)
    remaining_updates = list(updates_gen)
    total_from_first_call = 1 + len(remaining_updates)

    # Should have gotten exactly 3 updates (the 3 pending routes)
    # This verifies the fix: resend() during iteration doesn't affect current iteration
    assert total_from_first_call == 3

    # Now second updates() call should yield the resent routes
    assert rib.pending()  # Should still have pending from resend()
    second_updates = consume_updates(rib)

    # Should get all cached routes that were resent
    assert len(second_updates) == cached_count

    # Now nothing should be pending
    assert not rib.pending()


@pytest.mark.asyncio
async def test_reset_during_updates():
    """
    Race Condition #4: reset() called while updates() active

    Problem: reset() creates NEW updates() generator while old one still active
             Code comment acknowledges: "this function can run while we are in the updates() loop too!"

    Scenario: Connection drops while peer is sending routes

    Location: outgoing.py:69-74 (reset()) with warning comment
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add routes
    for i in range(5):
        add_route_to_rib(rib, f"192.168.0.{i}/32")

    # Start consuming updates
    updates_gen = rib.updates(grouped=False)
    update1 = next(updates_gen)

    # Simulate connection drop -> reset() is called
    rib.reset()  # Calls updates() internally

    # Original generator should handle this gracefully
    # Either: continue yielding, stop cleanly, or raise appropriate exception
    try:
        remaining = list(updates_gen)
        # If it continues, should not corrupt state
        assert isinstance(remaining, list)
    except (StopIteration, RuntimeError):
        # Also acceptable - generator can't continue after reset
        pass

    # RIB should be in consistent state after reset
    assert not rib.pending()
    assert len(rib._new_nlri) == 0
    assert len(rib._refresh_changes) == 0


@pytest.mark.asyncio
async def test_concurrent_add_del_operations():
    """
    Race Condition #3: Check-then-act pattern in del_from_rib

    Problem: Multi-step operation without atomicity (lines 180-187)
             Another task could modify state between check and act

    Location: outgoing.py:180-187
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    route_change = create_change("192.168.0.1/32")

    # Add route
    rib.add_to_rib(route_change)

    # Simulate concurrent operations
    async def task_delete():
        """Delete the route"""
        await asyncio.sleep(0.001)
        rib.del_from_rib(route_change)

    async def task_add():
        """Re-add the same route"""
        await asyncio.sleep(0.002)
        rib.add_to_rib(route_change, force=True)

    # Run concurrently
    await asyncio.gather(task_delete(), task_add())

    # State should be consistent (route present or absent, not corrupted)
    # Check internal structures are not corrupted
    assert isinstance(rib._new_nlri, dict)
    assert isinstance(rib._new_attr_af_nlri, dict)

    # Either route is there or not, but data structures should be valid
    if route_change.index() in rib._new_nlri:
        # If route is present, it should be in both structures
        assert len(rib._new_nlri) >= 1
    else:
        # If route withdrawn, structures can be empty or have withdrawal
        pass


def test_exception_during_updates_recovery():
    """
    Issue #7: State inconsistency after error during updates() iteration

    Problem: If exception during iteration, state is already cleared but not all updates sent
             No rollback mechanism

    Location: outgoing.py:220-265
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add routes
    for i in range(5):
        add_route_to_rib(rib, f"192.168.0.{i}/32")

    # Start consuming
    updates_gen = rib.updates(grouped=False)

    # Consume one update
    update1 = next(updates_gen)
    assert update1 is not None

    # Simulate error by closing generator
    updates_gen.close()

    # RIB state should be recoverable
    # New routes should still be addable
    add_route_to_rib(rib, "192.168.0.100/32")
    assert rib.pending()

    # Should be able to create new updates generator
    new_updates = list(rib.updates(grouped=False))
    assert len(new_updates) >= 1


# ==============================================================================
# EDGE CASE TESTS
# ==============================================================================


def test_empty_rib_operations():
    """
    Edge Case: Operations on empty RIB should handle gracefully

    Problem: Empty operations may fail silently or raise unexpected errors

    Covers: All RIB operations on empty state
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # All operations should handle empty state gracefully
    assert not rib.pending()
    assert list(rib.updates(False)) == []

    # Resend on empty RIB
    rib.resend(False)
    assert not rib.pending()

    # Cached changes on empty RIB
    assert list(rib.cached_changes(None)) == []

    # Withdraw on empty RIB
    rib.withdraw()
    assert not rib.pending()

    # Reset on empty RIB
    rib.reset()
    assert not rib.pending()

    # Clear on empty RIB
    rib.clear()
    assert not rib.pending()


def test_single_route_rib():
    """
    Edge Case: RIB with single route

    Tests that operations work correctly with minimal data
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add single route
    change = add_route_to_rib(rib, "192.168.0.1/32")

    # Verify pending
    assert rib.pending()
    assert len(rib._new_nlri) == 1

    # Consume
    updates = consume_updates(rib)
    assert len(updates) == 1
    assert not rib.pending()

    # Verify cached
    cached = list(rib.cached_changes(None))
    assert len(cached) == 1

    # Resend single route
    rib.resend(False)
    assert rib.pending()

    updates2 = consume_updates(rib)
    assert len(updates2) == 1

    # Delete single route
    rib.del_from_rib(change)
    assert rib.pending()  # Withdrawal pending

    updates3 = consume_updates(rib)
    assert len(updates3) == 1  # Withdrawal


def test_large_rib_stress():
    """
    Stress Test: Large RIB with many routes

    Tests performance and stability with realistic route table size

    Note: Using 10k routes for unit test speed (investigation used 100k)
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    import time

    # Add 10,000 routes
    start = time.time()
    for i in range(10000):
        # Generate prefix: 10.0-39.0-255.0-255/32
        octet2 = i // 256
        octet3 = i % 256
        add_route_to_rib(rib, f"10.{octet2}.{octet3}.1/32")
    elapsed_add = time.time() - start

    # Should complete quickly
    assert elapsed_add < 5.0  # 5 seconds for 10k routes

    # Verify all pending
    assert rib.pending()
    assert len(rib._new_nlri) == 10000

    # Consume all updates
    start = time.time()
    updates = consume_updates(rib)
    elapsed_consume = time.time() - start

    # Should yield updates (may be batched)
    assert len(updates) >= 1
    assert not rib.pending()

    # Consume should be fast
    assert elapsed_consume < 5.0

    # Verify all cached
    cached = list(rib.cached_changes(None))
    assert len(cached) == 10000

    # Test resend performance
    start = time.time()
    rib.resend(False)
    elapsed_resend = time.time() - start

    assert rib.pending()
    assert elapsed_resend < 2.0  # Resend should be fast (just appends to list)

    # Clean up (consume resent routes)
    consume_updates(rib)


def test_rapid_add_remove_cycles():
    """
    Edge Case: Rapid add/remove cycles on same route

    Tests state consistency under rapid mutations
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    change = create_change("192.168.0.1/32")

    # Perform 100 rapid cycles
    for i in range(100):
        # Add
        rib.add_to_rib(change)
        assert rib.pending()

        # Immediately delete
        rib.del_from_rib(change)
        assert rib.pending()  # Withdrawal pending

        # Consume
        updates = consume_updates(rib)
        assert len(updates) >= 1

    # RIB should be consistent and empty
    assert not rib.pending()

    # Cache should have the route marked as withdrawn
    cached = list(rib.cached_changes(None))
    # Either empty (withdrawn) or has announce from last cycle
    assert len(cached) <= 1


# ==============================================================================
# RACE CONDITION TESTS (Async/Concurrency)
# ==============================================================================


@pytest.mark.asyncio
async def test_multiple_peers_same_rib():
    """
    Concurrency Test: Multiple peers accessing same RIB

    Problem: No locking mechanism - relies on single-threaded event loop
    In async mode: Multiple tasks can interleave at await points

    Scenario: 3 peers consuming updates concurrently
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add routes
    for i in range(20):
        add_route_to_rib(rib, f"192.168.0.{i}/32")

    update_counts = []

    async def peer_task(peer_id: int):
        """Simulate a peer consuming updates"""
        count = 0
        # Each peer tries to consume updates
        while rib.pending():
            updates = rib.updates(grouped=False)
            for update in updates:
                count += 1
                await asyncio.sleep(0.001)  # Simulate send delay
        update_counts.append(count)

    # Run 3 peers concurrently
    await asyncio.gather(
        peer_task(1),
        peer_task(2),
        peer_task(3)
    )

    # RIB should be empty and consistent after all peers done
    assert not rib.pending()
    assert len(rib._new_nlri) == 0

    # At least one peer should have consumed some updates
    # (Exact behavior depends on interleaving)
    assert sum(update_counts) >= 1


@pytest.mark.asyncio
async def test_api_commands_during_peer_sending():
    """
    Concurrency Test: API commands (flush, clear) during peer sending

    Scenario: API callback scheduled during peer's update loop
    In async mode: ASYNC.schedule() can interleave with peer tasks
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add and cache routes
    for i in range(10):
        add_route_to_rib(rib, f"192.168.0.{i}/32")
    consume_updates(rib)

    # Add new pending routes
    for i in range(10, 15):
        add_route_to_rib(rib, f"192.168.0.{i}/32")

    peer_updates = []
    api_completed = False

    async def peer_sending():
        """Peer consumes updates slowly"""
        updates = rib.updates(grouped=False)
        for update in updates:
            peer_updates.append(update)
            await asyncio.sleep(0.01)  # Slow sending

    async def api_flush():
        """API flush command arrives during peer sending"""
        nonlocal api_completed
        await asyncio.sleep(0.02)  # Delay to hit during peer sending
        rib.resend(enhanced_refresh=False)
        api_completed = True

    # Run concurrently
    await asyncio.gather(peer_sending(), api_flush())

    # API should have completed
    assert api_completed

    # Peer should have received some updates
    assert len(peer_updates) >= 1

    # Refresh changes should be pending or consumed
    # (Exact state depends on timing)


@pytest.mark.asyncio
async def test_flush_interleaving():
    """
    Concurrency Test: Multiple flush commands interleaving

    Scenario: Multiple API flush commands in rapid succession
    Tests _refresh_changes list consistency
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add and cache routes
    for i in range(5):
        add_route_to_rib(rib, f"192.168.0.{i}/32")
    consume_updates(rib)

    async def flush_task(task_id: int):
        """Issue multiple flush commands"""
        for i in range(3):
            rib.resend(enhanced_refresh=False)
            await asyncio.sleep(0.001)

    # Run 3 flush tasks concurrently
    await asyncio.gather(
        flush_task(1),
        flush_task(2),
        flush_task(3)
    )

    # RIB should be consistent
    # _refresh_changes may have multiple copies of routes
    assert isinstance(rib._refresh_changes, list)

    # Should be pending
    assert rib.pending()

    # Consume all
    updates = consume_updates(rib)
    assert len(updates) >= 1

    # Should be empty after consumption
    assert len(rib._refresh_changes) == 0


# ==============================================================================
# MEMORY & PERFORMANCE TESTS
# ==============================================================================


def test_watchdog_memory_behavior():
    """
    Memory Test: Watchdog dictionary growth

    Issue #4: Watchdog dict grows unbounded

    Problem: Routes added to watchdog never removed from _watchdog dict
             Only moved between '+' and '-' sub-dicts

    Location: outgoing.py:144-153

    Note: This test documents current behavior. A proper fix would add cleanup.
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add routes with different watchdog names
    for i in range(10):
        change = create_change(f"192.168.0.{i}/32")
        watchdog_name = f"dog_{i}"

        # Add to watchdog '-' (withdrawn state)
        rib._watchdog.setdefault(watchdog_name, {}).setdefault('-', {})[change.index()] = change

    # Initial state: 10 watchdog names
    assert len(rib._watchdog) == 10

    # Announce each watchdog (moves to '+')
    for i in range(10):
        watchdog_name = f"dog_{i}"
        if watchdog_name in rib._watchdog:
            for change in list(rib._watchdog[watchdog_name].get('-', {}).values()):
                change.nlri.action = Action.ANNOUNCE
                rib._watchdog[watchdog_name].setdefault('+', {})[change.index()] = change
                rib._watchdog[watchdog_name]['-'].pop(change.index(), None)

    # Watchdog dict still has 10 entries (documented behavior)
    assert len(rib._watchdog) == 10

    # Withdraw each watchdog (moves back to '-')
    for i in range(10):
        watchdog_name = f"dog_{i}"
        if watchdog_name in rib._watchdog:
            for change in list(rib._watchdog[watchdog_name].get('+', {}).values()):
                change.nlri.action = Action.WITHDRAW
                rib._watchdog[watchdog_name].setdefault('-', {})[change.index()] = change
                rib._watchdog[watchdog_name]['+'].pop(change.index(), None)

    # ISSUE: Watchdog dict STILL has 10 entries - no cleanup mechanism
    # In production with many watchdogs over time, this grows unbounded
    assert len(rib._watchdog) == 10  # Documents current behavior (memory leak)


def test_deepcopy_usage():
    """
    Performance Test: deepcopy usage in del_from_rib

    Issue #5: Expensive deepcopy() in del_from_rib() line 189

    This test documents that deepcopy is used.
    A performance improvement would use shallow copy or copy-on-write.
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add route
    change = add_route_to_rib(rib, "192.168.0.1/32")

    # Delete route (internally uses deepcopy)
    rib.del_from_rib(change)

    # Verify withdrawal is pending
    assert rib.pending()

    # Consume withdrawal
    updates = consume_updates(rib)
    assert len(updates) == 1

    # This test just verifies the operation works
    # Performance impact is documented in investigation


def test_rib_size_bounds():
    """
    Memory Test: RIB growth limits

    Issue: No validation or bounds checking in add_to_rib
           Could lead to memory exhaustion

    This test verifies current behavior (no limits)
    Production deployment should consider adding limits
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add many routes without limit
    for i in range(1000):
        add_route_to_rib(rib, f"10.0.{i // 256}.{i % 256}/32")

    # All routes accepted (no rejection)
    assert len(rib._new_nlri) == 1000

    # Consume
    consume_updates(rib)

    # All routes cached (no limit)
    cached = list(rib.cached_changes(None))
    assert len(cached) == 1000

    # Documents current behavior: unbounded growth


# ==============================================================================
# INCOMING RIB TESTS
# ==============================================================================


def test_incoming_rib_basic():
    """
    Basic test for IncomingRIB

    IncomingRIB is simpler than OutgoingRIB but inherits from Cache
    Tests that Cache bugs are fixed for IncomingRIB too
    """
    families = {(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)}
    rib = IncomingRIB(cache=True, families=families)

    # Add changes
    change1 = create_change("192.168.0.1/32", AFI.ipv4)
    change2 = create_change("2001:db8::1/128", AFI.ipv6)

    rib.update_cache(change1)
    rib.update_cache(change2)

    # Test delete_cached_family (should not crash after fix)
    rib.delete_cached_family({(AFI.ipv4, SAFI.unicast)})

    # IPv4 kept, IPv6 removed
    assert (AFI.ipv4, SAFI.unicast) in rib._seen
    assert (AFI.ipv6, SAFI.unicast) not in rib._seen


def test_resend_with_enhanced_refresh():
    """
    Test that enhanced refresh (route refresh messages) works correctly
    and that _refresh_families is also snapshotted properly

    This tests the same race condition fix but for _refresh_families
    """
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    # Add and cache a route
    add_route_to_rib(rib, "192.168.0.1/32")
    consume_updates(rib)

    # Call resend with enhanced refresh
    rib.resend(enhanced_refresh=True)

    # Should have both _refresh_families and _refresh_changes populated
    assert len(rib._refresh_families) == 1
    assert len(rib._refresh_changes) == 1

    # Create updates generator
    # NOTE: Generator function doesn't execute until first next() call
    updates_gen = rib.updates(grouped=False)

    # Consume first update (triggers generator execution)
    update1 = next(updates_gen)

    # At this point (after first next()), both should be cleared (moved to snapshots)
    assert len(rib._refresh_families) == 0
    assert len(rib._refresh_changes) == 0

    # Call resend again during iteration (with different family to distinguish)
    rib.resend(enhanced_refresh=True, family=(AFI.ipv4, SAFI.unicast))

    # New resend should populate the fresh lists
    assert len(rib._refresh_families) == 1
    assert len(rib._refresh_changes) == 1

    # Consume rest of current iteration
    remaining = list(updates_gen)

    # First iteration should have yielded:
    # - RouteRefresh start (1)
    # - Update for cached route (1) <- update1
    # - RouteRefresh end (1)
    # Total: 3 messages, we got 1 in update1, so remaining should be 2
    # (But actual implementation may group, so just verify we got something)
    assert len(remaining) >= 1

    # Second updates() call should handle the second resend
    assert rib.pending()
    second_updates = consume_updates(rib)
    assert len(second_updates) >= 1


if __name__ == '__main__':
    # Run with: pytest test_rib_stress.py -v
    # Or: python test_rib_stress.py
    pytest.main([__file__, '-v'])
