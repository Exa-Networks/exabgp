"""`ttl-security` on an IPv4 neighbour claimed a protection it had not installed.

GTSM (RFC 5082) works by refusing packets which arrive with a TTL below a minimum.  On the
receive side that is the `IP_MINTTL` socket option, and `IP_MINTTL` does not exist on every
platform: it is absent on macOS, and `socket` has no attribute for it there.

`min_ttl` asked for it with `getattr(socket, 'IP_MINTTL', None)`, raised `AttributeError`
against itself when the answer was None, and then swallowed that with `except
AttributeError: pass`.  What it did next was set `IP_TTL`, which is the TTL this end puts
*on* the packets it sends.  That is the other half of GTSM and it is not a substitute: the
inbound check, the half which actually rejects a forged packet from off-link, was never
installed and nothing said so.

So an operator who configured `ttl-security` got a session, no warning, and no inbound
protection, while believing a security control was on.  Silence is the defect here rather
than the missing option: the platform cannot do it, and that is worth being told.

The sibling asymmetry is why this was easy to miss.  `min_ttlv6` hardcodes
`IPV6_MINHOPCOUNT` as 73 rather than looking it up, so it always calls `setsockopt` and
raises `TTLError` when the platform refuses.  On the same macOS box, IPv6 `ttl-security`
fails loudly and IPv4 fails silently, for the same configuration.

The first fix for this read the absence of `socket.IP_MINTTL` as "this platform has no
IP_MINTTL".  It is not that: CPython does not export the constant on any platform, so the
inbound check was missing on Linux too, and the new warning fired there with a reason which
was false.  The option number now comes from the kernel headers where CPython is silent,
as `min_ttlv6` already does for IPv6.
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


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown')
@pytest.mark.parametrize('system, option', [('Linux', 21), ('FreeBSD', 66)])
def test_the_kernel_option_is_used_when_python_does_not_export_it(
    monkeypatch: pytest.MonkeyPatch, warnings: list[str], system: str, option: int
) -> None:
    """The inbound check is installed where the kernel has it, whatever socket exports."""
    without_exported_ip_minttl(monkeypatch, system)
    io = FakeSocket()

    tcp.min_ttl(io, '192.0.2.1', TTL)

    assert (socket.IPPROTO_IP, option, TTL) in io.options, f'{system} has IP_MINTTL and it was not set'
    assert not warnings, f'{system} was said to lack an option it has: {warnings}'


def test_a_platform_without_ip_minttl_says_so(monkeypatch: pytest.MonkeyPatch, warnings: list[str]) -> None:
    """The operator asked for GTSM and is not getting the inbound half of it."""
    without_exported_ip_minttl(monkeypatch, 'Darwin')
    io = FakeSocket()

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
    io = FakeSocket()

    tcp.min_ttl(io, '192.0.2.1', TTL)

    assert not io.options, f'nothing could be installed, and yet options were set: {io.options}'


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown')
def test_ip_minttl_is_used_when_the_platform_has_it(monkeypatch: pytest.MonkeyPatch, warnings: list[str]) -> None:
    """The working path must not have been lost, and must not warn."""
    monkeypatch.setattr(socket, 'IP_MINTTL', 21, raising=False)
    io = FakeSocket()

    tcp.min_ttl(io, '192.0.2.1', TTL)

    assert (socket.IPPROTO_IP, 21, TTL) in io.options, 'IP_MINTTL was available and was not set'
    assert not warnings, f'the supported path warned about nothing: {warnings}'


def test_a_platform_which_rejects_ip_minttl_still_raises(monkeypatch: pytest.MonkeyPatch, warnings: list[str]) -> None:
    """Present but refused is a different thing from absent, and stays an error.

    The option exists, so the kernel refusing it means the request was wrong rather than
    unsupported, and the operator should not get a session out of it.
    """
    monkeypatch.setattr(socket, 'IP_MINTTL', 21, raising=False)
    io = FakeSocket(refuse={(socket.IPPROTO_IP, 21)})

    with pytest.raises(TTLError):
        tcp.min_ttl(io, '192.0.2.1', TTL)


@pytest.mark.rfc('rfc5082#3-must-not-drop-trusted-or-unknown', polarity='negative')
@pytest.mark.rfc('rfc5082#3-should-not-be-enabled-by-default')
def test_no_ttl_configured_touches_nothing(warnings: list[str]) -> None:
    """None (unset) and zero (maximum) both mean ttl-security is off."""
    for ttl in (None, 0):
        io = FakeSocket()
        tcp.min_ttl(io, '192.0.2.1', ttl)
        assert not io.options, f'ttl={ttl!r} set a socket option'
        assert not warnings, f'ttl={ttl!r} warned about an option nobody asked for'
