#!/usr/bin/env python3
"""
Tests for RIB flush callback mechanism.

Flush callbacks allow API commands to wait until routes are sent on wire.
- register_flush_callback() returns an asyncio.Event
- fire_flush_callbacks() sets all registered events and clears list

Used by sync mode API commands for synchronous route announcement.
"""

import asyncio
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

from exabgp.rib.outgoing import OutgoingRIB  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_rib() -> OutgoingRIB:
    """Create a standard test RIB."""
    return OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})


# ==============================================================================
# Test register_flush_callback
# ==============================================================================


class TestRegisterFlushCallback:
    """Tests for register_flush_callback() method."""

    def test_register_returns_asyncio_event(self):
        """register_flush_callback() returns an asyncio.Event."""
        rib = create_rib()

        event = rib.register_flush_callback()

        assert isinstance(event, asyncio.Event)

    def test_register_event_not_set_initially(self):
        """Returned event is not set initially."""
        rib = create_rib()

        event = rib.register_flush_callback()

        assert not event.is_set()

    def test_register_adds_to_callback_list(self):
        """register_flush_callback() adds event to internal list."""
        rib = create_rib()

        event = rib.register_flush_callback()

        assert event in rib._flush_callbacks

    def test_multiple_registers_all_tracked(self):
        """Multiple register calls track all events."""
        rib = create_rib()

        event1 = rib.register_flush_callback()
        event2 = rib.register_flush_callback()
        event3 = rib.register_flush_callback()

        assert len(rib._flush_callbacks) == 3
        assert event1 in rib._flush_callbacks
        assert event2 in rib._flush_callbacks
        assert event3 in rib._flush_callbacks

    def test_register_returns_unique_events(self):
        """Each register call returns a unique event."""
        rib = create_rib()

        event1 = rib.register_flush_callback()
        event2 = rib.register_flush_callback()

        assert event1 is not event2


# ==============================================================================
# Test fire_flush_callbacks
# ==============================================================================


class TestFireFlushCallbacks:
    """Tests for fire_flush_callbacks() method."""

    def test_fire_sets_single_event(self):
        """fire_flush_callbacks() sets registered event."""
        rib = create_rib()
        event = rib.register_flush_callback()

        assert not event.is_set()

        rib.fire_flush_callbacks()

        assert event.is_set()

    def test_fire_sets_all_events(self):
        """fire_flush_callbacks() sets all registered events."""
        rib = create_rib()

        events = [rib.register_flush_callback() for _ in range(5)]

        for event in events:
            assert not event.is_set()

        rib.fire_flush_callbacks()

        for event in events:
            assert event.is_set()

    def test_fire_clears_callback_list(self):
        """fire_flush_callbacks() clears the callback list."""
        rib = create_rib()

        rib.register_flush_callback()
        rib.register_flush_callback()

        assert len(rib._flush_callbacks) == 2

        rib.fire_flush_callbacks()

        assert len(rib._flush_callbacks) == 0

    def test_fire_with_no_callbacks_is_noop(self):
        """fire_flush_callbacks() with no callbacks does nothing."""
        rib = create_rib()

        # Should not raise
        rib.fire_flush_callbacks()

        assert len(rib._flush_callbacks) == 0

    def test_fire_only_affects_registered_events(self):
        """fire_flush_callbacks() only affects events in callback list."""
        rib = create_rib()

        registered_event = rib.register_flush_callback()
        unregistered_event = asyncio.Event()

        rib.fire_flush_callbacks()

        assert registered_event.is_set()
        assert not unregistered_event.is_set()


# ==============================================================================
# Test Callback Lifecycle
# ==============================================================================


class TestFlushCallbackLifecycle:
    """Tests for complete callback lifecycle."""

    def test_register_fire_register_cycle(self):
        """Can register new callbacks after firing."""
        rib = create_rib()

        # First cycle
        event1 = rib.register_flush_callback()
        rib.fire_flush_callbacks()
        assert event1.is_set()

        # Second cycle - new registration after fire
        event2 = rib.register_flush_callback()
        assert not event2.is_set()
        assert len(rib._flush_callbacks) == 1

        rib.fire_flush_callbacks()
        assert event2.is_set()

    def test_fire_does_not_affect_previously_fired_events(self):
        """Previously fired events stay set after new fire."""
        rib = create_rib()

        event1 = rib.register_flush_callback()
        rib.fire_flush_callbacks()

        event2 = rib.register_flush_callback()
        rib.fire_flush_callbacks()

        # Both should be set
        assert event1.is_set()
        assert event2.is_set()

    def test_clear_does_not_fire_callbacks(self):
        """RIB clear does not fire flush callbacks."""
        rib = create_rib()

        event = rib.register_flush_callback()

        rib.clear()

        # Event should NOT be set by clear
        assert not event.is_set()
        # Callbacks should still be registered
        assert len(rib._flush_callbacks) == 1


# ==============================================================================
# Test Async Integration
# ==============================================================================


class TestFlushCallbackAsync:
    """Async tests for flush callback mechanism."""

    @pytest.mark.asyncio
    async def test_can_await_event(self):
        """Event can be awaited asynchronously."""
        rib = create_rib()
        event = rib.register_flush_callback()

        # Fire in background
        async def fire_later():
            await asyncio.sleep(0.01)
            rib.fire_flush_callbacks()

        task = asyncio.create_task(fire_later())

        # Wait for event with timeout
        await asyncio.wait_for(event.wait(), timeout=1.0)

        assert event.is_set()
        await task

    @pytest.mark.asyncio
    async def test_multiple_waiters(self):
        """Multiple coroutines can wait on different events."""
        rib = create_rib()

        events = [rib.register_flush_callback() for _ in range(3)]
        results = []

        async def wait_and_record(idx, event):
            await event.wait()
            results.append(idx)

        # Start waiters
        tasks = [asyncio.create_task(wait_and_record(i, e)) for i, e in enumerate(events)]

        # Fire callbacks
        await asyncio.sleep(0.01)
        rib.fire_flush_callbacks()

        # Wait for all
        await asyncio.gather(*tasks)

        assert len(results) == 3
        assert set(results) == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_event_can_be_checked_without_blocking(self):
        """Event.is_set() doesn't block."""
        rib = create_rib()
        event = rib.register_flush_callback()

        # Check without blocking
        assert not event.is_set()

        rib.fire_flush_callbacks()

        assert event.is_set()


# ==============================================================================
# Test Edge Cases
# ==============================================================================


class TestFlushCallbackEdgeCases:
    """Edge case tests for flush callbacks."""

    def test_fire_twice_is_safe(self):
        """Calling fire_flush_callbacks() twice is safe."""
        rib = create_rib()

        event = rib.register_flush_callback()

        rib.fire_flush_callbacks()
        rib.fire_flush_callbacks()  # Should not raise

        assert event.is_set()
        assert len(rib._flush_callbacks) == 0

    def test_large_number_of_callbacks(self):
        """Handles large number of callbacks."""
        rib = create_rib()

        events = [rib.register_flush_callback() for _ in range(1000)]

        rib.fire_flush_callbacks()

        assert all(e.is_set() for e in events)
        assert len(rib._flush_callbacks) == 0

    def test_callback_after_rib_reset(self):
        """Callbacks survive RIB reset."""
        rib = create_rib()

        event = rib.register_flush_callback()

        rib.reset()

        # Callback should still be registered
        assert event in rib._flush_callbacks

        rib.fire_flush_callbacks()
        assert event.is_set()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
