"""A neighbor which listens has an address to bind.

Reactor._listen_for_neighbors binds `session.md5_ip`, which is None until a local address
gives it. A neighbor with `listen` and no local address (none given, or `auto`) is refused
when read, so the listener never sees one. The API creates no listening neighbor: its
`neighbor` command takes no `listen` and requires a local address.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.configuration import Configuration

NEIGHBOR = """
neighbor 192.0.2.1 {
  router-id 192.0.2.2; local-as 65001; peer-as 65002; %s
  listen 1179;
}
"""


@pytest.mark.parametrize('local', ['', 'local-address auto;'])
def test_listen_without_a_local_address_is_refused(local: str) -> None:
    config = Configuration([NEIGHBOR % local], text=True)
    assert not config.reload()
    assert 'local-address required when listen is set' in str(config.error)


def test_a_listening_neighbor_has_an_address_to_bind() -> None:
    config = Configuration([NEIGHBOR % 'local-address 192.0.2.2;'], text=True)
    assert config.reload(), str(config.error)
    (neighbor,) = config.neighbors.values()
    assert neighbor.session.listen == 1179
    assert neighbor.session.md5_ip is not None and neighbor.session.md5_ip.top() == '192.0.2.2'
