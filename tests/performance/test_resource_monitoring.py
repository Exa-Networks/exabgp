"""Performance tests with memory and resource monitoring.

Tests that monitor system resource usage (memory, CPU) under high load
to identify potential resource leaks or inefficiencies.
"""

import pytest
import psutil
import os
from io import BytesIO
from collections import deque
from unittest.mock import Mock

from exabgp.reactor.protocol import Protocol, MAX_BACKLOG
from exabgp.reactor.network.connection import Connection
from exabgp.bgp.message import Update
from exabgp.bgp.message.direction import Direction

from .perf_helpers import (
    create_simple_update_bytes,
    create_batch_messages,
    create_large_update_bytes,
    create_mixed_message_batch,
    create_mock_logger,
    create_mock_negotiated,
)


class TestMemoryUsage:
    """Tests for memory usage under various load scenarios."""

    def test_memory_baseline_message_parsing(self, benchmark):
        """Measure baseline memory usage for message parsing."""
        msg_bytes = create_simple_update_bytes(num_routes=1)
        negotiated = create_mock_negotiated()

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        def parse_with_memory_tracking():
            # Parse 1000 messages
            for _ in range(1000):
                reader = BytesIO(msg_bytes)
                marker = reader.read(16)
                length = int.from_bytes(reader.read(2), 'big')
                msg_type = int.from_bytes(reader.read(1), 'big')
                body = reader.read(length - 19)
                msg = Update.unpack_message(body, Direction.IN, negotiated)

            # Get memory after parsing
            final_memory = process.memory_info().rss / 1024 / 1024
            memory_delta = final_memory - initial_memory

            return memory_delta

        # Note: This returns memory delta, actual benchmark is on the function
        result = benchmark(parse_with_memory_tracking)

    def test_memory_growth_with_backlog(self, benchmark):
        """Monitor memory growth as backlog increases."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(10000)]
        process = psutil.Process(os.getpid())

        def track_memory_growth():
            backlog = deque()
            memory_samples = []

            initial_memory = process.memory_info().rss / 1024 / 1024

            # Add messages and sample memory
            for i, msg in enumerate(messages):
                backlog.append(msg)

                # Sample every 1000 messages
                if i % 1000 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_samples.append(current_memory - initial_memory)

            # Clear backlog
            backlog.clear()

            return len(memory_samples)

        result = benchmark(track_memory_growth)
        assert result > 0

    def test_memory_large_message_handling(self, benchmark):
        """Monitor memory when handling large messages."""
        messages = [create_large_update_bytes(num_routes=200) for _ in range(1000)]
        process = psutil.Process(os.getpid())

        def handle_large_messages():
            backlog = deque()
            initial_memory = process.memory_info().rss / 1024 / 1024

            # Fill backlog
            for msg in messages:
                backlog.append(msg)

            peak_memory = process.memory_info().rss / 1024 / 1024

            # Process all
            while backlog:
                _ = backlog.popleft()

            final_memory = process.memory_info().rss / 1024 / 1024

            return {
                'peak_delta': peak_memory - initial_memory,
                'final_delta': final_memory - initial_memory,
            }

        result = benchmark(handle_large_messages)

    def test_memory_recovery_after_load(self, benchmark):
        """Test memory recovery after processing high load."""
        process = psutil.Process(os.getpid())

        def load_and_recover():
            initial_memory = process.memory_info().rss / 1024 / 1024

            # Create and process high load
            for _ in range(5):
                messages = [create_simple_update_bytes() for _ in range(2000)]
                backlog = deque(messages)

                while backlog:
                    _ = backlog.popleft()

                # Clear references
                messages = None
                backlog = None

            final_memory = process.memory_info().rss / 1024 / 1024
            memory_delta = final_memory - initial_memory

            return memory_delta

        result = benchmark(load_and_recover)


class TestResourceUtilization:
    """Tests for overall resource utilization."""

    def test_cpu_usage_during_parsing(self, benchmark):
        """Monitor CPU usage during message parsing."""
        batch_bytes = create_batch_messages('update', count=5000)
        negotiated = create_mock_negotiated()
        process = psutil.Process(os.getpid())

        def parse_with_cpu_tracking():
            # Get initial CPU times
            cpu_start = process.cpu_times()

            # Parse messages
            stream = BytesIO(batch_bytes)
            count = 0

            while count < 5000:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length = int.from_bytes(stream.read(2), 'big')
                msg_type = int.from_bytes(stream.read(1), 'big')
                body = stream.read(length - 19)
                count += 1

            # Get final CPU times
            cpu_end = process.cpu_times()

            cpu_delta = cpu_end.user - cpu_start.user

            return cpu_delta

        result = benchmark(parse_with_cpu_tracking)

    def test_resource_usage_multi_peer(self, benchmark):
        """Monitor resource usage with multiple peers."""
        num_peers = 50
        messages_per_peer = 100

        peer_data = {
            peer_id: create_batch_messages('update', count=messages_per_peer)
            for peer_id in range(num_peers)
        }

        process = psutil.Process(os.getpid())

        def multi_peer_resources():
            initial_memory = process.memory_info().rss / 1024 / 1024

            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            total = 0

            # Process all messages
            for peer_id in range(num_peers):
                reader = readers[peer_id]
                for _ in range(messages_per_peer):
                    marker = reader.read(16)
                    if len(marker) < 16:
                        break
                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)
                    total += 1

            final_memory = process.memory_info().rss / 1024 / 1024
            memory_delta = final_memory - initial_memory

            return {'processed': total, 'memory_delta_mb': memory_delta}

        result = benchmark(multi_peer_resources)


class TestMemoryLeakDetection:
    """Tests designed to detect potential memory leaks."""

    def test_repeated_allocation_deallocation(self, benchmark):
        """Test for leaks in repeated allocation/deallocation cycles."""
        process = psutil.Process(os.getpid())

        def cycle_allocations():
            memory_samples = []

            for cycle in range(10):
                # Record memory before cycle
                mem_before = process.memory_info().rss / 1024 / 1024

                # Allocate and deallocate
                for _ in range(1000):
                    msg = create_simple_update_bytes(num_routes=10)
                    backlog = deque([msg] * 100)
                    backlog.clear()

                # Record memory after cycle
                mem_after = process.memory_info().rss / 1024 / 1024
                memory_samples.append(mem_after - mem_before)

            # Check if memory consistently grows (potential leak)
            return memory_samples

        result = benchmark(cycle_allocations)

    def test_backlog_growth_shrink_cycles(self, benchmark):
        """Test for leaks in backlog growth/shrink cycles."""
        process = psutil.Process(os.getpid())

        def cycle_backlog():
            memory_samples = []
            backlog = deque()

            for cycle in range(10):
                mem_before = process.memory_info().rss / 1024 / 1024

                # Grow backlog
                for _ in range(5000):
                    backlog.append(create_simple_update_bytes())

                # Shrink backlog
                while backlog:
                    backlog.popleft()

                mem_after = process.memory_info().rss / 1024 / 1024
                memory_samples.append(mem_after - mem_before)

            return memory_samples

        result = benchmark(cycle_backlog)


class TestScalabilityLimits:
    """Tests to identify scalability limits."""

    def test_max_sustainable_message_rate(self, benchmark):
        """Determine maximum sustainable message processing rate."""
        process = psutil.Process(os.getpid())

        def measure_max_rate():
            # Process increasing message counts
            rates = []

            for count in [1000, 5000, 10000, 15000]:
                batch = create_batch_messages('update', count=count)
                stream = BytesIO(batch)

                import time
                start_time = time.time()

                processed = 0
                while processed < count:
                    marker = stream.read(16)
                    if len(marker) < 16:
                        break
                    length = int.from_bytes(stream.read(2), 'big')
                    msg_type = int.from_bytes(stream.read(1), 'big')
                    body = stream.read(length - 19)
                    processed += 1

                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                rates.append(rate)

            return rates

        result = benchmark(measure_max_rate)

    def test_backlog_size_limits(self, benchmark):
        """Test behavior at different backlog size limits."""
        process = psutil.Process(os.getpid())

        def test_limits():
            results = {}

            # Test at different backlog sizes
            for size in [1000, 5000, 10000, MAX_BACKLOG]:
                mem_before = process.memory_info().rss / 1024 / 1024

                backlog = deque()
                for _ in range(size):
                    backlog.append(create_simple_update_bytes())

                mem_after = process.memory_info().rss / 1024 / 1024

                # Clear
                backlog.clear()

                results[size] = mem_after - mem_before

            return results

        result = benchmark(test_limits)


class TestStressWithMonitoring:
    """Stress tests with comprehensive resource monitoring."""

    def test_extreme_load_monitoring(self, benchmark):
        """Stress test with full resource monitoring."""
        process = psutil.Process(os.getpid())

        def extreme_load():
            metrics = {
                'memory_initial': process.memory_info().rss / 1024 / 1024,
                'cpu_initial': process.cpu_times().user,
            }

            # Create extreme load
            backlog = deque()

            # Add 20,000 messages
            for i in range(20000):
                if i % 2 == 0:
                    msg = create_large_update_bytes(num_routes=100)
                else:
                    msg = create_simple_update_bytes(num_routes=1)
                backlog.append(msg)

                # Process some to avoid memory exhaustion
                if len(backlog) > 10000:
                    for _ in range(5000):
                        if backlog:
                            backlog.popleft()

            # Process remaining
            processed = 0
            while backlog:
                backlog.popleft()
                processed += 1

            metrics['memory_final'] = process.memory_info().rss / 1024 / 1024
            metrics['cpu_final'] = process.cpu_times().user
            metrics['memory_delta'] = metrics['memory_final'] - metrics['memory_initial']
            metrics['cpu_delta'] = metrics['cpu_final'] - metrics['cpu_initial']
            metrics['processed'] = processed

            return metrics

        result = benchmark(extreme_load)

    def test_sustained_high_throughput(self, benchmark):
        """Test sustained high throughput with monitoring."""
        process = psutil.Process(os.getpid())

        def sustained_throughput():
            import time

            metrics = []

            # Sustain high throughput for multiple rounds
            for round_num in range(5):
                mem_before = process.memory_info().rss / 1024 / 1024
                start_time = time.time()

                # Process 5000 messages per round
                batch = create_batch_messages('update', count=5000)
                stream = BytesIO(batch)

                count = 0
                while count < 5000:
                    marker = stream.read(16)
                    if len(marker) < 16:
                        break
                    length = int.from_bytes(stream.read(2), 'big')
                    msg_type = int.from_bytes(stream.read(1), 'big')
                    body = stream.read(length - 19)
                    count += 1

                elapsed = time.time() - start_time
                mem_after = process.memory_info().rss / 1024 / 1024

                metrics.append({
                    'round': round_num,
                    'messages': count,
                    'time': elapsed,
                    'rate': count / elapsed if elapsed > 0 else 0,
                    'memory_delta': mem_after - mem_before,
                })

            return metrics

        result = benchmark(sustained_throughput)
