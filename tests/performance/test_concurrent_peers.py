"""Performance tests for concurrent peer handling.

Tests the system's ability to handle messages from multiple BGP peers
simultaneously under high load.
"""

from io import BytesIO
from collections import deque, defaultdict
from typing import Any


from .perf_helpers import (
    create_simple_update_bytes,
    create_batch_messages,
    create_mixed_message_batch,
)


class TestMultiplePeerProcessing:
    """Tests for processing messages from multiple peers."""

    def test_process_10_peers_100_messages_each(self, benchmark: Any) -> None:
        """Benchmark processing 100 messages from 10 peers."""
        num_peers = 10
        messages_per_peer = 100

        # Create message batches for each peer
        peer_data = {}
        for peer_id in range(num_peers):
            peer_data[peer_id] = create_batch_messages('update', count=messages_per_peer)

        def process_multi_peer():
            readers = {}
            message_counts = defaultdict(int)

            # Create readers for each peer
            for peer_id, data in peer_data.items():
                readers[peer_id] = BytesIO(data)

            # Process messages in round-robin fashion
            total = 0
            while total < num_peers * messages_per_peer:
                for peer_id, reader in readers.items():
                    marker = reader.read(16)
                    if len(marker) < 16:
                        continue

                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)

                    message_counts[peer_id] += 1
                    total += 1

                    if total >= num_peers * messages_per_peer:
                        break

            return total

        result = benchmark(process_multi_peer)
        assert result == num_peers * messages_per_peer

    def test_process_50_peers_concurrent(self, benchmark: Any) -> None:
        """Benchmark processing from 50 concurrent peers."""
        num_peers = 50
        messages_per_peer = 50

        peer_data = {}
        for peer_id in range(num_peers):
            peer_data[peer_id] = create_batch_messages('update', count=messages_per_peer)

        def process_many_peers():
            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            total = 0

            # Round-robin processing
            active_readers = set(readers.keys())
            while active_readers and total < num_peers * messages_per_peer:
                for peer_id in list(active_readers):
                    reader = readers[peer_id]
                    marker = reader.read(16)

                    if len(marker) < 16:
                        active_readers.remove(peer_id)
                        continue

                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)
                    total += 1

                    if total >= num_peers * messages_per_peer:
                        break

            return total

        result = benchmark(process_many_peers)
        assert result == num_peers * messages_per_peer

    def test_process_100_peers_mixed_messages(self, benchmark: Any) -> None:
        """Benchmark processing mixed messages from 100 peers."""
        num_peers = 100
        messages_per_peer = 20

        peer_data = {}
        for peer_id in range(num_peers):
            peer_data[peer_id] = create_mixed_message_batch(
                update_count=10,
                keepalive_count=7,
                notification_count=3,
            )

        def process_mixed_peers():
            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            total = 0

            active_readers = set(readers.keys())
            while active_readers and total < num_peers * messages_per_peer:
                for peer_id in list(active_readers):
                    reader = readers[peer_id]
                    marker = reader.read(16)

                    if len(marker) < 16:
                        active_readers.remove(peer_id)
                        continue

                    length_bytes = reader.read(2)
                    if len(length_bytes) < 2:
                        active_readers.remove(peer_id)
                        continue

                    length = int.from_bytes(length_bytes, 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)
                    total += 1

                    if total >= num_peers * messages_per_peer:
                        break

            return total

        result = benchmark(process_mixed_peers)
        assert result == num_peers * messages_per_peer


class TestPeerBacklogManagement:
    """Tests for managing backlogs across multiple peers."""

    def test_per_peer_backlog_10_peers(self, benchmark: Any) -> None:
        """Benchmark per-peer backlog management for 10 peers."""
        num_peers = 10
        messages_per_peer = 500

        def manage_peer_backlogs():
            # Create backlog for each peer
            backlogs = {peer_id: deque() for peer_id in range(num_peers)}

            # Fill backlogs
            for peer_id in range(num_peers):
                for _ in range(messages_per_peer):
                    msg = create_simple_update_bytes(num_routes=1)
                    backlogs[peer_id].append(msg)

            # Process messages from each peer
            total_processed = 0
            for peer_id in range(num_peers):
                while backlogs[peer_id]:
                    _ = backlogs[peer_id].popleft()
                    total_processed += 1

            return total_processed

        result = benchmark(manage_peer_backlogs)
        assert result == num_peers * messages_per_peer

    def test_shared_backlog_multiple_peers(self, benchmark: Any) -> None:
        """Benchmark shared backlog with messages from multiple peers."""
        num_peers = 20
        messages_per_peer = 250

        def manage_shared_backlog():
            # Single shared backlog
            backlog = deque()

            # Add messages from all peers
            for peer_id in range(num_peers):
                for _ in range(messages_per_peer):
                    msg = (peer_id, create_simple_update_bytes(num_routes=1))
                    backlog.append(msg)

            # Process all messages
            processed = 0
            while backlog:
                _ = backlog.popleft()
                processed += 1

            return processed

        result = benchmark(manage_shared_backlog)
        assert result == num_peers * messages_per_peer

    def test_priority_based_peer_processing(self, benchmark: Any) -> None:
        """Benchmark priority-based processing across peers."""
        num_peers = 15
        messages_per_peer = 200

        def priority_processing():
            # Create backlogs with priorities
            peer_backlogs = {}
            peer_priorities = {}

            for peer_id in range(num_peers):
                peer_backlogs[peer_id] = deque()
                peer_priorities[peer_id] = peer_id % 3  # 3 priority levels

                for _ in range(messages_per_peer):
                    peer_backlogs[peer_id].append(create_simple_update_bytes())

            # Process higher priority peers first
            processed = 0
            for priority in range(3):
                for peer_id in range(num_peers):
                    if peer_priorities[peer_id] == priority:
                        while peer_backlogs[peer_id]:
                            _ = peer_backlogs[peer_id].popleft()
                            processed += 1

            return processed

        result = benchmark(priority_processing)
        assert result == num_peers * messages_per_peer


class TestPeerLoadBalancing:
    """Tests for load balancing across multiple peers."""

    def test_fair_scheduling_10_peers(self, benchmark: Any) -> None:
        """Benchmark fair scheduling across 10 peers."""
        num_peers = 10
        messages_per_peer = 300

        peer_data = {
            peer_id: create_batch_messages('update', count=messages_per_peer)
            for peer_id in range(num_peers)
        }

        def fair_schedule():
            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            processed_per_peer = defaultdict(int)
            total = 0

            # Process one message per peer per round
            max_rounds = messages_per_peer
            for _ in range(max_rounds):
                for peer_id in range(num_peers):
                    reader = readers[peer_id]
                    marker = reader.read(16)

                    if len(marker) < 16:
                        continue

                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)

                    processed_per_peer[peer_id] += 1
                    total += 1

            return total

        result = benchmark(fair_schedule)
        assert result == num_peers * messages_per_peer

    def test_weighted_scheduling_peers(self, benchmark: Any) -> None:
        """Benchmark weighted scheduling (some peers get more CPU time)."""
        num_peers = 10
        base_messages = 100

        # Create peers with different message counts
        peer_data = {}
        peer_weights = {}
        total_expected = 0

        for peer_id in range(num_peers):
            weight = (peer_id % 3) + 1  # Weights: 1, 2, 3
            peer_weights[peer_id] = weight
            count = base_messages * weight
            peer_data[peer_id] = create_batch_messages('update', count=count)
            total_expected += count

        def weighted_schedule():
            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            total = 0

            # Process based on weights
            active = set(readers.keys())
            while active:
                for peer_id in list(active):
                    reader = readers[peer_id]
                    weight = peer_weights[peer_id]

                    # Process 'weight' number of messages
                    for _ in range(weight):
                        marker = reader.read(16)
                        if len(marker) < 16:
                            active.discard(peer_id)
                            break

                        length = int.from_bytes(reader.read(2), 'big')
                        msg_type = int.from_bytes(reader.read(1), 'big')
                        body = reader.read(length - 19)
                        total += 1

            return total

        result = benchmark(weighted_schedule)
        assert result == total_expected


class TestHighPeerCountStress:
    """Stress tests for very high peer counts."""

    def test_process_500_peers(self, benchmark: Any) -> None:
        """Stress test: Process messages from 500 concurrent peers."""
        num_peers = 500
        messages_per_peer = 10

        peer_data = {
            peer_id: create_batch_messages('update', count=messages_per_peer)
            for peer_id in range(num_peers)
        }

        def process_many():
            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            total = 0
            active = set(readers.keys())

            while active:
                for peer_id in list(active):
                    reader = readers[peer_id]
                    marker = reader.read(16)

                    if len(marker) < 16:
                        active.remove(peer_id)
                        continue

                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)
                    total += 1

            return total

        result = benchmark(process_many)
        assert result == num_peers * messages_per_peer

    def test_1000_peers_light_load(self, benchmark: Any) -> None:
        """Stress test: 1000 peers with light message load."""
        num_peers = 1000
        messages_per_peer = 5

        peer_data = {
            peer_id: create_batch_messages('keepalive', count=messages_per_peer)
            for peer_id in range(num_peers)
        }

        def process_light_load():
            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            total = 0

            for peer_id in range(num_peers):
                reader = readers[peer_id]
                for _ in range(messages_per_peer):
                    marker = reader.read(16)
                    if len(marker) < 16:
                        break
                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    total += 1

            return total

        result = benchmark(process_light_load)
        assert result == num_peers * messages_per_peer

    def test_variable_load_across_peers(self, benchmark: Any) -> None:
        """Stress test: Variable load across many peers."""
        num_peers = 200
        peer_data = {}
        total_expected = 0

        # Each peer gets variable number of messages
        for peer_id in range(num_peers):
            count = (peer_id % 50) + 10  # 10-59 messages
            peer_data[peer_id] = create_batch_messages('update', count=count)
            total_expected += count

        def process_variable():
            readers = {peer_id: BytesIO(data) for peer_id, data in peer_data.items()}
            total = 0
            active = set(readers.keys())

            while active:
                for peer_id in list(active):
                    reader = readers[peer_id]
                    marker = reader.read(16)

                    if len(marker) < 16:
                        active.remove(peer_id)
                        continue

                    length = int.from_bytes(reader.read(2), 'big')
                    msg_type = int.from_bytes(reader.read(1), 'big')
                    body = reader.read(length - 19)
                    total += 1

            return total

        result = benchmark(process_variable)
        assert result == total_expected
