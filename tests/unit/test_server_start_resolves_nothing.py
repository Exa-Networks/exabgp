"""The daemon starts without asking the resolver for this host's FQDN.

server.run called util.dns.warn(), which timed socket.getfqdn() to warn about a slow
resolver. Nothing in the daemon uses the domain, and the lookup is what was slow: on the
macOS runner the reverse lookup went to mDNS and never answered, so every daemon of the
compiled wheel hung before its first log line (sampled in qa/bin/test_wheel).
"""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

import pytest

from exabgp.application import server
from exabgp.environment import getenv
from exabgp.reactor.loop import Reactor
from exabgp.util import dns


def _refuse(*_: object) -> NoReturn:
    raise AssertionError('the daemon start asked the resolver for the FQDN')


def test_the_daemon_start_does_not_look_up_the_fqdn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The real start, up to a real reactor which stops on a configuration it can not read.

    Nothing in server is replaced: a compiled server calls Configuration, Reactor and __exit
    directly, so replacing those names in the module would be seen by the interpreter only.
    """
    monkeypatch.setattr(dns, '__domain_name', None)
    monkeypatch.setattr(dns.socket, 'getfqdn', _refuse)
    monkeypatch.setattr(dns.socket, 'gethostbyaddr', _refuse)
    environment = getenv()
    monkeypatch.setattr(environment.api, 'cli', False)
    monkeypatch.setattr(environment.profile, 'enable', False)
    # no listener: the only way out of the reactor is then the configuration it could not load
    monkeypatch.setattr(environment.tcp, 'bind', [])
    monkeypatch.setattr(environment.daemon, 'daemonize', False)

    with pytest.raises(SystemExit) as exited:
        server.run('', [str(tmp_path / 'missing.conf')])
    # run exits only after the reactor returned, with the code the reactor returned
    assert exited.value.code == Reactor.Exit.configuration
