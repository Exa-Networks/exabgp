"""test_reactor_signal.py

Unit tests for reactor/interrupt.py (Signal class).

Test Coverage:
- Signal deferral when not ready (issue #1172 fix)
- Signal processing when ready
- mark_ready() behavior
- Deduplicated signal queue before ready
- rearm() processes queued signals
"""

from __future__ import annotations

import signal
from unittest.mock import patch


from exabgp.reactor.interrupt import Signal


class TestSignalInit:
    """Test Signal initialization."""

    def test_init_not_ready(self) -> None:
        """Test Signal starts in not-ready state."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            assert sig._ready is False

    def test_init_empty_pending_queue(self) -> None:
        """Test Signal starts with empty pending queue."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            assert sig._pending == []

    def test_init_received_none(self) -> None:
        """Test Signal starts with no received signal."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            assert sig.received == Signal.NONE

    def test_init_registers_handlers(self) -> None:
        """Test Signal registers signal handlers on init."""
        with patch('exabgp.reactor.interrupt.signal.signal') as mock_signal:
            Signal()
            # Should register 5 signals
            assert mock_signal.call_count == 5


class TestSignalBeforeReady:
    """Test signal handling before mark_ready() is called (issue #1172)."""

    def test_sigusr1_deferred_when_not_ready(self) -> None:
        """Test SIGUSR1 is deferred when not ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            assert sig._ready is False

            # Simulate SIGUSR1
            sig.sigusr1(signal.SIGUSR1, None)

            # Should be queued, not processed
            assert sig.received == Signal.NONE
            assert sig._pending == [(Signal.RELOAD, signal.SIGUSR1)]

    def test_sigusr2_deferred_when_not_ready(self) -> None:
        """Test SIGUSR2 is deferred when not ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.sigusr2(signal.SIGUSR2, None)

            assert sig.received == Signal.NONE
            assert sig._pending == [(Signal.FULL_RELOAD, signal.SIGUSR2)]

    def test_sigterm_deferred_when_not_ready(self) -> None:
        """Test SIGTERM is deferred when not ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.sigterm(signal.SIGTERM, None)

            assert sig.received == Signal.NONE
            assert sig._pending == [(Signal.SHUTDOWN, signal.SIGTERM)]

    def test_sighup_deferred_when_not_ready(self) -> None:
        """Test SIGHUP is deferred when not ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.sighup(signal.SIGHUP, None)

            assert sig.received == Signal.NONE
            assert sig._pending == [(Signal.SHUTDOWN, signal.SIGHUP)]

    def test_sigalrm_deferred_when_not_ready(self) -> None:
        """Test SIGALRM is deferred when not ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.sigalrm(signal.SIGALRM, None)

            assert sig.received == Signal.NONE
            assert sig._pending == [(Signal.RESTART, signal.SIGALRM)]


class TestSignalAfterReady:
    """Test signal handling after mark_ready() is called."""

    def test_sigusr1_processed_when_ready(self) -> None:
        """Test SIGUSR1 is processed immediately when ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            sig.mark_ready()

            sig.sigusr1(signal.SIGUSR1, None)

            assert sig.received == Signal.RELOAD
            assert sig.number == signal.SIGUSR1
            assert sig._pending == []

    def test_sigusr2_processed_when_ready(self) -> None:
        """Test SIGUSR2 is processed immediately when ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            sig.mark_ready()

            sig.sigusr2(signal.SIGUSR2, None)

            assert sig.received == Signal.FULL_RELOAD
            assert sig.number == signal.SIGUSR2

    def test_sigterm_processed_when_ready(self) -> None:
        """Test SIGTERM is processed immediately when ready."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            sig.mark_ready()

            sig.sigterm(signal.SIGTERM, None)

            assert sig.received == Signal.SHUTDOWN
            assert sig.number == signal.SIGTERM

    def test_signal_ignored_when_already_received(self) -> None:
        """Test second signal is ignored when one is already pending processing."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            sig.mark_ready()

            # First signal
            sig.sigusr1(signal.SIGUSR1, None)
            assert sig.received == Signal.RELOAD

            # Second signal should be ignored
            sig.sigterm(signal.SIGTERM, None)
            assert sig.received == Signal.RELOAD  # Still RELOAD, not SHUTDOWN


class TestMarkReady:
    """Test mark_ready() behavior."""

    def test_mark_ready_sets_ready_flag(self) -> None:
        """Test mark_ready sets _ready to True."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            assert sig._ready is False

            sig.mark_ready()

            assert sig._ready is True

    def test_mark_ready_processes_first_pending_signal(self) -> None:
        """Test mark_ready processes the first pending signal."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            # Queue a signal before ready
            sig.sigusr1(signal.SIGUSR1, None)
            assert sig._pending == [(Signal.RELOAD, signal.SIGUSR1)]
            assert sig.received == Signal.NONE

            # Now mark ready
            sig.mark_ready()

            # First pending signal should be processed
            assert sig.received == Signal.RELOAD
            assert sig.number == signal.SIGUSR1
            assert sig._pending == []

    def test_mark_ready_no_op_without_pending(self) -> None:
        """Test mark_ready is no-op when no pending signal."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.mark_ready()

            assert sig._ready is True
            assert sig.received == Signal.NONE
            assert sig._pending == []

    def test_mark_ready_idempotent(self) -> None:
        """Test calling mark_ready multiple times is safe."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.mark_ready()
            sig.mark_ready()
            sig.mark_ready()

            assert sig._ready is True


class TestSignalQueueDeduplication:
    """Test deduplicated signal queue behavior."""

    def test_duplicate_signal_ignored(self) -> None:
        """Test duplicate signals are not queued twice."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            # Same signal twice
            sig.sigusr1(signal.SIGUSR1, None)
            sig.sigusr1(signal.SIGUSR1, None)

            # Should only be queued once
            assert len(sig._pending) == 1
            assert sig._pending == [(Signal.RELOAD, signal.SIGUSR1)]

    def test_different_signals_both_queued(self) -> None:
        """Test different signals are both queued."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.sigusr1(signal.SIGUSR1, None)
            sig.sigterm(signal.SIGTERM, None)

            # Both should be queued in order
            assert len(sig._pending) == 2
            assert sig._pending[0] == (Signal.RELOAD, signal.SIGUSR1)
            assert sig._pending[1] == (Signal.SHUTDOWN, signal.SIGTERM)

    def test_queue_order_preserved(self) -> None:
        """Test signal queue preserves order."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.sigterm(signal.SIGTERM, None)
            sig.sigusr1(signal.SIGUSR1, None)
            sig.sigusr2(signal.SIGUSR2, None)

            assert sig._pending[0] == (Signal.SHUTDOWN, signal.SIGTERM)
            assert sig._pending[1] == (Signal.RELOAD, signal.SIGUSR1)
            assert sig._pending[2] == (Signal.FULL_RELOAD, signal.SIGUSR2)

    def test_sighup_sigterm_deduplicated(self) -> None:
        """Test SIGHUP and SIGTERM both map to SHUTDOWN and deduplicate."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            sig.sigterm(signal.SIGTERM, None)
            sig.sighup(signal.SIGHUP, None)  # Also SHUTDOWN

            # Should only have one SHUTDOWN queued
            assert len(sig._pending) == 1
            assert sig._pending[0][0] == Signal.SHUTDOWN


class TestRearmWithQueue:
    """Test rearm() processes queued signals."""

    def test_rearm_processes_next_queued_signal(self) -> None:
        """Test rearm processes the next signal from queue."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            # Queue multiple signals
            sig.sigusr1(signal.SIGUSR1, None)
            sig.sigterm(signal.SIGTERM, None)

            # Mark ready - processes first signal (RELOAD)
            sig.mark_ready()
            assert sig.received == Signal.RELOAD
            assert len(sig._pending) == 1

            # Rearm - should process next signal (SHUTDOWN)
            sig.rearm()
            assert sig.received == Signal.SHUTDOWN
            assert sig._pending == []

    def test_rearm_clears_when_queue_empty(self) -> None:
        """Test rearm clears received when queue is empty."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            sig.mark_ready()

            sig.sigusr1(signal.SIGUSR1, None)
            assert sig.received == Signal.RELOAD

            # Rearm with empty queue
            sig.rearm()
            assert sig.received == Signal.NONE
            assert sig.number == 0

    def test_rearm_preserves_ready_state(self) -> None:
        """Test rearm does NOT reset _ready flag."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()
            sig.mark_ready()
            assert sig._ready is True

            sig.rearm()

            # Should still be ready
            assert sig._ready is True

    def test_full_signal_processing_cycle(self) -> None:
        """Test complete cycle: queue -> mark_ready -> rearm -> rearm."""
        with patch('exabgp.reactor.interrupt.signal.signal'):
            sig = Signal()

            # Queue 3 signals before ready
            sig.sigusr1(signal.SIGUSR1, None)
            sig.sigterm(signal.SIGTERM, None)
            sig.sigalrm(signal.SIGALRM, None)
            assert len(sig._pending) == 3

            # mark_ready processes first
            sig.mark_ready()
            assert sig.received == Signal.RELOAD
            assert len(sig._pending) == 2

            # rearm processes second
            sig.rearm()
            assert sig.received == Signal.SHUTDOWN
            assert len(sig._pending) == 1

            # rearm processes third
            sig.rearm()
            assert sig.received == Signal.RESTART
            assert len(sig._pending) == 0

            # rearm with empty queue
            sig.rearm()
            assert sig.received == Signal.NONE


class TestSignalName:
    """Test Signal.name() class method."""

    def test_name_returns_signal_name(self) -> None:
        """Test name returns human-readable signal name."""
        assert Signal.name(Signal.NONE) == 'none'
        assert Signal.name(Signal.SHUTDOWN) == 'shutdown'
        assert Signal.name(Signal.RESTART) == 'restart'
        assert Signal.name(Signal.RELOAD) == 'reload'
        assert Signal.name(Signal.FULL_RELOAD) == 'full reload'

    def test_name_returns_unknown_for_invalid(self) -> None:
        """Test name returns 'unknown' for invalid signal."""
        assert Signal.name(999) == 'unknown'
