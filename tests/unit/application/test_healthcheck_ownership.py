"""The checker sets up each --ip once, takes off only what it put on, and sends path-id 0.

- setup_ips() expanded each --ip into every address of the prefix, one `ip address add`
  each: 16 million for a /8, and an IPv6 /64 never finished
- on exit, remove_ips() deleted every configured address it found, so an address which was
  on the box before the checker started went with it when no label told them apart
- `--path-id 0` was tested for truth, and 0 is a valid Path Identifier

No root needed: the system is replaced by recorders.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from io import StringIO
from ipaddress import IPv4Network, IPv6Network, ip_network
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.application import healthcheck
from exabgp.application.healthcheck import loop, setup_ips

Network = IPv4Network | IPv6Network


REAL_POPEN = subprocess.Popen


class Listing:
    """What `ip -o address show` or `ifconfig` prints for the addresses given."""

    def __init__(self, cmd: list[str], addresses: list[Network]) -> None:
        if cmd[0] == 'ip':
            self.stdout = [f'1: lo    inet{family(a)} {a} scope global lo\n'.encode() for a in addresses]
        else:
            self.stdout = [f'inet{family(a)} {a.network_address} prefixlen {a.prefixlen}\n'.encode() for a in addresses]


def family(address: Network) -> str:
    return '6' if address.version == 6 else ''


class FakeSystem:
    """The addresses on the box, and the commands run against them.

    Replaced where the checker reaches the system, at subprocess: a compiled setup_ips and
    remove_ips call system_ips directly, so replacing system_ips in the module would be seen
    by the interpreter only, and the real loopback would be read.
    """

    def __init__(self, present: list[Network]) -> None:
        self.present = set(present)
        self.added: list[str] = []
        self.deleted: list[str] = []

    def popen(self, cmd: Any, **kwargs: Any) -> Any:
        # the addresses are listed by the fake, the health check command itself still runs
        if cmd[0] in ('ip', 'ifconfig'):
            return Listing(cmd, sorted(self.present, key=str))
        return REAL_POPEN(cmd, **kwargs)

    def _apply(self, cmd: list[str]) -> None:
        address = ip_network(next(word for word in cmd if '/' in word))
        if 'add' in cmd or 'alias' in cmd:
            self.added.append(str(address))
            self.present.add(address)
        else:
            self.deleted.append(str(address))
            self.present.discard(address)

    def run(self, cmd: list[str], **_: Any) -> subprocess.CompletedProcess[bytes]:
        self._apply(cmd)
        return subprocess.CompletedProcess(cmd, 0, b'', b'')

    def check_call(self, cmd: list[str], **_: Any) -> int:
        self._apply(cmd)
        return 0


@pytest.fixture
def system() -> Any:
    def make(present: list[Network]) -> FakeSystem:
        fake = FakeSystem(present)
        patches = [
            patch.object(healthcheck.subprocess, 'Popen', fake.popen),
            patch.object(healthcheck.subprocess, 'run', fake.run),
            patch.object(healthcheck.subprocess, 'check_call', fake.check_call),
        ]
        for one in patches:
            one.start()
            stack.append(one)
        return fake

    stack: list[Any] = []
    yield make
    for one in stack:
        one.stop()


def test_a_prefix_is_set_up_as_one_address(system: Any) -> None:
    fake = system([])
    added = setup_ips([ip_network('192.0.2.0/29'), ip_network('2001:db8::/126')], {}, None, False)
    assert sorted(fake.added) == ['192.0.2.0/29', '2001:db8::/126']
    assert added == {ip_network('192.0.2.0/29'), ip_network('2001:db8::/126')}


def _options(**overrides: object) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    healthcheck.setargs(parser)
    options = parser.parse_args(['--command', 'true', '--rise', '1', '--no-ack', '--interval', '1'])
    options.ip_ifnames = {}  # parse() turns the IP%IFNAME list into a mapping
    for key, value in overrides.items():
        setattr(options, key, value)
    return options


def _run_until_exit(options: argparse.Namespace) -> list[str]:
    captured = StringIO()
    with (
        patch.object(sys, 'stdout', captured),
        patch('signal.signal'),
        patch.object(healthcheck.time, 'sleep', side_effect=KeyboardInterrupt),
    ):
        loop(options)
    return [line for line in captured.getvalue().splitlines() if line]


def test_on_exit_only_the_addresses_it_added_are_removed(system: Any) -> None:
    before = ip_network('192.0.2.1/32')
    ours = ip_network('192.0.2.2/32')
    fake = system([before])
    options = _options(ips=[before, ours])
    options.ips_added = setup_ips(options.ips, {}, None, False)
    _run_until_exit(options)
    assert fake.added == ['192.0.2.2/32']
    assert fake.deleted == ['192.0.2.2/32']
    assert before in fake.present


def test_path_id_zero_is_sent(system: Any) -> None:
    system([])
    options = _options(ips=[ip_network('192.0.2.1/32')], path_id=0, ip_setup=False)
    commands = _run_until_exit(options)
    announces = [command for command in commands if ' announce ' in command]
    assert announces
    assert all(command.endswith('path-information 0') for command in announces)
