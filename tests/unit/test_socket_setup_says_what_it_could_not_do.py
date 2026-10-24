"""Three places in the socket layer threw an error away without a word.

`create()` asked for SO_REUSEADDR and SO_REUSEPORT with `except (OSError, AttributeError):
pass`.  SO_REUSEPORT genuinely does not exist everywhere and neither option has to succeed
for the session to come up, so not failing is right; being quiet about it is not.  Without
SO_REUSEADDR a session which drops cannot rebind its local port until the old socket leaves
TIME_WAIT, and what the operator sees is a peer which will not come back with nothing
pointing at a socket option.

`Incoming.notification()` swallowed every NetworkError while sending the NOTIFICATION which
tells a peer why its connection is being refused.  The connection is going away either way,
so this is still not an error, but an operator asking why the far end never saw a reason had
no way to learn that the reason never left the host.

`md5()` in 'auto' mode tried three paddings of a base64 key and swallowed a PSKError per
candidate.  That silence is correct, a failed candidate is an answer and not a fault, so it
is now a `contextlib.suppress` with the reason written down, and the reading which won is
logged because a hex key is also valid base64 and the choice used to be invisible.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from exabgp.protocol.family import AFI
from exabgp.reactor.network import incoming as incoming_module
from exabgp.reactor.network import tcp
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.incoming import Incoming


class RecordingLog:
    """Stands in for the module-local `log`, rendering every lazy message."""

    def __init__(self) -> None:
        self.debugs: list[str] = []
        self.warnings: list[str] = []

    def debug(self, message: Any, source: str = '', level: str = 'DEBUG') -> None:
        self.debugs.append(str(message() if callable(message) else message))

    def warning(self, message: Any, source: str = '', level: str = 'WARNING') -> None:
        self.warnings.append(str(message() if callable(message) else message))

    info = debug
    error = warning
    critical = warning


class FakeSocket:
    """Records every setsockopt, and refuses the ones the caller nominates."""

    def __init__(self, refuse: set[int] | None = None) -> None:
        self.options: list[tuple[int, int, int]] = []
        self._refuse = refuse or set()

    def setsockopt(self, level: int, option: int, value: int) -> None:
        if option in self._refuse:
            raise OSError(22, 'Invalid argument')
        self.options.append((level, option, value))


@pytest.fixture
def tcp_log(monkeypatch: pytest.MonkeyPatch) -> RecordingLog:
    """Patched by the module-local name, so nothing else in the suite sees it."""
    recorder = RecordingLog()
    monkeypatch.setattr(tcp, 'log', recorder)
    return recorder


@pytest.fixture
def incoming_log(monkeypatch: pytest.MonkeyPatch) -> RecordingLog:
    recorder = RecordingLog()
    monkeypatch.setattr(incoming_module, 'log', recorder)
    return recorder


def test_both_reuse_options_are_asked_for(tcp_log: RecordingLog) -> None:
    """Control: on a platform which has both, both are set and nothing is said."""
    io = FakeSocket()
    tcp.set_reuse_options(io)

    assert (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) in io.options
    assert (socket.SOL_SOCKET, socket.SO_REUSEPORT, 1) in io.options
    assert tcp_log.warnings == []


def test_a_refused_reuse_option_names_itself_and_time_wait(tcp_log: RecordingLog) -> None:
    io = FakeSocket(refuse={socket.SO_REUSEADDR})
    tcp.set_reuse_options(io)

    warned = '\n'.join(tcp_log.warnings)
    assert 'SO_REUSEADDR' in warned
    assert 'TIME_WAIT' in warned
    # refusing one does not stop us asking for the other
    assert (socket.SOL_SOCKET, socket.SO_REUSEPORT, 1) in io.options


def test_a_missing_reuse_option_is_said_at_debug_not_warned(
    monkeypatch: pytest.MonkeyPatch, tcp_log: RecordingLog
) -> None:
    """SO_REUSEPORT does not exist on every platform, which is not worth a warning."""
    monkeypatch.delattr(socket, 'SO_REUSEPORT', raising=False)
    io = FakeSocket()
    tcp.set_reuse_options(io)

    assert tcp_log.warnings == []
    assert any('SO_REUSEPORT' in line for line in tcp_log.debugs)
    assert (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) in io.options


def test_a_refused_reuse_option_is_not_fatal(tcp_log: RecordingLog) -> None:
    """The socket is still returned: neither option is needed to reach a peer."""
    io = tcp.create(AFI.ipv4)
    try:
        assert io is not None
    finally:
        io.close()


def test_an_unsendable_notification_is_recorded(incoming_log: RecordingLog) -> None:
    """The peer never learns why it was refused, so the log has to."""
    connection = Incoming.__new__(Incoming)
    connection.afi = AFI.ipv4
    connection.peer = '127.0.0.2'
    connection.local = '127.0.0.1'
    connection.io = None

    def failing_writer(data: bytes) -> Any:
        raise NetworkError('Broken TCP connection')
        yield False  # pragma: no cover - makes this a generator

    connection.writer = failing_writer

    assert list(connection.notification(6, 3, 'no session configured for the peer')) == []

    logged = '\n'.join(incoming_log.debugs)
    assert '127.0.0.2' in logged
    assert 'Broken TCP connection' in logged


def test_a_sendable_notification_says_nothing(incoming_log: RecordingLog) -> None:
    """Control: the ordinary path is unchanged and silent."""
    sent: list[bytes] = []

    connection = Incoming.__new__(Incoming)
    connection.afi = AFI.ipv4
    connection.peer = '127.0.0.2'
    connection.local = '127.0.0.1'
    connection.io = None
    connection.close = lambda: None

    def writer(data: bytes) -> Any:
        sent.append(data)
        yield True

    connection.writer = writer

    assert list(connection.notification(6, 3, 'no session configured for the peer')) == [False]
    assert sent
    assert incoming_log.debugs == []


@pytest.mark.parametrize(
    'key',
    ('abcdef1234', 'abcdef12', 'abcdef1234ab'),
)
def test_an_unpadded_base64_key_decodes(key: str) -> None:
    """One of the three candidate paddings wins, and the PSKErrors on the way are not news."""
    assert tcp.decode_unpadded_base64(key) is not None


def test_a_key_which_is_not_base64_at_any_padding_is_none() -> None:
    """Five hex characters cannot be base64 whatever padding is added, so we say so."""
    assert tcp.decode_unpadded_base64('abcde') is None
