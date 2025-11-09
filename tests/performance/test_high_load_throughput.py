"""
Performance tests for high message load throughput.

Tests the system's ability to handle high volumes of BGP messages
and maintain throughput under sustained load.
"""

import pytest
from io import BytesIO
from unittest.mock import Mock, MagicMock, patch
from collections import deque

from exabgp.reactor.protocol import Protocol
from exabgp.reactor.network.connection import Connection
from exabgp.bgp.message import Message

from .perf_helpers import (
    create_simple_update_bytes,
    create_keepalive_bytes,
    create_batch_messages,
    create_mixed_message_batch,
    create_large_update_bytes,
    create_mock_logger,
    create_mock_negotiated,
    create_mock_neighbor,
)


class TestMessageStreamProcessing:
    """Performance tests for processing message streams."""

    def test_parse_message_stream_100(self, benchmark):
        """Benchmark parsing 100 messages from a stream."""
        batch_bytes = create_batch_messages('update', count=100)
        from exabgp.bgp.message import Update
        from exabgp.bgp.message.direction import Direction

        def process_stream():
            stream = BytesIO(batch_bytes)
            negotiated = create_mock_negotiated()
            count = 0

            while count < 100:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length = int.from_bytes(stream.read(2), 'big')
                msg_type = int.from_bytes(stream.read(1), 'big')
                body = stream.read(length - 19)

                # Parse the message
                if msg_type == 2:  # UPDATE
                    msg = Update.unpack_message(body, Direction.IN, negotiated)

                count += 1

            return count

        result = benchmark(process_stream)
        assert result == 100

    def test_parse_mixed_stream_1000(self, benchmark):
        """Benchmark parsing 1000 mixed messages."""
        batch_bytes = create_mixed_message_batch(
            update_count=600,
            keepalive_count=300,
            notification_count=100
        )
        from exabgp.bgp.message import Update, KeepAlive
        from exabgp.bgp.message.direction import Direction

        def process_stream():
            stream = BytesIO(batch_bytes)
            negotiated = create_mock_negotiated()
            count = 0

            while count < 1000:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length_bytes = stream.read(2)
                if len(length_bytes) < 2:
                    break
                length = int.from_bytes(length_bytes, 'big')
                msg_type = int.from_bytes(stream.read(1), 'big')
                body = stream.read(length - 19)

                # Parse based on type
                if msg_type == 2:  # UPDATE
                    msg = Update.unpack_message(body, Direction.IN, negotiated)
                elif msg_type == 4:  # KEEPALIVE
                    msg = KeepAlive()

                count += 1

            return count

        result = benchmark(process_stream)
        assert result == 1000


class TestMessageQueuePerformance:
    """Performance tests for message queuing and buffering."""

    def test_queue_append_performance(self, benchmark):
        """Benchmark message queue append operations."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(1000)]

        def queue_messages():
            queue = deque()
            for msg in messages:
                queue.append(msg)
            return len(queue)

        result = benchmark(queue_messages)
        assert result == 1000

    def test_queue_append_popleft_performance(self, benchmark):
        """Benchmark queue operations under load."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(1000)]

        def queue_operations():
            queue = deque()
            processed = 0

            # Simulate producer-consumer pattern
            for i, msg in enumerate(messages):
                queue.append(msg)

                # Process every other message to build backlog
                if i % 2 == 0 and queue:
                    _ = queue.popleft()
                    processed += 1

            # Drain remaining
            while queue:
                _ = queue.popleft()
                processed += 1

            return processed

        result = benchmark(queue_operations)
        assert result == 1000

    def test_large_queue_performance(self, benchmark):
        """Benchmark operations on large message queue."""
        messages = [create_simple_update_bytes(num_routes=1) for _ in range(10000)]

        def large_queue_ops():
            queue = deque()

            # Fill queue
            for msg in messages:
                queue.append(msg)

            # Process half
            processed = 0
            for _ in range(5000):
                if queue:
                    _ = queue.popleft()
                    processed += 1

            # Add more while processing
            for i in range(5000):
                queue.append(messages[i])
                if queue:
                    _ = queue.popleft()
                    processed += 1

            return processed

        result = benchmark(large_queue_ops)
        assert result == 10000


class TestConcurrentMessageProcessing:
    """Performance tests for processing messages from multiple sources."""

    def test_interleaved_message_streams(self, benchmark):
        """Benchmark processing interleaved messages from multiple peers."""
        # Create messages from 5 different "peers"
        peer_messages = {
            f'peer{i}': create_batch_messages('update', count=200)
            for i in range(5)
        }

        def process_interleaved():
            processed = {f'peer{i}': 0 for i in range(5)}
            readers = {}

            # Create readers for each peer
            for peer_id, messages in peer_messages.items():
                readers[peer_id] = BytesIO(messages)

            # Process messages in round-robin fashion
            total = 0
            while total < 1000:
                for peer_id, reader in readers.items():
                    marker = reader.read(16)
                    if len(marker) < 16:
                        continue
                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)

                    processed[peer_id] += 1
                    total += 1

                    if total >= 1000:
                        break

            return total

        result = benchmark(process_interleaved)
        assert result == 1000

    def test_burst_message_handling(self, benchmark):
        """Benchmark handling message bursts."""
        # Simulate burst pattern: 100 messages, pause, 100 messages, etc.
        bursts = [create_batch_messages('update', count=100) for _ in range(10)]

        def process_bursts():
            total = 0

            for burst in bursts:
                reader = BytesIO(burst)
                count = 0

                while count < 100:
                    marker = reader.read(16)
                    if len(marker) < 16:
                        break
                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)
                    count += 1
                    total += 1

            return total

        result = benchmark(process_bursts)
        assert result == 1000


class TestHighLoadStress:
    """Stress tests for extreme high load scenarios."""

    def test_process_10000_messages(self, benchmark):
        """Stress test: Process 10,000 messages continuously."""
        batch_bytes = create_batch_messages('update', count=10000)

        def process_all():
            stream = BytesIO(batch_bytes)
            count = 0

            while True:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length = int.from_bytes(stream.read(2), 'big')
                msg_type = int.from_bytes(stream.read(1), 'big')
                body = stream.read(length - 19)
                count += 1

            return count

        result = benchmark(process_all)
        assert result == 10000

    def test_mixed_load_10000(self, benchmark):
        """Stress test: Process 10,000 mixed messages."""
        batch_bytes = create_mixed_message_batch(
            update_count=6000,
            keepalive_count=3000,
            notification_count=1000
        )

        def process_mixed():
            stream = BytesIO(batch_bytes)
            count = 0

            while True:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length_bytes = stream.read(2)
                if len(length_bytes) < 2:
                    break
                length = int.from_bytes(length_bytes, 'big')
                msg_type = int.from_bytes(stream.read(1), 'big')
                body = stream.read(length - 19)
                count += 1

                if count >= 10000:
                    break

            return count

        result = benchmark(process_mixed)
        assert result == 10000

    def test_large_message_throughput(self, benchmark):
        """Stress test: Process large UPDATE messages."""
        messages = [create_large_update_bytes(num_routes=200) for _ in range(1000)]
        batch_bytes = b''.join(messages)

        def process_large():
            stream = BytesIO(batch_bytes)
            count = 0
            total_bytes = 0

            while True:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length = int.from_bytes(stream.read(2), 'big')
                msg_type = int.from_bytes(stream.read(1), 'big')
                body = stream.read(length - 19)

                count += 1
                total_bytes += length

            return count

        result = benchmark(process_large)
        assert result == 1000
