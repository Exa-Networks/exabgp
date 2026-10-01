"""A word a value does not use is refused, not ignored.

The configuration took the words a value needed and ignored the rest, so
`md5-password include "secret";` set the MD5 password to `include`, and the session was
signed with a key the operator never wrote. Nothing said so.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB

NEIGHBOR = """neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65000;
    peer-as 65001;
    {statement}
}}"""


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def _loaded(statement: str) -> Configuration:
    config = Configuration([NEIGHBOR.format(statement=statement)], text=True)
    config.reload()
    return config


def test_a_second_word_after_the_md5_password_is_refused() -> None:
    config = _loaded('md5-password include "secret";')
    assert not config.neighbors
    assert "'secret' follows the value of md5-password" in str(config.error)


def test_the_md5_password_alone_is_read() -> None:
    config = _loaded('md5-password "secret";')
    (neighbor,) = config.neighbors.values()
    assert neighbor.session.md5_password == 'secret'
