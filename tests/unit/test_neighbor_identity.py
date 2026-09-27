"""test_neighbor_identity.py

A neighbour is identified by its whole session, not by the peer address alone.
One exabgp can open several sessions to the same router, each from its own
local address or AS, which is how a large IXP route server gets tested from a
single process (issue #760). Only a definition identical in every field that
names the session is a duplicate.

License: 3-clause BSD
"""

from __future__ import annotations

from typing import Any

import pytest

from exabgp.configuration.configuration import Configuration


def _parse(cfg: str) -> tuple[bool, Configuration]:
    c = Configuration([cfg], text=True)
    ok = c.reload()
    return ok, c


def _neighbor(
    local: str = '192.0.2.2',
    local_as: int = 65001,
    peer_as: int = 65000,
    router_id: str = '10.0.0.2',
    listen: int = 0,
) -> str:
    port = f'    listen {listen};\n' if listen else ''
    return f"""neighbor 192.0.2.1 {{
    router-id {router_id};
    local-address {local};
    local-as {local_as};
    peer-as {peer_as};
{port}}}"""


# ==============================================================================
# The same peer address, several sessions
# ==============================================================================


@pytest.mark.parametrize(
    'other',
    [
        {'local': '192.0.2.3'},
        {'local_as': 65002},
        {'peer_as': 65003},
        {'router_id': '10.0.0.3'},
        {'local': '192.0.2.3', 'local_as': 65002},
    ],
)
def test_one_peer_address_may_carry_several_sessions(other: dict[str, Any]) -> None:
    ok, c = _parse(_neighbor() + '\n' + _neighbor(**other))

    assert ok, c.error
    assert len(c.neighbors) == 2


def test_the_same_session_twice_is_a_duplicate() -> None:
    ok, c = _parse(_neighbor() + '\n' + _neighbor())

    assert not ok
    assert 'duplicate peer definition 192.0.2.1' in str(c.error)


def test_two_listeners_on_one_address_and_port_are_a_duplicate() -> None:
    # Only one of them could accept the incoming connection, whatever their AS
    ok, c = _parse(_neighbor(listen=1790) + '\n' + _neighbor(local_as=65002, listen=1790))

    assert not ok
    assert 'duplicate peer definition 192.0.2.1' in str(c.error)
