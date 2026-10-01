"""`family { ipv6 multicast; }` is read, as `all` already negotiated it.

The family table had no `multicast` for ipv6, while `all`, and a neighbor with no family
block, asked for it. So a neighbor printed by `configuration validate -nrv` listed
`ipv6 multicast;`, and that text was refused when given back.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB

NEIGHBOR = """neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65000;
    peer-as 65001;
    {families}
}}"""


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def _loaded(text: str) -> Configuration:
    config = Configuration([text], text=True)
    assert config.reload(), str(config.error)
    return config


def test_ipv6_multicast_alone_is_read() -> None:
    (neighbor,) = _loaded(NEIGHBOR.format(families='family { ipv6 multicast; }')).neighbors.values()
    assert neighbor.families() == [(AFI.ipv6, SAFI.multicast)]


def test_the_printed_families_of_all_read_back() -> None:
    (neighbor,) = _loaded(NEIGHBOR.format(families='family { all; }')).neighbors.values()
    # only the family block: the rest of a printed neighbor does not all read back yet
    # (`rate-limit disable`, plan/done-config-grammar.md section 6)
    printed = str(neighbor)
    start = printed.index('family {')
    block = printed[start : printed.index('}', start) + 1]
    assert 'ipv6 multicast;' in block
    (again,) = _loaded(NEIGHBOR.format(families=block)).neighbors.values()
    assert again.families() == neighbor.families()
