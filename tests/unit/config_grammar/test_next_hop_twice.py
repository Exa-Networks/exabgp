"""A route given two next-hops is refused in a configuration, as any attribute given twice is.

The second was dropped without a word. An API command keeps the first and says it dropped
the other, as 4.2 and 5.0 kept the first of a repeated attribute.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.read import read_command, read_text
from exabgp.configuration.grammar.tree import static

NEIGHBOR = 'neighbor 127.0.0.2 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 1; peer-as 2; {body} }}'


@pytest.mark.parametrize(
    'body',
    [
        'static { route 10.0.0.0/24 next-hop 192.0.2.1 next-hop 192.0.2.2; }',
        'static { route 10.0.0.0/24 { next-hop 192.0.2.1; next-hop 192.0.2.2; } }',
        'announce { ipv4 { unicast 10.0.0.0/24 next-hop 192.0.2.1 next-hop 192.0.2.2; } }',
    ],
)
def test_two_next_hops_are_refused_in_a_configuration(body: str) -> None:
    with pytest.raises(ConfigError, match='next-hop is given twice'):
        read_text(NEIGHBOR.format(body=body))


def test_an_api_command_keeps_the_first_and_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(static.log, 'warning', lambda message, source='', level='WARNING': said.append(message()))
    (route,), _ = read_command('static', 'route 10.0.0.0/24 next-hop 192.0.2.1 next-hop 192.0.2.2', True)
    assert str(route.nexthop) == '192.0.2.1'
    assert said == ['api.attribute.repeated name=next-hop kept="192.0.2.1" dropped="192.0.2.2"']
