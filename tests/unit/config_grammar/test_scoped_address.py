"""An IPv6 address with a scope (`fe80::1%en0`) is refused, on every platform.

macOS inet_pton takes the scope and writes the interface index into the address: `fe80::1%en0`
was read as `fe80:e::1`, another address, without a word. Linux refuses the scope.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_command, read_text
from exabgp.protocol.ip import IP, IPRange, IPv6

SCOPED = 'fe80::1%en0'
NEIGHBOR = (
    'neighbor {peer} {{ router-id 192.0.2.2; local-address {local}; local-as 65001; peer-as 65002; '
    'family {{ ipv6 unicast; }} capability {{ link-local-nexthop enable; }} {extra} }}'
)


def test_an_address_with_a_scope_is_not_read_as_another_address() -> None:
    for make in (lambda: IP.from_string(SCOPED), lambda: IPv6.from_string(SCOPED), lambda: IP.pton(SCOPED)):
        with pytest.raises(ValueError, match='scope'):
            make()
    with pytest.raises(ValueError, match='scope'):
        IPRange.make_range(SCOPED, 128)


def test_the_address_without_its_scope_is_read() -> None:
    assert str(IP.from_string('fe80::1')) == 'fe80::1'


@pytest.mark.parametrize(
    'peer,local,extra',
    [
        (SCOPED, 'fe80::2', ''),
        ('fe80::1', SCOPED, ''),
        ('2001:db8::1', '2001:db8::2', f'static {{ route 2001:db8:1::/48 next-hop {SCOPED}; }}'),
    ],
    ids=['peer-address', 'local-address', 'next-hop'],
)
def test_a_configured_address_with_a_scope_is_refused(peer: str, local: str, extra: str) -> None:
    with pytest.raises(ConfigError, match='scope|not a valid'):
        read_text(NEIGHBOR.format(peer=peer, local=local, extra=extra))


def test_an_api_next_hop_with_a_scope_is_refused() -> None:
    with pytest.raises(ValueError):
        read_command('ipv6', f'unicast 2001:db8:1::/48 next-hop {SCOPED}', True)
