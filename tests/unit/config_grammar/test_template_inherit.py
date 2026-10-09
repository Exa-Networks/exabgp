"""Templates: what one neighbor inherits does not leak into another, and a template may inherit.

A template gives defaults: what the neighbor says itself wins, and so does what a template
listed first says over one listed after it, as a template's own values over those of the
templates it inherits. The template won over the neighbor, so `hold-time 30;` in a neighbor
inheriting a template with `hold-time 60;` was 60. Lists (routes, families) add up.

A list a neighbor took whole from a template was the template's own, and the next template
the neighbor inherited extended it in place: every other neighbor inheriting the first
template was given the routes of the second. `inherit` inside a template was ignored.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.tree import resolve
from exabgp.configuration.grammar.read import read_text
from exabgp.configuration.grammar.tree.resolve import MAX_INHERIT_DEPTH

NEIGHBOR = (
    'neighbor {peer} {{ inherit {inherit}; router-id 10.0.0.1; local-address 127.0.0.1; '
    'local-as 65001; peer-as 65002; }} '
)
OWN = (
    'neighbor 127.0.0.2 {{ inherit {inherit}; router-id 10.0.0.1; local-address 127.0.0.1; '
    'local-as 65001; peer-as 65002; {own} }} '
)


def _template(name: str, body: str) -> str:
    return f'template {{ neighbor {name} {{ {body} }} }} '


def _route(prefix: str) -> str:
    return f'static {{ route {prefix} next-hop 10.0.0.1; }}'


def _routes(text: str) -> dict[str, list[str]]:
    return {
        str(neighbor.session.peer_address): sorted(str(route.nlri) for route in neighbor.routes)
        for neighbor in read_text(text).neighbors
    }


def test_a_template_list_is_not_extended_for_another_neighbor() -> None:
    text = (
        _template('a', _route('10.0.0.0/24'))
        + _template('b', _route('10.0.1.0/24'))
        + NEIGHBOR.format(peer='127.0.0.2', inherit='[ a b ]')
        + NEIGHBOR.format(peer='127.0.0.3', inherit='a')
    )
    found = _routes(text)
    assert found['127.0.0.2'] == ['10.0.0.0/24', '10.0.1.0/24']
    assert found['127.0.0.3'] == ['10.0.0.0/24']


def test_a_template_section_is_not_changed_for_another_neighbor() -> None:
    text = (
        _template('a', 'family { ipv4 unicast; }')
        + _template('b', 'family { ipv6 unicast; }')
        + NEIGHBOR.format(peer='127.0.0.2', inherit='[ a b ]')
        + NEIGHBOR.format(peer='127.0.0.3', inherit='a')
    )
    families = {str(neighbor.session.peer_address): neighbor.families for neighbor in read_text(text).neighbors}
    assert len(families['127.0.0.2']) == 2
    assert len(families['127.0.0.3']) == 1


def test_a_template_inherits_another() -> None:
    text = (
        _template('base', 'hold-time 60; ' + _route('10.0.0.0/24'))
        + _template('child', 'inherit base; ' + _route('10.0.1.0/24'))
        + NEIGHBOR.format(peer='127.0.0.2', inherit='child')
    )
    neighbor = read_text(text).neighbors[0]
    assert neighbor.hold_time == 60
    assert sorted(str(route.nlri) for route in neighbor.routes) == ['10.0.0.0/24', '10.0.1.0/24']


def test_a_template_wins_over_the_one_it_inherits() -> None:
    text = (
        _template('base', 'hold-time 60;')
        + _template('child', 'inherit base; hold-time 90;')
        + NEIGHBOR.format(peer='127.0.0.2', inherit='child')
    )
    assert read_text(text).neighbors[0].hold_time == 90


def test_a_template_inherited_twice_is_merged_once() -> None:
    text = (
        _template('base', _route('10.0.0.0/24'))
        + _template('left', 'inherit base;')
        + _template('right', 'inherit base;')
        + NEIGHBOR.format(peer='127.0.0.2', inherit='[ left right ]')
    )
    assert _routes(text)['127.0.0.2'] == ['10.0.0.0/24']


def test_a_template_inheriting_itself_is_refused() -> None:
    text = _template('a', 'inherit b;') + _template('b', 'inherit a;') + NEIGHBOR.format(peer='127.0.0.2', inherit='a')
    with pytest.raises(ConfigError, match='inherits itself'):
        read_text(text)


def test_templates_inheriting_too_deep_are_refused() -> None:
    names = [f't{index}' for index in range(MAX_INHERIT_DEPTH + 1)]
    text = ''.join(_template(name, f'inherit {parent};') for name, parent in zip(names, names[1:]))
    text += _template(names[-1], 'hold-time 60;')
    with pytest.raises(ConfigError, match='more than'):
        read_text(text + NEIGHBOR.format(peer='127.0.0.2', inherit=names[0]))


def test_templates_inheriting_as_deep_as_allowed_are_read() -> None:
    names = [f't{index}' for index in range(MAX_INHERIT_DEPTH)]
    text = ''.join(_template(name, f'inherit {parent};') for name, parent in zip(names, names[1:]))
    text += _template(names[-1], 'hold-time 60;')
    assert read_text(text + NEIGHBOR.format(peer='127.0.0.2', inherit=names[0])).neighbors[0].hold_time == 60


def test_the_neighbor_wins_over_its_template() -> None:
    text = _template('t', 'hold-time 60; description "template";')
    neighbor = read_text(text + OWN.format(inherit='t', own='hold-time 30;')).neighbors[0]
    assert neighbor.hold_time == 30
    # what the neighbor leaves out still comes from the template
    assert neighbor.description == 'template'


def test_the_neighbor_wins_whatever_the_order_of_its_statements() -> None:
    text = _template('t', 'hold-time 60;')
    own = 'neighbor 127.0.0.2 { hold-time 30; inherit t; router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; } '
    assert read_text(text + own).neighbors[0].hold_time == 30


def test_the_template_listed_first_wins() -> None:
    text = _template('a', 'hold-time 60;') + _template('b', 'hold-time 90;')
    assert read_text(text + NEIGHBOR.format(peer='127.0.0.2', inherit='[ a b ]')).neighbors[0].hold_time == 60
    assert read_text(text + NEIGHBOR.format(peer='127.0.0.2', inherit='[ b a ]')).neighbors[0].hold_time == 90


def test_a_section_takes_the_neighbor_values_and_the_template_others() -> None:
    text = _template('t', 'capability { route-refresh enable; graceful-restart 60; }')
    own = 'capability { graceful-restart 120; }'
    capability = read_text(text + OWN.format(inherit='t', own=own)).neighbors[0].capability
    assert capability.graceful_restart.time == 120
    assert capability.route_refresh


def test_a_neighbor_address_wins_over_the_template() -> None:
    text = _template('t', 'local-address 127.0.0.9; router-id 10.9.9.9;')
    own = (
        'neighbor 127.0.0.2 { inherit t; router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; } '
    )
    neighbor = read_text(text + own).neighbors[0]
    assert str(neighbor.session.local_address) == '127.0.0.1'
    assert str(neighbor.session.router_id) == '10.0.0.1'


def test_a_template_written_after_the_neighbor_is_inherited() -> None:
    """A neighbor was made from the templates read before it, and given nothing from this one."""
    text = NEIGHBOR.format(peer='127.0.0.2', inherit='t') + _template('t', 'hold-time 60;')
    assert read_text(text).neighbors[0].hold_time == 60


def test_inheriting_a_template_which_does_not_exist_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    said: list[str] = []
    monkeypatch.setattr(resolve.log, 'warning', lambda message, source='', level='WARNING': said.append(message()))
    neighbor = read_text(NEIGHBOR.format(peer='127.0.0.2', inherit='nothing')).neighbors[0]
    assert neighbor.hold_time == 180
    assert said == ['inherit nothing: no template has this name, nothing is inherited']


def test_a_comma_between_template_names_is_no_template(monkeypatch: pytest.MonkeyPatch) -> None:
    """The comma of `[ t, u ]` was a name: inherited as a template no one wrote, and warned about."""
    said: list[str] = []
    monkeypatch.setattr(resolve.log, 'warning', lambda message, source='', level='WARNING': said.append(message()))
    text = _template('t', 'hold-time 60;') + _template('u', 'description "u";')
    neighbor = read_text(text + NEIGHBOR.format(peer='127.0.0.2', inherit='[ t, u ]')).neighbors[0]
    assert (neighbor.hold_time, neighbor.description, said) == (60, 'u', [])
