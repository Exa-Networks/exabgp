"""A route statement prints words which read back, or refuses to print.

`exabgp decode --command` prints the routes of a decoded UPDATE, which hold what the wire
carried, not what a statement read: a mup route carries the ORIGIN every UPDATE has, which no
mup statement reads. It was printed, `mup ... origin igp`, and the command was refused.

The communities of a flow route were printed as words, the brackets with them, so the line
read `community "[" 1:1 2:2 "]"`: it read back, quoted where nothing needs quoting.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.update.attribute import Origin
from exabgp.configuration.grammar.read import read_command
from exabgp.configuration.grammar.render import quote
from exabgp.configuration.grammar.tree.announce import IPV4
from exabgp.configuration.grammar.tree.static import Unprintable

MUP = 'mup mup-t1st 192.168.0.1/32 rd 100:100 teid 12345 qfi 9 endpoint 10.0.0.1 next-hop 10.0.0.2'
FLOW = 'flow destination-ipv4 10.0.0.2/32 source-ipv4 10.0.0.1/32 community [ 1:1 2:2 ]'


def _printed(line: str, keyword: str) -> str:
    (route,), _ = read_command('ipv4', line, True)
    return ' '.join(quote(word) for word in IPV4.leaf(keyword).type.printed(route))


def test_a_mup_route_prints_what_it_read() -> None:
    printed = _printed(f'{MUP} extended-community [ target:10:10 ]', 'mup')
    (again,), _ = read_command('ipv4', f'mup {printed}', True)
    (route,), _ = read_command('ipv4', f'{MUP} extended-community [ target:10:10 ]', True)
    assert again == route


def test_a_mup_route_holding_an_attribute_no_mup_statement_reads_is_not_printed() -> None:
    (route,), _ = read_command('ipv4', MUP, True)
    route.attributes.add(Origin.from_int(Origin.IGP))
    with pytest.raises(Unprintable, match='origin'):
        IPV4.leaf('mup').type.printed(route)


def test_the_brackets_of_flow_communities_are_not_quoted() -> None:
    printed = _printed(FLOW, 'flow')
    assert 'community [ 1:1 2:2 ]' in printed, printed
    assert '"' not in printed
    (again,), _ = read_command('ipv4', f'flow {printed}', True)
    (route,), _ = read_command('ipv4', FLOW, True)
    assert again == route
