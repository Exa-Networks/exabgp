"""exabgp.log.destination host:<addr>[:<port>] sends the log to a remote syslog server.

The destination was accepted, then fell through to the file branch of option.setup(): the
log went to a local file named after the host, in the current directory.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest

from exabgp.environment import getenv
from exabgp.logger.handler import SYSLOG_UDP_PORT, remote_syslog_address
from exabgp.logger.option import option


@pytest.mark.parametrize(
    ('location', 'expected'),
    [
        ('192.0.2.1', ('192.0.2.1', SYSLOG_UDP_PORT)),
        ('192.0.2.1:1514', ('192.0.2.1', 1514)),
        ('syslog.example.net', ('syslog.example.net', SYSLOG_UDP_PORT)),
        ('2001:db8::1', ('2001:db8::1', SYSLOG_UDP_PORT)),
        ('[2001:db8::1]:1514', ('2001:db8::1', 1514)),
        ('[2001:db8::1]', ('2001:db8::1', SYSLOG_UDP_PORT)),
    ],
)
def test_the_address_of_a_host_destination(location: str, expected: tuple[str, int]) -> None:
    assert remote_syslog_address(location) == expected


@pytest.mark.parametrize('location', ['', '192.0.2.1:', '192.0.2.1:0', '192.0.2.1:65536', '192.0.2.1:x', '[::1]x'])
def test_a_bad_host_destination_is_refused(location: str) -> None:
    with pytest.raises(ValueError):
        remote_syslog_address(location)


@pytest.fixture
def restored(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ('logger', 'formater', 'destination', 'level', 'logit', 'option', 'short', 'cwd'):
        monkeypatch.setattr(option, name, getattr(option, name))
    env = getenv()
    for name in ('destination', 'level', 'enable', 'all'):
        monkeypatch.setattr(env.log, name, getattr(env.log, name))


@pytest.mark.usefixtures('restored')
def test_host_destination_sends_to_the_syslog_server(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / 'cwd'
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(('127.0.0.1', 0))
    server.settimeout(5)
    try:
        port = server.getsockname()[1]
        env = getenv()
        env.log.destination = f'host:127.0.0.1:{port}'
        env.log.level = 'INFO'
        option.setup(env)
        assert option.logger is not None
        option.logger.warning('remote syslog audit')
        data, _ = server.recvfrom(4096)
        for handler in option.logger.handlers:
            handler.close()
    finally:
        server.close()
    assert b'remote syslog audit' in data
    assert list(cwd.iterdir()) == []
