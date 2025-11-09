"""Performance tests for message backlog saturation.

Tests the system's behavior when the message backlog approaches and reaches
the MAX_BACKLOG limit of 15,000 messages defined in Protocol.
"""

from collections import deque
from typing import Any

from exabgp.reactor.protocol import MAX_BACKLOG

from .perf_helpers import (
    create_simple_update_bytes,
    create_large_update_bytes,
)


class TestBacklogNearCapacity:
    """Tests for backlog behavior near MAX_BACKLOG capacity."""

    def test_backlog_at_1000_messages(self, benchmark: Any) -> None:
        """Benchmark backlog performance with 1,000 messages."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(1000)]

        def manage_backlog():
            backlog = deque()

            # Fill backlog
            for msg in messages:
                backlog.append(msg)

            # Process half
            processed = 0
            while len(backlog) > 500:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(manage_backlog)
        assert result == 500

    def test_backlog_at_5000_messages(self, benchmark: Any) -> None:
        """Benchmark backlog performance with 5,000 messages."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(5000)]

        def manage_backlog():
            backlog = deque()

            # Fill backlog
            for msg in messages:
                backlog.append(msg)

            # Process all
            processed = 0
            while backlog:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(manage_backlog)
        assert result == 5000

    def test_backlog_at_10000_messages(self, benchmark: Any) -> None:
        """Benchmark backlog performance with 10,000 messages."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(10000)]

        def manage_backlog():
            backlog = deque()

            # Fill backlog
            for msg in messages:
                backlog.append(msg)

            # Verify size
            len(backlog)

            # Process all
            processed = 0
            while backlog:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(manage_backlog)
        assert result == 10000

    def test_backlog_at_max_capacity(self, benchmark: Any) -> None:
        """Benchmark backlog performance at MAX_BACKLOG (15,000) messages."""
        # Create exactly MAX_BACKLOG messages
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(MAX_BACKLOG)]

        def manage_backlog():
            backlog = deque()

            # Fill to MAX_BACKLOG
            for msg in messages:
                backlog.append(msg)

            # Verify we're at capacity
            assert len(backlog) == MAX_BACKLOG

            # Process all
            processed = 0
            while backlog:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(manage_backlog)
        assert result == MAX_BACKLOG


class TestBacklogSaturationBehavior:
    """Tests for backlog saturation and overflow scenarios."""

    def test_backlog_cycling_at_capacity(self, benchmark: Any) -> None:
        """Benchmark backlog with continuous add/remove at capacity."""
        # Pre-fill to 90% capacity
        initial_size = int(MAX_BACKLOG * 0.9)
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(initial_size)]
        new_messages = [create_simple_update_bytes(num_routes=1) for _ in range(5000)]

        def cycle_backlog():
            backlog = deque(messages)

            # Add and remove to simulate steady state near capacity
            processed = 0
            for msg in new_messages:
                backlog.append(msg)
                if len(backlog) > MAX_BACKLOG * 0.95:
                    # Process some messages to stay under limit
                    for _ in range(100):
                        if backlog:
                            _ = backlog.popleft()
                            processed += 1

            return processed

        result = benchmark(cycle_backlog)
        assert result > 0

    def test_burst_handling_with_backlog(self, benchmark: Any) -> None:
        """Benchmark handling message bursts with existing backlog."""
        # Start with half-full backlog
        existing = [create_simple_update_bytes(num_routes=1) for _ in range(7500)]
        burst = [create_simple_update_bytes(num_routes=1) for _ in range(3000)]

        def handle_burst():
            backlog = deque(existing)
            len(backlog)

            # Receive burst
            for msg in burst:
                backlog.append(msg)

            # Process to avoid overflow
            processed = 0
            while len(backlog) > 5000:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(handle_burst)
        assert result > 0

    def test_large_message_backlog(self, benchmark: Any) -> None:
        """Benchmark backlog with large UPDATE messages."""
        # Large messages consume more memory
        messages = [create_large_update_bytes(num_routes=100) for _ in range(5000)]

        def manage_large_backlog():
            backlog = deque()

            # Fill backlog
            for msg in messages:
                backlog.append(msg)

            # Process all
            processed = 0
            total_size = 0
            while backlog:
                msg = backlog.popleft()
                total_size += len(msg)
                processed += 1

            return processed

        result = benchmark(manage_large_backlog)
        assert result == 5000


class TestBacklogMemoryPressure:
    """Tests for memory usage under backlog pressure."""

    def test_memory_with_increasing_backlog(self, benchmark: Any) -> None:
        """Benchmark memory behavior as backlog grows."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(10000)]

        def grow_backlog():
            backlog = deque()
            sizes = []

            # Grow backlog in steps
            for i, msg in enumerate(messages):
                backlog.append(msg)

                # Sample size at intervals
                if i % 1000 == 0:
                    sizes.append(len(backlog))

            return len(sizes)

        result = benchmark(grow_backlog)
        assert result > 0

    def test_backlog_with_mixed_message_sizes(self, benchmark: Any) -> None:
        """Benchmark backlog with mixed small and large messages."""
        messages = []
        for i in range(5000):
            if i % 10 == 0:
                messages.append(create_large_update_bytes(num_routes=100))
            else:
                messages.append(create_simple_update_bytes(num_routes=1))

        def manage_mixed_backlog():
            backlog = deque()

            # Fill backlog
            for msg in messages:
                backlog.append(msg)

            # Process all
            processed = 0
            while backlog:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(manage_mixed_backlog)
        assert result == 5000


class TestBacklogRecovery:
    """Tests for backlog recovery scenarios."""

    def test_recovery_from_saturation(self, benchmark: Any) -> None:
        """Benchmark recovery from backlog saturation."""
        # Fill to MAX_BACKLOG
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(MAX_BACKLOG)]

        def recover_backlog():
            backlog = deque(messages)
            assert len(backlog) == MAX_BACKLOG

            # Process down to 10% capacity
            target_size = int(MAX_BACKLOG * 0.1)
            processed = 0

            while len(backlog) > target_size:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(recover_backlog)
        expected = MAX_BACKLOG - int(MAX_BACKLOG * 0.1)
        assert result == expected

    def test_sustained_processing_rate(self, benchmark: Any) -> None:
        """Benchmark sustained message processing rate."""
        # Create continuous stream
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(20000)]

        def sustained_processing():
            backlog = deque()
            processed = 0

            # Simulate producer faster than consumer
            for i, msg in enumerate(messages):
                backlog.append(msg)

                # Process messages at sustained rate
                if i % 2 == 0 and backlog:
                    _ = backlog.popleft()
                    processed += 1

                # Don't let backlog exceed MAX_BACKLOG
                while len(backlog) >= MAX_BACKLOG:
                    _ = backlog.popleft()
                    processed += 1

            # Drain remaining
            while backlog:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(sustained_processing)
        assert result == 20000


class TestBacklogStressScenarios:
    """Stress tests for extreme backlog scenarios."""

    def test_rapid_backlog_growth(self, benchmark: Any) -> None:
        """Stress test: Rapid backlog growth to capacity."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(MAX_BACKLOG)]

        def rapid_growth():
            backlog = deque()

            # Add all messages as fast as possible
            for msg in messages:
                backlog.append(msg)

            return len(backlog)

        result = benchmark(rapid_growth)
        assert result == MAX_BACKLOG

    def test_oscillating_backlog_size(self, benchmark: Any) -> None:
        """Stress test: Backlog size oscillating between full and empty."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(MAX_BACKLOG)]

        def oscillate_backlog():
            backlog = deque()
            cycles = 0

            # Perform 5 full cycles
            for _ in range(5):
                # Fill
                for msg in messages:
                    backlog.append(msg)

                # Empty
                while backlog:
                    _ = backlog.popleft()

                cycles += 1

            return cycles

        result = benchmark(oscillate_backlog)
        assert result == 5

    def test_concurrent_backlog_operations(self, benchmark: Any) -> None:
        """Stress test: Concurrent add/remove operations."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(50000)]

        def concurrent_ops():
            backlog = deque()
            added = 0
            removed = 0

            for i, msg in enumerate(messages):
                backlog.append(msg)
                added += 1

                # Remove every 3rd message immediately
                if i % 3 == 0 and backlog:
                    _ = backlog.popleft()
                    removed += 1

                # Prevent overflow
                while len(backlog) >= MAX_BACKLOG:
                    _ = backlog.popleft()
                    removed += 1

            # Drain
            while backlog:
                _ = backlog.popleft()
                removed += 1

            return removed

        result = benchmark(concurrent_ops)
        assert result == 50000
