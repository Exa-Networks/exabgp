"""A reload re-establishes a neighbor whose session settings changed: Neighbor.__eq__ sees each one.

The reactor compares the neighbor of the new configuration with the running one, and only an
unequal one is re-established. md5-base64, TCP-AO, add-path and the nexthop block were not
compared, so changing them on reload kept the old session with the old settings. prefix-limit is
left out on purpose (tests/unit/rfc/test_rfc4486_prefix_limit.py): the running session takes it.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.grammar.read import read_text

NEIGHBOR = (
    'neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; '
    'family {{ ipv4 unicast; ipv6 unicast; }} {extra} }}'
)

BEFORE_AFTER = {
    'md5-base64': ('md5-password "c2VjcmV0"; md5-base64 false;', 'md5-password "c2VjcmV0"; md5-base64 true;'),
    'tcp-ao password': (
        'tcp-ao { keyid 1; algorithm hmac-sha-1-96; password secret; }',
        'tcp-ao { keyid 1; algorithm hmac-sha-1-96; password other; }',
    ),
    'tcp-ao keyid': (
        'tcp-ao { keyid 1; algorithm hmac-sha-1-96; password secret; }',
        'tcp-ao { keyid 2; algorithm hmac-sha-1-96; password secret; }',
    ),
    # the capability is on in both, only the families it is advertised for change
    'add-path': (
        'capability { add-path send/receive; } add-path { ipv6 unicast; }',
        'capability { add-path send/receive; } add-path { ipv4 unicast; }',
    ),
    'nexthop': ('nexthop { ipv6 unicast ipv4; }', 'nexthop { ipv4 unicast ipv6; }'),
}


def _neighbor(extra: str) -> Neighbor:
    settings = read_text(NEIGHBOR.format(extra=extra))
    return Neighbor.from_settings(settings.neighbors[0], rib=False)


@pytest.mark.parametrize('before,after', BEFORE_AFTER.values(), ids=BEFORE_AFTER.keys())
def test_a_changed_setting_makes_the_neighbor_unequal(before: str, after: str) -> None:
    assert _neighbor(before) == _neighbor(before)
    assert _neighbor(before) != _neighbor(after)
