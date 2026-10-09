"""A boolean keyword given alone is true, the way `respawn;` and `passive;` always were.

Each boolean had its own value when given no word, the default of the statement, so
`adj-rib-in;`, `shutdown;`, `software-version;` or `base64;` read as false, and
`link-local-nexthop;` was refused.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.read import read_text
from exabgp.util.enumeration import TriState

NEIGHBOR = 'neighbor 127.0.0.2 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; {body} }}'


def _neighbor(body: str):
    return read_text(NEIGHBOR.format(body=body)).neighbors[0]


@pytest.mark.parametrize('keyword', ['adj-rib-in', 'adj-rib-out', 'manual-eor', 'shutdown'])
def test_a_neighbor_boolean_alone_is_true(keyword: str) -> None:
    assert getattr(_neighbor(f'{keyword};'), keyword.replace('-', '_')) is True


def test_a_capability_alone_is_enabled() -> None:
    capability = _neighbor('capability { software-version; link-local-nexthop; link-local-prefer; }').capability
    assert capability.software_version is not None
    assert capability.link_local_nexthop == TriState.TRUE
    assert capability.link_local_prefer is True


def test_base64_alone_reads_the_password_as_base64() -> None:
    tcp_ao = 'tcp-ao { keyid 1; algorithm hmac-sha-256; password c2VjcmV0; base64; }'
    assert _neighbor(tcp_ao).session.tcp_ao_base64 is True
