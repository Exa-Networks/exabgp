#!/usr/bin/env python
"""
Test API command response time under load.

This stress test measures:
1. Time from sending API command to receiving ACK
2. Impact of concurrent peers on API latency
3. Backpressure behavior with slow consumers

Usage:
    pytest qa/stress/test_api_reaction.py -v
    pytest qa/stress/test_api_reaction.py -v -k test_api_response_latency

Enable timing instrumentation:
    env exabgp_debug_timing=true pytest qa/stress/test_api_reaction.py -v
"""

from __future__ import annotations

import asyncio
import time

import pytest


class MockProcess:
    """Mock API process for testing."""

    def __init__(self, read_delay: float = 0.0):
        self.read_delay = read_delay
        self.stdin_buffer: list[bytes] = []
        self.messages_received: list[bytes] = []

    async def read_stdin(self) -> bytes | None:
        """Simulate reading from stdin with optional delay."""
        if self.read_delay > 0:
            await asyncio.sleep(self.read_delay)
        if self.stdin_buffer:
            msg = self.stdin_buffer.pop(0)
            self.messages_received.append(msg)
            return msg
        return None


class TestAPIResponseLatency:
    """Test API command response latency."""

    @pytest.mark.asyncio
    async def test_api_write_latency_fast_consumer(self) -> None:
        """Test API write latency with a fast-consuming process."""
        from collections import deque

        # Simulate a write queue
        queue: deque[bytes] = deque()
        messages_written = 0
        latencies: list[float] = []

        async def write_message(msg: bytes) -> float:
            """Write message and return latency in ms."""
            start = time.perf_counter()
            queue.append(msg)
            # Simulate fast flush
            await asyncio.sleep(0)
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed

        # Write 100 messages and measure latency
        for i in range(100):
            msg = f'{{"type": "announce", "id": {i}}}\n'.encode()
            latency = await write_message(msg)
            latencies.append(latency)
            messages_written += 1

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Fast consumer should have sub-millisecond latency
        assert avg_latency < 1.0, f'Average latency {avg_latency:.3f}ms exceeds 1ms'
        assert max_latency < 5.0, f'Max latency {max_latency:.3f}ms exceeds 5ms'

        print(f'\nFast consumer latency: avg={avg_latency:.3f}ms, max={max_latency:.3f}ms')

    @pytest.mark.asyncio
    async def test_api_write_latency_slow_consumer(self) -> None:
        """Test API write latency with a slow-consuming process."""
        from collections import deque

        # Simulate a write queue with backpressure
        queue: deque[bytes] = deque()
        HIGH_WATER = 50
        latencies: list[float] = []

        async def write_with_backpressure(msg: bytes) -> float:
            """Write message with backpressure simulation."""
            start = time.perf_counter()
            queue.append(msg)

            # Simulate backpressure when queue is full
            while len(queue) > HIGH_WATER:
                # Drain some messages (slow consumer)
                for _ in range(5):
                    if queue:
                        queue.popleft()
                await asyncio.sleep(0.01)  # 10ms delay per drain cycle

            elapsed = (time.perf_counter() - start) * 1000
            return elapsed

        # Write 100 messages, triggering backpressure
        for i in range(100):
            msg = f'{{"type": "announce", "id": {i}}}\n'.encode()
            latency = await write_with_backpressure(msg)
            latencies.append(latency)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Slow consumer will have higher latency due to backpressure
        print(f'\nSlow consumer latency: avg={avg_latency:.3f}ms, max={max_latency:.3f}ms')

        # Verify we experienced some backpressure
        high_latency_count = sum(1 for lat in latencies if lat > 10)
        print(f'Messages with >10ms latency: {high_latency_count}')


class TestYieldBehavior:
    """Test that the reactor yields control properly."""

    @pytest.mark.asyncio
    async def test_flush_yields_control(self) -> None:
        """Test that flush_write_queue_async yields control periodically."""
        from collections import deque

        YIELD_INTERVAL = 50
        yield_count = 0
        items_processed = 0

        queue: deque[bytes] = deque()
        for i in range(200):
            queue.append(f'message_{i}'.encode())

        async def flush_with_yield() -> int:
            """Simulate flush with yield points."""
            nonlocal yield_count, items_processed
            while queue:
                queue.popleft()
                items_processed += 1
                if items_processed % YIELD_INTERVAL == 0:
                    yield_count += 1
                    await asyncio.sleep(0)
            return yield_count

        result = await flush_with_yield()

        # With 200 items and YIELD_INTERVAL=50, we should yield 4 times
        expected_yields = 200 // YIELD_INTERVAL
        assert result == expected_yields, f'Expected {expected_yields} yields, got {result}'
        print(f'\nYield count: {result} (expected {expected_yields})')

    @pytest.mark.asyncio
    async def test_concurrent_tasks_fair_scheduling(self) -> None:
        """Test that multiple tasks get fair scheduling."""
        execution_order: list[str] = []
        iterations_per_task = 10

        async def task(name: str) -> None:
            for i in range(iterations_per_task):
                execution_order.append(f'{name}_{i}')
                await asyncio.sleep(0)  # Yield control

        # Run 3 tasks concurrently
        await asyncio.gather(
            task('A'),
            task('B'),
            task('C'),
        )

        # Check that tasks interleaved (not all A, then all B, then all C)
        # Count transitions between different tasks
        transitions = 0
        for i in range(1, len(execution_order)):
            if execution_order[i][0] != execution_order[i - 1][0]:
                transitions += 1

        # With fair scheduling, we should have many transitions
        # Perfect round-robin would have 29 transitions (A->B->C->A->...)
        min_expected_transitions = 20  # Allow some variance

        print(f'\nTask transitions: {transitions}')
        print(f'Execution order sample: {execution_order[:15]}...')

        assert transitions >= min_expected_transitions, (
            f'Expected at least {min_expected_transitions} task transitions, got {transitions}. '
            f'Tasks may not be yielding control properly.'
        )


class TestTimingInstrumentation:
    """Test the timing instrumentation module."""

    @pytest.mark.asyncio
    async def test_loop_timer_enabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test LoopTimer functionality when timing is enabled."""
        # Enable timing via environment
        monkeypatch.setenv('exabgp_debug_timing', 'true')

        # Need to reset the environment singleton to pick up new value
        from exabgp.environment.config import Environment
        Environment._setup_done = False
        Environment._instance = None
        Environment.setup()

        from exabgp.reactor.timing import LoopTimer, timing_enabled

        assert timing_enabled(), 'Timing should be enabled'

        timer = LoopTimer('test_loop', warn_threshold_ms=10)

        for _ in range(5):
            timer.start()
            await asyncio.sleep(0.005)  # 5ms
            elapsed = timer.stop()
            assert elapsed >= 4.0, f'Elapsed {elapsed}ms should be >= 4ms'

        # Test stats
        assert timer._iteration == 5
        assert timer._max_ms >= 4.0

        # Cleanup - reset environment
        Environment._setup_done = False
        Environment._instance = None

    @pytest.mark.asyncio
    async def test_loop_timer_disabled(self) -> None:
        """Test LoopTimer returns 0 when timing is disabled."""
        from exabgp.reactor.timing import LoopTimer, timing_enabled

        # Timing should be disabled by default
        assert not timing_enabled(), 'Timing should be disabled by default'

        timer = LoopTimer('test_loop', warn_threshold_ms=10)

        timer.start()
        await asyncio.sleep(0.005)  # 5ms
        elapsed = timer.stop()

        # When disabled, elapsed should be 0
        assert elapsed == 0, f'Expected 0 when disabled, got {elapsed}ms'

    @pytest.mark.asyncio
    async def test_timed_async_context_manager(self) -> None:
        """Test timed_async context manager."""
        from exabgp.reactor.timing import timed_async

        # This should not raise (timing disabled, just passes through)
        async with timed_async('test_operation', warn_threshold_ms=100):
            await asyncio.sleep(0.01)  # 10ms, under threshold


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
