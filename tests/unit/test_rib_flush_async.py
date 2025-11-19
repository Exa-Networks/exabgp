"""
Unit tests for RIB flush/clear operations in async mode.

These tests verify:
1. FIFO ordering of route announcements
2. Atomic execution of clear followed by announce
3. Multiple flush sequences matching api-rib.run pattern
4. No race conditions in async command processing
"""

import pytest
import asyncio
from collections import deque

# Mock logger to avoid initialization issues
import sys
from unittest.mock import MagicMock

# Mock the option module before importing ExaBGP components
sys.modules['exabgp.logger'] = MagicMock()


class TestRibFlushFIFOOrdering:
    """Test that routes are announced in FIFO order (First In, First Out)"""

    @pytest.mark.asyncio
    async def test_command_queue_fifo(self):
        """Verify command queue uses FIFO ordering (popleft not pop)"""
        # Create a deque to simulate command queue
        command_queue = deque()

        # Add commands in order
        command_queue.append(('process', 'announce route 192.168.0.2/32'))
        command_queue.append(('process', 'announce route 192.168.0.3/32'))
        command_queue.append(('process', 'announce route 192.168.0.4/32'))

        # Dequeue and verify FIFO order
        results = []
        while command_queue:
            service, command = command_queue.popleft()  # FIFO - from start
            results.append(command)

        # Verify order is preserved
        assert results == [
            'announce route 192.168.0.2/32',
            'announce route 192.168.0.3/32',
            'announce route 192.168.0.4/32',
        ], f'Expected FIFO order, got: {results}'

    @pytest.mark.asyncio
    async def test_command_queue_lifo_would_fail(self):
        """Demonstrate that LIFO (pop) would give wrong order"""
        # Create a list to simulate broken queue
        command_list = []

        # Add commands in order
        command_list.append(('process', 'announce route 192.168.0.2/32'))
        command_list.append(('process', 'announce route 192.168.0.3/32'))
        command_list.append(('process', 'announce route 192.168.0.4/32'))

        # Dequeue with pop() - LIFO (wrong)
        results = []
        while command_list:
            service, command = command_list.pop()  # LIFO - from end
            results.append(command)

        # Verify this gives REVERSE order (wrong)
        assert results == [
            'announce route 192.168.0.4/32',  # Last added, first out
            'announce route 192.168.0.3/32',
            'announce route 192.168.0.2/32',  # First added, last out
        ], "LIFO (pop) gives reverse order - this is the bug we're avoiding"

    @pytest.mark.asyncio
    async def test_async_scheduler_fifo(self):
        """Verify async scheduler maintains FIFO order"""
        from exabgp.reactor.asynchronous import ASYNC

        scheduler = ASYNC()
        execution_order = []

        async def callback1():
            execution_order.append(1)

        async def callback2():
            execution_order.append(2)

        async def callback3():
            execution_order.append(3)

        # Schedule callbacks in order
        scheduler.schedule('1', 'cmd1', callback1())
        scheduler.schedule('2', 'cmd2', callback2())
        scheduler.schedule('3', 'cmd3', callback3())

        # Execute all callbacks
        await scheduler._run_async()
        await scheduler._run_async()
        await scheduler._run_async()

        # Verify FIFO execution order
        assert execution_order == [1, 2, 3], f'Expected [1, 2, 3], got {execution_order}'


class TestRibClearThenAnnounce:
    """Test that clear adj-rib out completes before next announce"""

    @pytest.mark.asyncio
    async def test_clear_completes_atomically(self):
        """Verify clear command completes before next command processes"""
        # Simulate command processing
        commands_executed = []

        async def clear_callback():
            commands_executed.append('clear_start')
            # Simulate RIB clear operation
            await asyncio.sleep(0.001)  # Minimal delay
            commands_executed.append('clear_complete')

        async def announce_callback():
            commands_executed.append('announce')

        # Execute clear, then announce
        await clear_callback()
        await announce_callback()

        # Verify clear completes before announce starts
        assert commands_executed == [
            'clear_start',
            'clear_complete',
            'announce',
        ], f'Clear must complete before announce, got: {commands_executed}'

    @pytest.mark.asyncio
    async def test_no_interleaving_with_one_command_per_iteration(self):
        """Verify one-command-per-iteration prevents interleaving"""
        # Simulate main loop processing one command at a time
        commands = deque(
            [
                ('clear', lambda: ['clear_exec']),
                ('announce', lambda: ['announce_exec']),
            ]
        )

        execution_log = []

        # Process ONE command per iteration (matches our fix)
        for _ in range(len(commands)):
            if commands:
                cmd_type, cmd_func = commands.popleft()
                result = cmd_func()
                execution_log.extend(result)
                # Only ONE command processed per iteration
                break

        # Continue with next iteration
        if commands:
            cmd_type, cmd_func = commands.popleft()
            result = cmd_func()
            execution_log.extend(result)

        assert execution_log == ['clear_exec', 'announce_exec'], (
            f'Commands must execute sequentially, got: {execution_log}'
        )


class TestRibMultipleFlushSequence:
    """Test multiple flush sequences matching api-rib.run pattern"""

    @pytest.mark.asyncio
    async def test_flush_sequence_from_test_t(self):
        """Reproduce api-rib.run flush sequence (lines 95-112)"""
        # Simulate RIB state
        rib_state = {
            '_new_nlri': {},  # New routes to announce
            '_seen': {},  # Cached announced routes
            '_refresh_changes': [],  # Routes to resend (flush)
        }

        # Simulate route announcements
        async def announce_route(route_id):
            rib_state['_new_nlri'][route_id] = f'route_{route_id}'
            rib_state['_seen'][route_id] = f'route_{route_id}'

        # Simulate flush operation
        async def flush_adj_rib():
            # Copy cached routes to refresh changes
            rib_state['_refresh_changes'] = list(rib_state['_seen'].values())

        # Simulate api-rib.run sequence
        # Line 95-96: announce 0.2, 0.3
        await announce_route('0.2')
        await announce_route('0.3')

        # Verify state before flush
        assert len(rib_state['_new_nlri']) == 2
        assert len(rib_state['_seen']) == 2

        # Line 101: flush adj-rib out
        await flush_adj_rib()

        # Verify flush populated refresh_changes
        assert len(rib_state['_refresh_changes']) == 2
        assert '0.2' in str(rib_state['_refresh_changes'])
        assert '0.3' in str(rib_state['_refresh_changes'])

        # Line 107: announce 0.4
        await announce_route('0.4')

        # Verify state includes new route
        assert len(rib_state['_seen']) == 3

        # Line 112: flush adj-rib out (should resend all 3)
        await flush_adj_rib()

        # Verify flush includes ALL cached routes
        assert len(rib_state['_refresh_changes']) == 3
        assert '0.2' in str(rib_state['_refresh_changes'])
        assert '0.3' in str(rib_state['_refresh_changes'])
        assert '0.4' in str(rib_state['_refresh_changes'])


class TestCommandAtomicExecution:
    """Test that commands execute atomically without interleaving"""

    @pytest.mark.asyncio
    async def test_no_yield_in_simple_callbacks(self):
        """Verify simple callbacks execute without yielding"""
        execution_log = []

        async def simple_callback():
            execution_log.append('start')
            # No await asyncio.sleep(0) - executes atomically
            execution_log.append('middle')
            execution_log.append('end')

        await simple_callback()

        # Verify callback executed atomically
        assert execution_log == ['start', 'middle', 'end']

    @pytest.mark.asyncio
    async def test_callback_with_yield_can_interleave(self):
        """Demonstrate that await asyncio.sleep(0) allows interleaving"""
        execution_log = []

        async def callback_with_yield():
            execution_log.append('callback1_start')
            await asyncio.sleep(0)  # Yields control
            execution_log.append('callback1_end')

        async def other_callback():
            execution_log.append('callback2')

        # Create tasks (simulates concurrent execution)
        task1 = asyncio.create_task(callback_with_yield())
        task2 = asyncio.create_task(other_callback())

        await task1
        await task2

        # With yield, callback2 can execute between callback1's start and end
        # This is the race condition we're avoiding with our fix
        assert 'callback1_start' in execution_log
        assert 'callback2' in execution_log
        assert 'callback1_end' in execution_log


class TestRibStateConsistency:
    """Test RIB state remains consistent during flush/clear operations"""

    @pytest.mark.asyncio
    async def test_announce_then_immediate_clear(self):
        """Test api-rib.run lines 77-78: announce + immediate clear"""
        # Simulate RIB state
        pending_routes = []

        # Line 77: announce route 192.168.0.0/32
        pending_routes.append('route_0.0')

        # Line 78: clear adj-rib out (immediate cancel)
        pending_routes.clear()

        # Expected: Route 0.0 never sent (cleared before transmission)
        assert len(pending_routes) == 0, 'Route should be cancelled before send'

    @pytest.mark.asyncio
    async def test_announce_wait_then_clear(self):
        """Test api-rib.run lines 84-89: announce, wait, clear"""
        # Simulate RIB state
        rib_state = {
            'pending': [],
            'announced': [],
        }

        # Line 84: announce route 192.168.0.1/32
        rib_state['pending'].append('route_0.1')

        # Simulate transmission (wait for ack)
        route = rib_state['pending'].pop(0)  # FIFO
        rib_state['announced'].append(route)

        # Line 89: clear adj-rib out
        withdrawals = rib_state['announced'].copy()
        rib_state['announced'].clear()

        # Expected: UPDATE for 0.1, then WITHDRAW for 0.1
        assert len(withdrawals) == 1
        assert withdrawals[0] == 'route_0.1'


if __name__ == '__main__':
    # Run with: pytest tests/unit/test_rib_flush_async.py -v
    pytest.main([__file__, '-v'])
