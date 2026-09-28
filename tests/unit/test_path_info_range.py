"""An ADD-PATH path identifier is four octets: a larger number is refused, not wrapped.

make_from_integer kept the low 32 bits: `path-information 4294967296` was path 0, and
4294967301 was path 5, without a word to the operator.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.configuration.configuration import Configuration

NEIGHBOR = (
    'neighbor 127.0.0.1 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; '
    'family {{ ipv4 unicast; }} capability {{ add-path send; }} '
    'static {{ route 10.0.0.0/24 next-hop 10.0.0.1 path-information {path}; }} }}'
)


def test_the_largest_path_identifier_is_kept() -> None:
    assert bytes(PathInfo.make_from_integer(PathInfo.MAX).pack_path()) == b'\xff\xff\xff\xff'


@pytest.mark.parametrize('integer', [PathInfo.MAX + 1, PathInfo.MAX + 6, -1])
def test_a_path_identifier_which_does_not_fit_is_refused(integer: int) -> None:
    with pytest.raises(ValueError):
        PathInfo.make_from_integer(integer)


def test_the_configuration_refuses_it() -> None:
    assert Configuration([NEIGHBOR.format(path=PathInfo.MAX)], text=True).reload()
    assert not Configuration([NEIGHBOR.format(path=PathInfo.MAX + 1)], text=True).reload()
