"""The checker sets up the addresses it announces on every system it runs on, or says it could not.

Three bugs, all on the way to an address being on the box:

- the addresses were read with `ifconfig lo` outside Linux, where the loopback is `lo0`, so a
  checker without `--ip` found none and stopped with `No IP found`
- they were added with `ip address add` everywhere, and macOS and the BSDs have no `ip`
- exit code 2 from `ip` was taken to mean "already there", but `ip` exits 2 for every netlink
  error, a refusal to a user who is not root included: the address was not added, and the
  checker announced it anyway
"""

from __future__ import annotations

import subprocess
import sys
from ipaddress import ip_network
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.application import healthcheck
from exabgp.application.healthcheck import AddressSetupError, address_command, loopback, setup_ips

COMPILED = not str(healthcheck.__file__).endswith('.py')
ON_LINUX = pytest.mark.skipif(
    COMPILED and not sys.platform.startswith('linux'), reason='compiled for another platform, sys.platform is fixed'
)
ON_BSD = pytest.mark.skipif(
    COMPILED and sys.platform.startswith('linux'), reason='compiled for another platform, sys.platform is fixed'
)

V4 = ip_network('192.0.2.10/32')
V6 = ip_network('2001:db8::10/128')


@ON_LINUX
def test_the_loopback_on_linux_is_lo() -> None:
    with patch('sys.platform', 'linux'):
        assert loopback() == 'lo'


@ON_BSD
@pytest.mark.parametrize('platform', ['darwin', 'freebsd14', 'netbsd10'])
def test_the_loopback_elsewhere_is_lo0(platform: str) -> None:
    with patch('sys.platform', platform):
        assert loopback() == 'lo0'


@ON_BSD
def test_addresses_are_read_from_lo0_outside_linux() -> None:
    seen: list[list[str]] = []
    real = subprocess.Popen

    def popen(cmd: list[str], **_: Any) -> Any:
        seen.append(cmd)
        return real(['true'], stdout=subprocess.PIPE)

    with patch('sys.platform', 'darwin'), patch.object(healthcheck.subprocess, 'Popen', popen):
        healthcheck.system_ips(None, None, False, False)
    assert seen == [['ifconfig', 'lo0']]


@ON_LINUX
def test_linux_uses_ip_with_the_label() -> None:
    with patch('sys.platform', 'linux'):
        assert address_command('add', V4, 'lo', 'web', False) == [
            'ip', 'address', 'add', '192.0.2.10/32', 'dev', 'lo', 'label', 'lo:web',
        ]  # fmt: skip
        assert address_command('delete', V6, 'lo', None, True) == [
            'sudo', 'ip', 'address', 'delete', '2001:db8::10/128', 'dev', 'lo',
        ]  # fmt: skip


@ON_BSD
def test_elsewhere_an_address_is_an_ifconfig_alias() -> None:
    with patch('sys.platform', 'darwin'):
        assert address_command('add', V4, 'lo0', 'web', False) == ['ifconfig', 'lo0', 'inet', '192.0.2.10/32', 'alias']
        assert address_command('delete', V6, 'lo0', None, True) == [
            'sudo', 'ifconfig', 'lo0', 'inet6', '2001:db8::10/128', '-alias',
        ]  # fmt: skip


class Listing:
    """What `ip -o address show` or `ifconfig` prints for the addresses given, as Popen would."""

    def __init__(self, cmd: list[str], addresses: list[Any]) -> None:
        if cmd[0] == 'ip':
            self.stdout = [f'1: lo    inet{family(a)} {a} scope global lo\n'.encode() for a in addresses]
        else:
            self.stdout = [f'inet{family(a)} {a.network_address} prefixlen {a.prefixlen}\n'.encode() for a in addresses]


def family(address: Any) -> str:
    return '6' if address.version == 6 else ''


def _setup(returncode: int, stderr: bytes, present_after: bool) -> None:
    """Add V4 with `ip`/`ifconfig` answering `returncode`, the address there afterwards or not.

    The system is replaced where the checker reaches it, at subprocess: a compiled setup_ips
    calls system_ips directly, so replacing system_ips in the module would be seen by the
    interpreter only, and the real loopback would be read.
    """
    reads = iter([[], [V4] if present_after else []])
    refused = subprocess.CompletedProcess([], returncode, b'', stderr)
    with (
        patch.object(healthcheck.subprocess, 'Popen', lambda cmd, **_: Listing(cmd, next(reads))),
        patch.object(healthcheck.subprocess, 'run', lambda *_, **__: refused),
    ):
        setup_ips([V4], {}, None, False)


def test_a_refused_address_stops_the_checker() -> None:
    with pytest.raises(AddressSetupError, match='Operation not permitted'):
        _setup(2, b'RTNETLINK answers: Operation not permitted\n', present_after=False)


def test_an_address_already_there_is_not_an_error() -> None:
    _setup(2, b'RTNETLINK answers: File exists\n', present_after=True)


def test_an_added_address_is_not_an_error() -> None:
    _setup(0, b'', present_after=True)
