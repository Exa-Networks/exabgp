"""Daemon-side command failures must produce failed CLI results."""

from argparse import Namespace
from pathlib import Path

import pytest

from exabgp.application import run


class ScriptedSocket:
    def __init__(self, responses: list[bytes]) -> None:
        self.responses = responses
        self.sent = b''
        self.closed = False

    def settimeout(self, _timeout: float) -> None:
        pass

    def connect(self, _path: str) -> None:
        pass

    def sendall(self, data: bytes) -> None:
        self.sent += data

    def recv(self, _size: int) -> bytes:
        return self.responses.pop(0) if self.responses else b''

    def close(self) -> None:
        self.closed = True


def socket_result(monkeypatch: pytest.MonkeyPatch, responses: list[bytes]) -> bool:
    client = ScriptedSocket(responses)
    monkeypatch.setattr(run.sock, 'socket', lambda *_args: client)

    result = run.send_command_socket('/tmp/exabgp.sock', 'show neighbor')

    assert client.sent == b'show neighbor\n'
    assert client.closed is True
    assert isinstance(result, bool)
    return result


def test_socket_done_is_success(monkeypatch: pytest.MonkeyPatch) -> None:
    assert socket_result(monkeypatch, [b'done\n']) is True


@pytest.mark.parametrize('response', [b'error\n', b'shutdown\n', b'', b'partial', b'partial\n'])
def test_socket_without_done_is_failure(monkeypatch: pytest.MonkeyPatch, response: bytes) -> None:
    assert socket_result(monkeypatch, [response, b'']) is False


def test_return_output_raises_when_connection_closes_early(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ScriptedSocket([b'partial', b''])
    monkeypatch.setattr(run.sock, 'socket', lambda *_args: client)

    with pytest.raises(RuntimeError, match='closed before ExaBGP completed'):
        run.send_command_socket('/tmp/exabgp.sock', 'show neighbor', return_output=True)


def test_cmdline_socket_maps_daemon_failure_to_exit_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, 'unix_socket', lambda *_args: ['/tmp/'])
    monkeypatch.setattr(run.os.path, 'exists', lambda _path: True)
    monkeypatch.setattr(run, 'send_command_socket', lambda *_args, **_kwargs: False)

    with pytest.raises(SystemExit) as raised:
        run.cmdline_socket('exabgp', 'show neighbor')

    assert isinstance(raised.value, SystemExit)
    assert raised.value.code == 1


def test_batch_counts_a_daemon_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    batch = tmp_path / 'commands.txt'
    batch.write_text('show neighbor\n')
    monkeypatch.setattr(run, 'cmdline_socket', lambda *_args, **_kwargs: False)

    with pytest.raises(SystemExit) as raised:
        run.cmdline_batch(str(batch), 'exabgp', 'exabgp', False, Namespace())

    assert isinstance(raised.value, SystemExit)
    assert raised.value.code == 1
