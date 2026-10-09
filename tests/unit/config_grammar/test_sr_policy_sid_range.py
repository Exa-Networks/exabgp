"""The MPLS SID of every segment type is a label of 20 bits.

The range was checked for the types c, d and e only: f, g and h took any number.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_command

POLICY = (
    'sr-policy distinguisher 0 color 100 endpoint 10.0.0.1 next-hop 192.0.2.1 preference 100 '
    'segment-list weight 1 segment {segment} sid {sid} extended-community [ target:192.0.2.1:100 ]'
)
SEGMENTS = [
    'type-f local 10.0.0.1 remote 10.0.0.2',
    'type-g local-if-id 1 local-ipv6 fc00::1 remote-if-id 2 remote-ipv6 fc00::2',
    'type-h local fc00::1 remote fc00::2',
]


@pytest.mark.parametrize('segment', SEGMENTS)
def test_a_label_of_more_than_20_bits_is_refused(segment: str) -> None:
    with pytest.raises(ConfigError, match='MPLS SID 1048576 out of range'):
        read_command('ipv4', POLICY.format(segment=segment, sid=1048576), True)


@pytest.mark.parametrize('segment', SEGMENTS)
def test_the_largest_label_is_read(segment: str) -> None:
    (route,), _ = read_command('ipv4', POLICY.format(segment=segment, sid=1048575), True)
    assert route
