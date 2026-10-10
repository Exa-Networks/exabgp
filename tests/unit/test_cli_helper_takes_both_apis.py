"""`exabgp run` and `exabgp cli` accept the commands of 5.x as well as those of 6.0.

ExaBGP's own CLI helper relays what the operator types. It was held to API v6, so `exabgp run
show neighbor`, `exabgp run shutdown` and the shortcut `s n summary` were all refused as
unknown. `exabgp run reset` was worse: 5.0's daemon never answered `reset`, so `run` sent it and
exited 0 without waiting, and the refusal went unseen.

The helper still answers in v6 JSON. Only the dispatch of its commands changed.
"""

from __future__ import annotations

import os
import shutil
import socket
import tempfile
import threading
from argparse import Namespace
from collections.abc import Iterator
from unittest.mock import patch

import pytest

from exabgp.application import run
from exabgp.configuration.cli_process import API_PREFIX
from exabgp.environment import Environment, getenv
from exabgp.reactor.api.command import reactor as reactor_cmd
from exabgp.reactor.api.dispatch.common import UnknownCommand
from exabgp.reactor.api.dispatch.version import API_AUTO, API_V6, dispatch_for
from exabgp.reactor.api.processes import Processes
from exabgp.reactor.loop import Reactor
from tests.api_daemon import Daemon

CLI = f'{API_PREFIX}-1'


def _started(name: str) -> Processes:
    env = Environment()
    env.api.version = API_V6
    with patch('exabgp.reactor.api.processes.getenv', return_value=env):
        processes = Processes()
        processes._configuration = {name: {'run': ['/bin/cat'], 'encoder': 'json'}}
        with patch('exabgp.reactor.api.processes.log'):
            processes._select_encoder(name, processes._configuration[name])
    return processes


@pytest.fixture
def reactor() -> Iterator[Reactor]:
    """A real Reactor with real peers: the compiled dispatch refuses a Mock for its Reactor."""
    daemon = Daemon()
    yield daemon.reactor
    daemon.close()


@pytest.mark.parametrize('command', ['reset', 'shutdown', 'show neighbor summary', 'session reset', 'peer show'])
def test_the_cli_helper_takes_both_forms(reactor: Reactor, command: str) -> None:
    processes = _started(CLI)
    handler, _, _ = dispatch_for(processes.dispatch_version(CLI), command, reactor, CLI)
    assert callable(handler)


def test_reset_reaches_the_reset_handler(reactor: Reactor) -> None:
    processes = _started(CLI)
    handler, _, _ = dispatch_for(processes.dispatch_version(CLI), 'reset', reactor, CLI)
    assert handler is reactor_cmd.reset


def test_the_cli_helper_still_answers_in_v6() -> None:
    processes = _started(CLI)
    assert processes.detect_api_version(CLI, 'show neighbor') == API_V6
    assert processes.dispatch_version(CLI) == API_AUTO


def test_an_operator_helper_held_to_v6_is_still_refused_v4(reactor: Reactor) -> None:
    processes = _started('helper')
    assert processes.dispatch_version('helper') == API_V6
    with pytest.raises(UnknownCommand):
        dispatch_for(processes.dispatch_version('helper'), 'reset', reactor, 'helper')


# how long the listening end waits for `exabgp run` before the test gives up on it
ANSWER_TIMEOUT = 5
# the most the listening end reads of the one command it is sent
COMMAND_READ_SIZE = 4096


@pytest.fixture
def daemon_socket(monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> Iterator[list[bytes]]:
    """A unix socket where exabgp_api_socketpath says the daemon's is, answering once with `request.param`.

    The compiled run.py calls cmdline_socket directly, so replacing it on the module changes
    nothing there: `run` is given a real socket to find, and what it wrote is what the
    listening end read. mkdtemp and not tmp_path: a unix socket path must fit in about a
    hundred bytes.
    """
    directory = tempfile.mkdtemp()
    path = os.path.join(directory, f'{getenv().api.socketname}.sock')
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)
    server.settimeout(ANSWER_TIMEOUT)
    received: list[bytes] = []

    def answer() -> None:
        connection, _ = server.accept()
        with connection:
            connection.settimeout(ANSWER_TIMEOUT)
            received.append(connection.recv(COMMAND_READ_SIZE))
            connection.sendall(request.param)

    listening = threading.Thread(target=answer, daemon=True)
    listening.start()
    monkeypatch.setenv('exabgp_api_socketpath', path)
    # unix_socket records what it found here: registered so it is put back afterwards
    monkeypatch.delenv('exabgp_cli_socket', raising=False)
    try:
        yield received
    finally:
        listening.join(ANSWER_TIMEOUT)
        server.close()
        shutil.rmtree(directory)


@pytest.mark.parametrize(
    ('daemon_socket', 'status'),
    [(b'done\n', 0), (b'error\n', 1)],
    indirect=['daemon_socket'],
)
def test_run_waits_for_the_answer_to_reset(
    monkeypatch: pytest.MonkeyPatch, daemon_socket: list[bytes], status: int
) -> None:
    # 5.0 sent reset and exited 0 unread: only a run which read the answer exits 1 on `error`
    monkeypatch.delenv('exabgp_cli_transport', raising=False)
    with pytest.raises(SystemExit) as exited:
        run.cmdline(Namespace(command=['reset'], pipename=None, use_pipe=False, use_socket=True, batch_file=None))
    assert exited.value.code == status
    assert daemon_socket == [b'reset\n']
