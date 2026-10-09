"""`add-path { all; }` negotiates ADD-PATH for every family the neighbor does, as `family { all; }` is every family.

It negotiated it for none. The one way left to get ADD-PATH for no family with the capability
on, an add-path block naming only families the neighbor does not negotiate, reads as the
capability off, which is what the session does.
"""

from __future__ import annotations

from exabgp.configuration.grammar.read import read_text
from exabgp.protocol.family import AFI, SAFI

NEIGHBOR = (
    'neighbor 127.0.0.2 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; '
    'family {{ ipv4 unicast; ipv6 unicast; }} capability {{ add-path send/receive; }} {body} }}'
)


def _neighbor(body: str):
    return read_text(NEIGHBOR.format(body=body)).neighbors[0]


def test_add_path_all_is_every_family_negotiated() -> None:
    neighbor = _neighbor('add-path { all; }')
    assert neighbor.addpaths == [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)]
    assert neighbor.capability.add_path


def test_add_path_for_no_negotiated_family_is_off() -> None:
    neighbor = _neighbor('add-path { ipv4 flow; }')
    assert neighbor.addpaths == []
    assert not neighbor.capability.add_path
