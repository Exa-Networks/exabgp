"""The prefixes of `attributes ... nlri` are of one address family.

Each was made a prefix of the family of the last one: `nlri 10.0.0.0/24 2001:db8::/32` sent
a00::/24, and `nlri 2001:db8::/32 10.0.0.0/24` sent 32.1.13.184/32.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_command


@pytest.mark.parametrize('prefixes', ['10.0.0.0/24 2001:db8::/32', '2001:db8::/32 10.0.0.0/24'])
def test_prefixes_of_two_families_are_refused(prefixes: str) -> None:
    with pytest.raises(ConfigError, match='of one address family'):
        read_command('static', f'attributes next-hop 192.0.2.1 nlri {prefixes}', True)


def test_prefixes_of_one_family_are_read() -> None:
    routes, _ = read_command('static', 'attributes next-hop 192.0.2.1 nlri 10.0.0.0/24 10.0.1.0/24', True)
    assert [str(route.nlri) for route in routes] == ['10.0.0.0/24', '10.0.1.0/24']
