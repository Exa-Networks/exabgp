"""What Control.loop does, seen from its three ends: the daemon's pipes and the CLI socket.

The loop is one 365 line method with its buffering in closures, so it is driven here as it
runs in production: a subprocess whose stdin and stdout are the daemon's side, and a real
Unix socket for the CLI clients. `./qa/bin/functional cli` reaches the single client mode
only; nothing ran the multi client one. These pin both before the method is split
(plan-large-function-decomposition step 2), and the split must not change any of them.
"""

from __future__ import annotations

import os
import select
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from exabgp.application.unixsocket import MAX_COMMAND_SIZE

TIMEOUT = 5.0


@dataclass
class Helper:
    process: subprocess.Popen[bytes]
    path: str
    pending: bytes = b''

    def daemon_reads(self) -> str:
        """The next line the helper wrote to the daemon."""
        assert self.process.stdout is not None
        deadline = time.monotonic() + TIMEOUT
        while b'\n' not in self.pending:
            remaining = deadline - time.monotonic()
            assert remaining > 0, f'the daemon saw no line, only {self.pending!r}'
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            if ready:
                chunk = os.read(self.process.stdout.fileno(), 4096)
                assert chunk, 'the helper closed its stdout'
                self.pending += chunk
        line, self.pending = self.pending.split(b'\n', 1)
        return line.decode()

    def daemon_hears_nothing(self, wait: float = 0.5) -> None:
        assert self.process.stdout is not None
        ready, _, _ = select.select([self.process.stdout], [], [], wait)
        if ready:
            self.pending += os.read(self.process.stdout.fileno(), 4096)
        assert self.pending == b''

    def daemon_says(self, data: bytes) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(data)
        self.process.stdin.flush()

    def connect(self) -> socket.socket:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(TIMEOUT)
        client.connect(self.path)
        return client


def received(client: socket.socket, expected: bytes) -> bytes:
    """Read until `expected` bytes have arrived, or the peer closes."""
    data = b''
    while len(data) < len(expected):
        chunk = client.recv(4096)
        if not chunk:
            break
        data += chunk
    return data


def nothing_received(client: socket.socket, wait: float = 0.5) -> None:
    client.settimeout(wait)
    try:
        data = client.recv(4096)
    except TimeoutError:
        data = b''
    finally:
        client.settimeout(TIMEOUT)
    assert data == b''


def start(multi_client: bool = False, max_clients: int = 10) -> Helper:
    # a Unix socket path is capped at 104 bytes on macOS, which pytest's tmp_path can pass
    directory = tempfile.mkdtemp(prefix='exasock')
    env = dict(os.environ)
    env.pop('exabgp_api_socketpath', None)
    env['exabgp_cli_socket'] = directory + '/'
    env['exabgp_api_multi_client'] = 'true' if multi_client else 'false'
    env['exabgp_api_max_clients'] = str(max_clients)
    process = subprocess.Popen(
        [sys.executable, '-c', 'from exabgp.application.unixsocket import main; main()'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    helper = Helper(process, directory + '/exabgp.sock')
    assert helper.daemon_reads() == 'session ack enable'
    helper.daemon_says(b'done\n')
    return helper


def stop(helper: Helper) -> None:
    if helper.process.poll() is None:
        helper.process.kill()
    helper.process.communicate(timeout=TIMEOUT)
    directory = os.path.dirname(helper.path)
    if os.path.exists(helper.path):
        os.unlink(helper.path)
    os.rmdir(directory)


@pytest.fixture
def single() -> Iterator[Helper]:
    helper = start()
    yield helper
    stop(helper)


@pytest.fixture
def multi() -> Iterator[Helper]:
    helper = start(multi_client=True, max_clients=2)
    yield helper
    stop(helper)


# ------------------------------------------------------------------------------ single client


def test_a_command_reaches_the_daemon_and_its_answer_the_client(single: Helper) -> None:
    client = single.connect()
    client.sendall(b'show neighbor\n')
    assert single.daemon_reads() == 'show neighbor'
    single.daemon_says(b'answer\ndone\n')
    assert received(client, b'answer\ndone\n') == b'answer\ndone\n'


def test_a_command_is_forwarded_once_its_newline_arrives(single: Helper) -> None:
    client = single.connect()
    client.sendall(b'show ')
    single.daemon_hears_nothing()
    client.sendall(b'neighbor\nshow adj-rib out\n')
    assert single.daemon_reads() == 'show neighbor'
    assert single.daemon_reads() == 'show adj-rib out'


def test_a_second_client_waits_for_the_first_to_leave(single: Helper) -> None:
    # The loop stops polling the listening socket while a client is connected, so the
    # "another CLI client is already connected" branch never runs: the second client sits
    # in the kernel's accept queue, unanswered, until the first leaves.
    first = single.connect()
    first.sendall(b'one\n')
    assert single.daemon_reads() == 'one'

    second = single.connect()
    second.sendall(b'two\n')
    single.daemon_hears_nothing()
    nothing_received(second)

    first.sendall(b'three\n')
    assert single.daemon_reads() == 'three'

    first.close()
    assert single.daemon_reads() == 'bye'
    assert single.daemon_reads() == 'two'


def test_a_client_leaving_says_bye_and_frees_the_socket(single: Helper) -> None:
    first = single.connect()
    first.sendall(b'one\n')
    assert single.daemon_reads() == 'one'
    first.close()
    assert single.daemon_reads() == 'bye'

    # what the daemon says with no client connected goes nowhere
    single.daemon_says(b'stale\n')
    time.sleep(0.3)

    second = single.connect()
    second.sendall(b'two\n')
    assert single.daemon_reads() == 'two'
    single.daemon_says(b'fresh\n')
    assert received(second, b'fresh\n') == b'fresh\n'


def test_a_command_with_no_newline_past_the_limit_ends_the_helper(single: Helper) -> None:
    client = single.connect()
    client.sendall(b'x' * (MAX_COMMAND_SIZE + 2048))
    assert single.process.wait(timeout=TIMEOUT) == 1
    assert single.process.stderr is not None
    assert b'received a command larger than' in single.process.stderr.read()


def test_sigterm_ends_the_helper_and_removes_the_socket(single: Helper) -> None:
    single.connect()
    single.process.send_signal(signal.SIGTERM)
    assert single.process.wait(timeout=TIMEOUT) == 0
    assert not os.path.exists(single.path)


# ------------------------------------------------------------------------------ multi client


def test_an_answer_goes_to_the_client_which_asked(multi: Helper) -> None:
    first = multi.connect()
    second = multi.connect()
    first.sendall(b'one\n')
    assert multi.daemon_reads() == 'one'
    multi.daemon_says(b'answer one\ndone\n')
    assert received(first, b'answer one\ndone\n') == b'answer one\ndone\n'
    nothing_received(second)

    second.sendall(b'two\n')
    assert multi.daemon_reads() == 'two'
    multi.daemon_says(b'answer two\ndone\n')
    assert received(second, b'answer two\ndone\n') == b'answer two\ndone\n'
    nothing_received(first)


def test_an_event_goes_to_every_client(multi: Helper) -> None:
    first = multi.connect()
    second = multi.connect()
    # the helper only knows a client once it has accepted it, which a command proves
    first.sendall(b'one\n')
    assert multi.daemon_reads() == 'one'
    second.sendall(b'two\n')
    assert multi.daemon_reads() == 'two'

    multi.daemon_says(b'neighbor 127.0.0.1 up\n')
    assert received(first, b'neighbor 127.0.0.1 up\n') == b'neighbor 127.0.0.1 up\n'
    assert received(second, b'neighbor 127.0.0.1 up\n') == b'neighbor 127.0.0.1 up\n'


def test_a_client_past_the_maximum_is_turned_away(multi: Helper) -> None:
    first = multi.connect()
    second = multi.connect()
    first.sendall(b'one\n')
    assert multi.daemon_reads() == 'one'
    second.sendall(b'two\n')
    assert multi.daemon_reads() == 'two'

    third = multi.connect()
    assert received(third, b'error: maximum concurrent clients reached\ndone\n') == (
        b'error: maximum concurrent clients reached\ndone\n'
    )
    assert third.recv(4096) == b''


def test_a_client_leaving_frees_its_place_and_says_nothing(multi: Helper) -> None:
    # a client is only named to the daemon by a uuid nothing in the loop sets, so no bye
    first = multi.connect()
    second = multi.connect()
    first.sendall(b'one\n')
    assert multi.daemon_reads() == 'one'
    second.sendall(b'two\n')
    assert multi.daemon_reads() == 'two'

    first.close()
    second.sendall(b'three\n')
    assert multi.daemon_reads() == 'three'

    third = multi.connect()
    third.sendall(b'four\n')
    assert multi.daemon_reads() == 'four'
