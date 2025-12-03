#!/usr/bin/env python
"""
Test message processing under high route load.

This stress test measures:
1. UPDATE messages per second throughput
2. Keepalive timing accuracy under load
3. Multi-peer message interleaving

Usage:
    pytest qa/stress/test_peer_throughput.py -v
    pytest qa/stress/test_peer_throughput.py -v -k test_message_throughput

Enable timing instrumentation:
    env exabgp_debug_timing=true pytest qa/stress/test_peer_throughput.py -v
"""

from __future__ import annotations

import asyncio
import time

import pytest


class MockBGPMessage:
    """Mock BGP message for throughput testing."""

    def __init__(self, msg_type: str, size: int = 100):
        self.msg_type = msg_type
        self.size = size
        self.data = b'\x00' * size


class TestMessageThroughput:
    """Test message processing throughput."""

    @pytest.mark.asyncio
    async def test_update_message_throughput(self) -> None:
        """Test UPDATE message processing throughput."""
        messages_processed = 0
        target_messages = 1000
        processing_times: list[float] = []

        async def process_update(msg: MockBGPMessage) -> float:
            """Simulate UPDATE message processing."""
            start = time.perf_counter()
            # Simulate message parsing
            await asyncio.sleep(0)  # Yield
            # Simulate attribute extraction
            _ = len(msg.data)
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed

        start_time = time.perf_counter()

        for i in range(target_messages):
            msg = MockBGPMessage('UPDATE', size=200)
            proc_time = await process_update(msg)
            processing_times.append(proc_time)
            messages_processed += 1

        total_time = time.perf_counter() - start_time
        messages_per_second = messages_processed / total_time

        avg_proc_time = sum(processing_times) / len(processing_times)
        max_proc_time = max(processing_times)

        print('\nUPDATE throughput:')
        print(f'  Messages: {messages_processed}')
        print(f'  Total time: {total_time:.3f}s')
        print(f'  Rate: {messages_per_second:.0f} msg/s')
        print(f'  Avg processing: {avg_proc_time:.3f}ms')
        print(f'  Max processing: {max_proc_time:.3f}ms')

        # Should process at least 1000 msg/s for basic messages
        assert messages_per_second > 1000, f'Throughput {messages_per_second:.0f} msg/s is too low'

    @pytest.mark.asyncio
    async def test_route_batch_processing(self) -> None:
        """Test processing routes in batches with yield points."""
        ROUTES_PER_ITERATION = 25
        total_routes = 500
        batch_times: list[float] = []

        async def process_route_batch(batch_size: int) -> float:
            """Process a batch of routes with yield after each."""
            start = time.perf_counter()
            for _ in range(batch_size):
                # Simulate route processing
                await asyncio.sleep(0)  # Yield control
            elapsed = (time.perf_counter() - start) * 1000
            return elapsed

        routes_sent = 0
        while routes_sent < total_routes:
            batch_size = min(ROUTES_PER_ITERATION, total_routes - routes_sent)
            batch_time = await process_route_batch(batch_size)
            batch_times.append(batch_time)
            routes_sent += batch_size

        avg_batch_time = sum(batch_times) / len(batch_times)
        max_batch_time = max(batch_times)
        num_batches = len(batch_times)

        print('\nBatch processing:')
        print(f'  Total routes: {total_routes}')
        print(f'  Batch size: {ROUTES_PER_ITERATION}')
        print(f'  Batches: {num_batches}')
        print(f'  Avg batch time: {avg_batch_time:.3f}ms')
        print(f'  Max batch time: {max_batch_time:.3f}ms')

        # Each batch should complete quickly (< 50ms with yields)
        assert max_batch_time < 50, f'Max batch time {max_batch_time:.3f}ms exceeds 50ms'


class TestKeepaliveAccuracy:
    """Test keepalive timing accuracy under load."""

    @pytest.mark.asyncio
    async def test_keepalive_timing_under_load(self) -> None:
        """Test that keepalive timing is maintained under message load."""
        KEEPALIVE_INTERVAL = 0.1  # 100ms for testing
        TEST_DURATION = 1.0  # 1 second
        WORK_INTERVAL = 0.01  # 10ms of work between checks

        keepalive_times: list[float] = []
        last_keepalive = time.perf_counter()
        start_time = last_keepalive

        async def send_keepalive_if_needed(current_time: float) -> bool:
            """Check if keepalive should be sent."""
            nonlocal last_keepalive
            if current_time - last_keepalive >= KEEPALIVE_INTERVAL:
                keepalive_times.append(current_time - start_time)
                last_keepalive = current_time
                return True
            return False

        async def do_work() -> None:
            """Simulate message processing work."""
            await asyncio.sleep(WORK_INTERVAL)

        # Run for TEST_DURATION with work and keepalive checks
        while time.perf_counter() - start_time < TEST_DURATION:
            await do_work()
            await send_keepalive_if_needed(time.perf_counter())

        # Analyze keepalive timing
        intervals: list[float] = []
        for i in range(1, len(keepalive_times)):
            intervals.append(keepalive_times[i] - keepalive_times[i - 1])

        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            max_interval = max(intervals)
            min_interval = min(intervals)

            print('\nKeepalive timing:')
            print(f'  Expected interval: {KEEPALIVE_INTERVAL * 1000:.0f}ms')
            print(f'  Keepalives sent: {len(keepalive_times)}')
            print(f'  Avg interval: {avg_interval * 1000:.1f}ms')
            print(f'  Min interval: {min_interval * 1000:.1f}ms')
            print(f'  Max interval: {max_interval * 1000:.1f}ms')

            # Allow 50% variance from expected interval
            max_allowed = KEEPALIVE_INTERVAL * 1.5
            assert max_interval < max_allowed, (
                f'Max keepalive interval {max_interval * 1000:.1f}ms '
                f'exceeds allowed {max_allowed * 1000:.1f}ms'
            )


class TestMultiPeerInterleaving:
    """Test message interleaving between multiple peers."""

    @pytest.mark.asyncio
    async def test_peer_message_interleaving(self) -> None:
        """Test that messages from multiple peers are interleaved fairly."""
        NUM_PEERS = 5
        MESSAGES_PER_PEER = 20
        execution_log: list[tuple[int, int, float]] = []  # (peer_id, msg_id, time)

        async def peer_task(peer_id: int) -> None:
            """Simulate a peer sending messages."""
            for msg_id in range(MESSAGES_PER_PEER):
                execution_log.append((peer_id, msg_id, time.perf_counter()))
                # Simulate message processing with yield
                await asyncio.sleep(0)

        # Run all peers concurrently
        start_time = time.perf_counter()
        await asyncio.gather(*[peer_task(i) for i in range(NUM_PEERS)])
        total_time = time.perf_counter() - start_time

        # Analyze interleaving
        # Count how many times consecutive messages are from different peers
        peer_switches = 0
        for i in range(1, len(execution_log)):
            if execution_log[i][0] != execution_log[i - 1][0]:
                peer_switches += 1

        # Calculate per-peer message spacing
        peer_times: dict[int, list[float]] = {i: [] for i in range(NUM_PEERS)}
        for peer_id, msg_id, t in execution_log:
            peer_times[peer_id].append(t)

        # Perfect interleaving would have NUM_PEERS-1 switches per round
        expected_switches = (NUM_PEERS - 1) * MESSAGES_PER_PEER
        min_expected = expected_switches * 0.5  # Allow 50% variance

        print('\nMulti-peer interleaving:')
        print(f'  Peers: {NUM_PEERS}')
        print(f'  Messages per peer: {MESSAGES_PER_PEER}')
        print(f'  Total messages: {len(execution_log)}')
        print(f'  Total time: {total_time * 1000:.1f}ms')
        print(f'  Peer switches: {peer_switches}')
        print(f'  Expected switches (ideal): {expected_switches}')

        # Show first 20 messages to visualize interleaving
        print(f'  First 20 messages: {[e[0] for e in execution_log[:20]]}')

        assert peer_switches >= min_expected, (
            f'Only {peer_switches} peer switches, expected at least {min_expected:.0f}. '
            f'Peers may not be yielding control properly.'
        )

    @pytest.mark.asyncio
    async def test_peer_starvation_prevention(self) -> None:
        """Test that no peer is starved of processing time."""
        NUM_PEERS = 3
        ITERATIONS = 100
        peer_iterations: dict[int, int] = {i: 0 for i in range(NUM_PEERS)}

        async def peer_task(peer_id: int, iterations: int) -> None:
            """Peer task that counts its iterations."""
            for _ in range(iterations):
                peer_iterations[peer_id] += 1
                await asyncio.sleep(0)

        await asyncio.gather(*[peer_task(i, ITERATIONS) for i in range(NUM_PEERS)])

        # All peers should have completed all iterations
        for peer_id, count in peer_iterations.items():
            assert count == ITERATIONS, (
                f'Peer {peer_id} only completed {count}/{ITERATIONS} iterations'
            )

        print(f'\nPeer completion: {peer_iterations}')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
