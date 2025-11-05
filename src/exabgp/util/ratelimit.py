"""
Rate limiting utilities for DoS protection.

Provides token bucket and sliding window rate limiters to protect
against resource exhaustion attacks.
"""

from __future__ import annotations

import time
from typing import Optional
from collections import deque


class RateLimiter:
    """Token bucket rate limiter for controlling request/message rates.

    This implements a token bucket algorithm which allows bursts while
    maintaining an average rate limit over time.
    """

    def __init__(
        self,
        max_rate: float,
        burst_size: Optional[int] = None,
        time_window: float = 1.0
    ):
        """Initialize the rate limiter.

        Args:
            max_rate: Maximum allowed rate (operations per time_window)
            burst_size: Maximum burst size (defaults to max_rate)
            time_window: Time window in seconds (default 1.0 = per second)
        """
        self.max_rate = max_rate
        self.burst_size = burst_size if burst_size is not None else int(max_rate)
        self.time_window = time_window

        # Token bucket implementation
        self.tokens = float(self.burst_size)
        self.last_update = time.time()
        self.refill_rate = max_rate / time_window

    def allow(self, cost: float = 1.0) -> bool:
        """Check if an operation should be allowed.

        Args:
            cost: Cost of the operation in tokens (default 1.0)

        Returns:
            True if operation is allowed, False if rate limit exceeded
        """
        now = time.time()
        elapsed = now - self.last_update

        # Refill tokens based on elapsed time
        self.tokens = min(
            self.burst_size,
            self.tokens + (elapsed * self.refill_rate)
        )
        self.last_update = now

        # Check if we have enough tokens
        if self.tokens >= cost:
            self.tokens -= cost
            return True

        return False

    def wait_time(self, cost: float = 1.0) -> float:
        """Calculate how long to wait before operation would be allowed.

        Args:
            cost: Cost of the operation in tokens (default 1.0)

        Returns:
            Time in seconds to wait (0.0 if operation allowed now)
        """
        if self.tokens >= cost:
            return 0.0

        needed_tokens = cost - self.tokens
        return needed_tokens / self.refill_rate

    def reset(self) -> None:
        """Reset the rate limiter to full capacity."""
        self.tokens = float(self.burst_size)
        self.last_update = time.time()


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for precise rate control.

    This provides more accurate rate limiting than token bucket by
    tracking exact timestamps of operations within a sliding time window.
    """

    def __init__(self, max_operations: int, window_seconds: float):
        """Initialize the sliding window rate limiter.

        Args:
            max_operations: Maximum operations allowed in time window
            window_seconds: Size of the sliding window in seconds
        """
        self.max_operations = max_operations
        self.window_seconds = window_seconds
        self.operations: deque = deque()

    def allow(self) -> bool:
        """Check if an operation should be allowed.

        Returns:
            True if operation is allowed, False if rate limit exceeded
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Remove operations outside the current window
        while self.operations and self.operations[0] < window_start:
            self.operations.popleft()

        # Check if we're within the limit
        if len(self.operations) < self.max_operations:
            self.operations.append(now)
            return True

        return False

    def count(self) -> int:
        """Get current count of operations in the window.

        Returns:
            Number of operations in current time window
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Remove operations outside the current window
        while self.operations and self.operations[0] < window_start:
            self.operations.popleft()

        return len(self.operations)

    def reset(self) -> None:
        """Reset the rate limiter."""
        self.operations.clear()


class MessageSizeTracker:
    """Track message sizes and detect potential DoS attacks.

    Monitors both message count and total bytes to detect abnormal patterns
    that might indicate a denial of service attack.
    """

    def __init__(
        self,
        max_messages_per_second: int = 1000,
        max_bytes_per_second: int = 10_000_000,
        window_seconds: float = 1.0
    ):
        """Initialize the message size tracker.

        Args:
            max_messages_per_second: Maximum message rate
            max_bytes_per_second: Maximum byte rate
            window_seconds: Time window for rate calculation
        """
        self.message_limiter = SlidingWindowRateLimiter(
            int(max_messages_per_second * window_seconds),
            window_seconds
        )
        self.max_bytes_per_second = max_bytes_per_second
        self.window_seconds = window_seconds
        self.bytes_in_window: deque = deque()  # (timestamp, size) tuples

    def track(self, message_size: int) -> bool:
        """Track a message and check if limits are exceeded.

        Args:
            message_size: Size of the message in bytes

        Returns:
            True if message is within limits, False if limits exceeded
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Check message rate
        if not self.message_limiter.allow():
            return False

        # Remove old byte counts
        while self.bytes_in_window and self.bytes_in_window[0][0] < window_start:
            self.bytes_in_window.popleft()

        # Calculate current byte rate
        current_bytes = sum(size for _, size in self.bytes_in_window)

        # Check if adding this message would exceed byte limit
        if current_bytes + message_size > self.max_bytes_per_second * self.window_seconds:
            return False

        # Track this message
        self.bytes_in_window.append((now, message_size))
        return True

    def get_stats(self) -> dict:
        """Get current statistics.

        Returns:
            Dictionary with message_count and byte_count
        """
        now = time.time()
        window_start = now - self.window_seconds

        # Remove old entries
        while self.bytes_in_window and self.bytes_in_window[0][0] < window_start:
            self.bytes_in_window.popleft()

        return {
            'message_count': self.message_limiter.count(),
            'byte_count': sum(size for _, size in self.bytes_in_window),
            'messages_per_second': self.message_limiter.count() / self.window_seconds,
            'bytes_per_second': sum(size for _, size in self.bytes_in_window) / self.window_seconds,
        }

    def reset(self) -> None:
        """Reset all tracking."""
        self.message_limiter.reset()
        self.bytes_in_window.clear()
