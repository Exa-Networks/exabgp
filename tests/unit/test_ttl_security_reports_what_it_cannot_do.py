"""`ttl-security` on an IPv4 neighbour claimed a protection it had not installed.

GTSM (RFC 5082) works by refusing packets which arrive with a TTL below a minimum.  On the
receive side that is the `IP_MINTTL` socket option.  `min_ttl` reached for
`socket.IP_MINTTL` and swallowed the `AttributeError` with `except AttributeError: pass`.

CPython exports `IP_MINTTL` on no platform at all: `socketmodule.c` has no entry for it.
So the lookup failed everywhere, Linux included, and the inbound half of GTSM, the half
which actually rejects a forged packet from off-link, was never installed on any host.
Nothing said so either, so an operator who configured `ttl-security` got a session, no
warning, and no inbound protection, while believing a security control was on.

The option number now comes from the kernel headers where CPython is silent, 21 on Linux
and 66 on FreeBSD, which is what `min_ttlv6` already does for `IPV6_MINHOPCOUNT`.  macOS
has no such option and is told so rather than left quiet.
"""

from __future__ import annotations

import socket
from typing import Any

import pytest

from exabgp.reactor.network import tcp
from exabgp.reactor.network.error import TTLError

TTL = 254


class FakeSocket:
    """Records every setsockopt, and refuses the ones the caller nominates."""

    def __init__(self, refuse: set[tuple[int, int]] | None = None) -> None:
        self.options: list[tuple[int, int, int]] = []
        self._refuse = refuse or set()

    def setsockopt(self, level: int, option: int, value: int) -> None:
        if (level, option) in self._refuse:
            raise OSError(22, 'Invalid argument')
        self.options.append((level, option, value))


@pytest.fixture
def warnings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every warning tcp.py emits, rendered."""
    captured: list[str] = []

    def record(message: Any, source: str = '', level: str = 'WARNING') -> None:
        captured.append(str(message() if callable(message) else message))

    monkeypatch.setattr(tcp.log, 'warning', record)
    return captured


def without_exported_ip_minttl(monkeypatch: pytest.MonkeyPatch, system: str) -> None:
    """What every CPython build looks like: no socket.IP_MINTTL, whatever the kernel has."""
    monkeypatch.delattr(socket, 'IP_MINTTL', raising=False)
    monkeypatch.setattr(tcp.platform, 'system', lambda: system)


@pytest.mark.parametrize('system, option', [('Linux', 21), ('FreeBSD', 66)])
def test_the_kernel_option_is_used_when_python_does_not_export_it(
    monkeypatch: pytest.MonkeyPatch, warnings: list[str], system: str, option: int
) -> None:
    """The inbound check is installed where the kernel has it, whatever socket exports."""
    without_exported_ip_minttl(monkeypatch, system)
    io: Any = FakeSocket()

    tcp.min_ttl(io, '192.0.2.1', TTL)

    assert (socket.IPPROTO_IP, option, TTL) in io.options, f'{system} has IP_MINTTL and it was not set'
    assert not warnings, f'{system} was said to lack an option it has: {warnings}'


def test_a_platform_without_ip_minttl_says_so(monkeypatch: pytest.MonkeyPatch, warnings: list[str]) -> None:
    """The operator asked for GTSM and is not getting the inbound half of it."""
    without_exported_ip_minttl(monkeypatch, 'Darwin')
    io: Any = FakeSocket()

    tcp.min_ttl(io, '192.0.2.1', TTL)

    assert warnings, 'ttl-security was configured, the inbound check was not installed, and nothing was logged'
    said = ' '.join(warnings).lower()
    assert 'ttl-security' in said or 'ip_minttl' in said, f'the warning does not name what is missing: {warnings}'


def test_a_missing_ip_minttl_warns_rather_than_raises(monkeypatch: pytest.MonkeyPatch, warnings: list[str]) -> None:
    """Warning, not raising.  A platform without IP_MINTTL worked before and still does.

    Turning this into a TTLError would refuse to bring up sessions which are running today
    on every host where the option is absent, which is a bigger change than the bug.
    """
    without_exported_ip_minttl(monkeypatch, 'Darwin')
    io: Any = FakeSocket()

    tcp.min_ttl(io, '192.0.2.1', TTL)

    assert not io.options, f'nothing could be installed, and yet options were set: {io.options}'


def test_ip_minttl_is_used_when_the_platform_has_it(monkeypatch: pytest.MonkeyPatch, warnings: list[str]) -> None:
    """The working path must not have been lost, and must not warn."""
    monkeypatch.setattr(socket, 'IP_MINTTL', 21, raising=False)
    io: Any = FakeSocket()

    tcp.min_ttl(io, '192.0.2.1', TTL)

    assert (socket.IPPROTO_IP, 21, TTL) in io.options, 'IP_MINTTL was available and was not set'
    assert not warnings, f'the supported path warned about nothing: {warnings}'


def test_a_platform_which_rejects_ip_minttl_still_raises(monkeypatch: pytest.MonkeyPatch, warnings: list[str]) -> None:
    """Present but refused is a different thing from absent, and stays an error.

    The option exists, so the kernel refusing it means the request was wrong rather than
    unsupported, and the operator should not get a session out of it.
    """
    monkeypatch.setattr(socket, 'IP_MINTTL', 21, raising=False)
    io: Any = FakeSocket(refuse={(socket.IPPROTO_IP, 21)})

    with pytest.raises(TTLError):
        tcp.min_ttl(io, '192.0.2.1', TTL)


def test_no_ttl_configured_touches_nothing(warnings: list[str]) -> None:
    """None (unset) and zero (maximum) both mean ttl-security is off."""
    for ttl in (None, 0):
        io: Any = FakeSocket()
        tcp.min_ttl(io, '192.0.2.1', ttl)
        assert not io.options, f'ttl={ttl!r} set a socket option'
        assert not warnings, f'ttl={ttl!r} warned about an option nobody asked for'
