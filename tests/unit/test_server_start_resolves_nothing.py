"""The daemon starts without asking the resolver for this host's FQDN.

server.run called util.dns.warn(), which timed socket.getfqdn() to warn about a slow
resolver. Nothing in the daemon uses the domain, and the lookup is what was slow: on the
macOS runner the reverse lookup went to mDNS and never answered, so every daemon of the
compiled wheel hung before its first log line (sampled in qa/bin/test_wheel).
"""

from __future__ import annotations

from typing import NoReturn
from unittest.mock import MagicMock

import pytest

from exabgp.application import server
from exabgp.environment import getenv
from exabgp.util import dns


class Exited(Exception):
    pass


def _refuse(*_: object) -> NoReturn:
    raise AssertionError('the daemon start asked the resolver for the FQDN')


def test_the_daemon_start_does_not_look_up_the_fqdn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dns, '__domain_name', None)
    monkeypatch.setattr(dns.socket, 'getfqdn', _refuse)
    monkeypatch.setattr(dns.socket, 'gethostbyaddr', _refuse)
    monkeypatch.setattr(server, 'Configuration', MagicMock())
    reactor = MagicMock()
    reactor.return_value.run.return_value = 0
    monkeypatch.setattr(server, 'Reactor', reactor)

    def exited(_memory: bool, code: int) -> NoReturn:
        raise Exited(code)

    monkeypatch.setattr(server, '__exit', exited)
    environment = getenv()
    monkeypatch.setattr(environment.api, 'cli', False)
    monkeypatch.setattr(environment.profile, 'enable', False)

    with pytest.raises(Exited):
        server.run('', ['unused.conf'])
    reactor.return_value.run.assert_called_once()
