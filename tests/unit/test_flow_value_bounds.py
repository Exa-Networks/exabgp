"""A flow match value the component cannot hold is refused where it is written.

The protocol, next header, ICMP type and ICMP code are one octet of the packet header, and
the grammar took any number for them: the route parsed and then failed when it was packed
for a peer, out of reach of the configuration line which caused it. The IPv6 traffic class
was bounded at 65535, where RFC 8956 3 makes type 11 for IPv6 the RFC 8955 DSCP, six bits.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.configuration import Configuration

IPV4 = 'route {{ match {{ destination 10.0.0.0/24; {match}; }} then {{ discard; }} }}'
IPV6 = 'route {{ match {{ destination 2001:db8::/32; {match}; }} then {{ discard; }} }}'

COMPONENTS = [
    (IPV4, 'protocol', 255),
    (IPV4, 'icmp-type', 255),
    (IPV4, 'icmp-code', 255),
    (IPV6, 'next-header', 255),
    (IPV6, 'traffic-class', 63),
    (IPV4, 'tcp-flags', 0x0FFF),
]


def parses(template: str, match: str) -> bool:
    return Configuration([''], text=True).partial('flow', template.format(match=match), 'announce')


@pytest.mark.parametrize('template,keyword,maximum', COMPONENTS, ids=[keyword for _, keyword, _ in COMPONENTS])
def test_the_largest_value_a_component_holds_is_accepted(template: str, keyword: str, maximum: int) -> None:
    assert parses(template, f'{keyword} ={maximum}')


@pytest.mark.parametrize('template,keyword,maximum', COMPONENTS, ids=[keyword for _, keyword, _ in COMPONENTS])
def test_one_more_than_a_component_holds_is_refused(template: str, keyword: str, maximum: int) -> None:
    assert not parses(template, f'{keyword} ={maximum + 1}')
