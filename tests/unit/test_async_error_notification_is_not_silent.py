#!/usr/bin/env python3
"""ASYNC._notify_error is the handler whose whole job is to stop a client hanging.

Its own docstring says the handler exists "so the client doesn't hang waiting for
done/error".  It wrapped the call in `except Exception: pass`, so when the notifier
itself failed the client hung forever and nothing was written down anywhere.

The swallow stays, because this runs inside the event loop and raising takes more
than the one client, but it now says which service will hang.

The logger is patched by the module-local name `exabgp.reactor.asynchronous.log`,
not on the shared logger class: patching the class made this pass alone and fail in
the full suite, and a result which depends on collection order is not evidence.
"""

from __future__ import annotations

import pytest

from exabgp.reactor import asynchronous
from exabgp.reactor.asynchronous import ASYNC


class RecordingLog:
    def __init__(self):
        self.errors = []

    def _record(self, message, source=None):
        self.errors.append(message() if callable(message) else message)

    error = _record
    warning = _record
    debug = _record
    info = _record


@pytest.fixture
def recorded(monkeypatch):
    recorder = RecordingLog()
    monkeypatch.setattr(asynchronous, 'log', recorder)
    return recorder


def _failing_callback():
    raise RuntimeError('the callback itself broke')
    yield  # pragma: no cover - makes this a generator


def test_a_failed_notification_names_the_service_that_will_hang(recorded):
    async_queue = ASYNC()

    def notifier(uid):
        raise OSError(32, 'Broken pipe')

    async_queue.set_error_handler(notifier)
    async_queue.schedule('service-17', 'announce route 10.0.0.0/24 next-hop 1.2.3.4', _failing_callback())
    async_queue.run()

    logged = '\n'.join(recorded.errors)
    assert 'service-17' in logged
    assert 'Broken pipe' in logged


def test_a_working_notification_is_called_and_says_nothing_extra(recorded):
    """Control: the ordinary path is unchanged."""
    async_queue = ASYNC()
    notified = []

    async_queue.set_error_handler(notified.append)
    async_queue.schedule('service-18', 'announce route 10.0.0.0/24 next-hop 1.2.3.4', _failing_callback())
    async_queue.run()

    assert notified == ['service-18']
    assert not [line for line in recorded.errors if 'notification' in line]


def test_no_error_handler_is_not_an_error(recorded):
    """Control: nothing registered means nothing to notify."""
    async_queue = ASYNC()
    async_queue.schedule('service-19', 'announce route 10.0.0.0/24 next-hop 1.2.3.4', _failing_callback())
    async_queue.run()
    assert not [line for line in recorded.errors if 'notification' in line]
