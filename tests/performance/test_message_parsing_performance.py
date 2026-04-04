"""Performance tests for BGP message parsing under high load.

Tests the throughput and efficiency of parsing various BGP message types
at high message rates.
"""

from io import BytesIO
from typing import Any

from exabgp.bgp.message import Update, KeepAlive
from exabgp.bgp.message.direction import Direction

from .perf_helpers import (
    create_simple_update_bytes,
    create_keepalive_bytes,
    create_batch_messages,
    create_mixed_message_batch,
    create_mock_negotiated,
)


class TestUpdateMessageParsingPerformance:
    """Performance tests for UPDATE message parsing."""

    def test_parse_single_route_update(self, benchmark: Any) -> None:
        """Benchmark parsing a simple UPDATE with one route."""
        msg_bytes = create_simple_update_bytes(num_routes=1)
        negotiated = create_mock_negotiated()

        def parse_update():
            reader = BytesIO(msg_bytes)
            # Read header
            reader.read(16)
            length = int.from_bytes(reader.read(2), 'big')
            int.from_bytes(reader.read(1), 'big')
            # Parse body
            body = reader.read(length - 19)
            msg = Update.unpack_message(body, Direction.IN, negotiated)
            return msg

        result = benchmark(parse_update)
        assert result is not None

    def test_parse_multi_route_update(self, benchmark: Any) -> None:
        """Benchmark parsing UPDATE with 10 routes."""
        msg_bytes = create_simple_update_bytes(num_routes=10)
        negotiated = create_mock_negotiated()

        def parse_update():
            reader = BytesIO(msg_bytes)
            reader.read(16)
            length = int.from_bytes(reader.read(2), 'big')
            int.from_bytes(reader.read(1), 'big')
            body = reader.read(length - 19)
            msg = Update.unpack_message(body, Direction.IN, negotiated)
            return msg

        result = benchmark(parse_update)
        assert result is not None

    def test_parse_many_routes_update(self, benchmark: Any) -> None:
        """Benchmark parsing UPDATE with 50 routes."""
        msg_bytes = create_simple_update_bytes(num_routes=50)
        negotiated = create_mock_negotiated()

        def parse_update():
            reader = BytesIO(msg_bytes)
            reader.read(16)
            length = int.from_bytes(reader.read(2), 'big')
            int.from_bytes(reader.read(1), 'big')
            body = reader.read(length - 19)
            msg = Update.unpack_message(body, Direction.IN, negotiated)
            return msg

        result = benchmark(parse_update)
        assert result is not None

    def test_parse_100_simple_updates(self, benchmark: Any) -> None:
        """Benchmark parsing 100 simple UPDATE messages in sequence."""
        negotiated = create_mock_negotiated()

        def parse_batch():
            count = 0
            for _ in range(100):
                msg_bytes = create_simple_update_bytes(num_routes=1)
                reader = BytesIO(msg_bytes)
                reader.read(16)
                length = int.from_bytes(reader.read(2), 'big')
                int.from_bytes(reader.read(1), 'big')
                body = reader.read(length - 19)
                Update.unpack_message(body, Direction.IN, negotiated)
                count += 1
            return count

        result = benchmark(parse_batch)
        assert result == 100

    def test_parse_1000_simple_updates(self, benchmark: Any) -> None:
        """Benchmark parsing 1000 simple UPDATE messages in sequence."""
        negotiated = create_mock_negotiated()

        def parse_batch():
            count = 0
            for _ in range(1000):
                msg_bytes = create_simple_update_bytes(num_routes=1)
                reader = BytesIO(msg_bytes)
                reader.read(16)
                length = int.from_bytes(reader.read(2), 'big')
                int.from_bytes(reader.read(1), 'big')
                body = reader.read(length - 19)
                Update.unpack_message(body, Direction.IN, negotiated)
                count += 1
            return count

        result = benchmark(parse_batch)
        assert result == 1000


class TestKeepAliveParsingPerformance:
    """Performance tests for KEEPALIVE message parsing."""

    def test_parse_single_keepalive(self, benchmark: Any) -> None:
        """Benchmark parsing a single KEEPALIVE message."""
        msg_bytes = create_keepalive_bytes()
        create_mock_negotiated()

        def parse_keepalive():
            reader = BytesIO(msg_bytes)
            reader.read(16)
            int.from_bytes(reader.read(2), 'big')
            int.from_bytes(reader.read(1), 'big')
            # KEEPALIVE has no body
            msg = KeepAlive()
            return msg

        result = benchmark(parse_keepalive)
        assert result is not None

    def test_parse_1000_keepalives(self, benchmark: Any) -> None:
        """Benchmark parsing 1000 KEEPALIVE messages."""
        msg_bytes = create_keepalive_bytes()

        def parse_batch():
            count = 0
            for _ in range(1000):
                reader = BytesIO(msg_bytes)
                reader.read(16)
                int.from_bytes(reader.read(2), 'big')
                int.from_bytes(reader.read(1), 'big')
                KeepAlive()
                count += 1
            return count

        result = benchmark(parse_batch)
        assert result == 1000


class TestRawMessageReading:
    """Performance tests for raw message reading and header parsing."""

    def test_read_message_headers_100(self, benchmark: Any) -> None:
        """Benchmark reading 100 message headers."""
        batch_bytes = create_batch_messages('update', count=100)

        def read_headers():
            stream = BytesIO(batch_bytes)
            count = 0
            while count < 100:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length = int.from_bytes(stream.read(2), 'big')
                int.from_bytes(stream.read(1), 'big')
                stream.read(length - 19)
                count += 1
            return count

        result = benchmark(read_headers)
        assert result == 100

    def test_read_and_validate_headers(self, benchmark: Any) -> None:
        """Benchmark reading and validating message headers."""
        batch_bytes = create_batch_messages('update', count=100)

        def read_and_validate():
            stream = BytesIO(batch_bytes)
            count = 0
            while count < 100:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                # Validate marker
                assert marker == b'\xff' * 16
                length = int.from_bytes(stream.read(2), 'big')
                int.from_bytes(stream.read(1), 'big')
                # Validate length
                assert 19 <= length <= 4096
                stream.read(length - 19)
                count += 1
            return count

        result = benchmark(read_and_validate)
        assert result == 100


class TestHighVolumeParsingStress:
    """Stress tests for parsing very high message volumes."""

    def test_parse_10000_keepalives(self, benchmark: Any) -> None:
        """Stress test: Parse 10,000 KEEPALIVE messages."""
        msg_bytes = create_keepalive_bytes()

        def parse_batch():
            count = 0
            for _ in range(10000):
                reader = BytesIO(msg_bytes)
                reader.read(16)
                int.from_bytes(reader.read(2), 'big')
                int.from_bytes(reader.read(1), 'big')
                KeepAlive()
                count += 1
            return count

        result = benchmark(parse_batch)
        assert result == 10000

    def test_parse_5000_updates(self, benchmark: Any) -> None:
        """Stress test: Parse 5,000 UPDATE messages."""
        negotiated = create_mock_negotiated()

        def parse_batch():
            count = 0
            for _ in range(5000):
                msg_bytes = create_simple_update_bytes(num_routes=1)
                reader = BytesIO(msg_bytes)
                reader.read(16)
                length = int.from_bytes(reader.read(2), 'big')
                int.from_bytes(reader.read(1), 'big')
                body = reader.read(length - 19)
                Update.unpack_message(body, Direction.IN, negotiated)
                count += 1
            return count

        result = benchmark(parse_batch)
        assert result == 5000

    def test_read_continuous_stream(self, benchmark: Any) -> None:
        """Stress test: Read continuous stream of 1000 messages."""
        batch_bytes = create_mixed_message_batch(
            update_count=600,
            keepalive_count=300,
            notification_count=100,
        )

        def read_stream():
            stream = BytesIO(batch_bytes)
            count = 0

            while count < 1000:
                marker = stream.read(16)
                if len(marker) < 16:
                    break
                length_bytes = stream.read(2)
                if len(length_bytes) < 2:
                    break
                length = int.from_bytes(length_bytes, 'big')
                int.from_bytes(stream.read(1), 'big')
                stream.read(length - 19)
                count += 1

            return count

        result = benchmark(read_stream)
        assert result == 1000
