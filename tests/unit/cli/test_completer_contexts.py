"""What CommandCompleter._get_completions offers in each context no other test reached.

Measured with branch coverage on 2026-09-29, the completer tests never ran the rib, system
and set sub-completions, the command tree walk (session, group, system api version), the
neighbor filters, the AFI/SAFI and route refresh hand-offs, or the multi-character
abbreviation. These pin each one, value and description, before the 570 line method is
split by context (plan-large-function-decomposition step 3).

The neighbor list is a fixed table rather than a query to a daemon: which neighbors
exist is not what is being pinned, where they are offered is.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from exabgp.cli.completer import CommandCompleter

NEIGHBORS = {'127.0.0.1': 'AS65000 up', '192.0.2.1': 'AS65001 down'}


@pytest.fixture
def completer(monkeypatch: pytest.MonkeyPatch) -> CommandCompleter:
    monkeypatch.setenv('exabgp_cli_fuzzy_matching', 'true')
    completer = CommandCompleter(Mock(return_value='[]'))
    monkeypatch.setattr(completer, '_get_neighbor_data', lambda: dict(NEIGHBORS))
    return completer


def offered(completer: CommandCompleter, tokens: list[str], text: str = '') -> dict[str, tuple[str | None, str]]:
    """What is offered, and how each offer is described, in the order offered."""
    matches = completer._get_completions(tokens, text)
    return {m: (completer.match_metadata[m].description, completer.match_metadata[m].item_type) for m in matches}


RIB_SHOW = {'in': ('Adj-RIB-In (received)', 'option'), 'out': ('Adj-RIB-Out (advertised)', 'option')}
RIB_CLEAR = {'in': ('Clear inbound RIB', 'option'), 'out': ('Clear outbound RIB', 'option')}
NEIGHBOR_IPS = {'127.0.0.1': ('AS65000 up', 'neighbor'), '192.0.2.1': ('AS65001 down', 'neighbor')}

CASES = [
    # noun-first sub-commands
    (
        ['rib'],
        '',
        {
            'clear': ('Clear RIB entries', 'command'),
            'flush': ('Flush RIB entries', 'command'),
            'show': ('Show RIB entries', 'command'),
        },
    ),
    (['rib', 'show'], '', RIB_SHOW),
    (['rib', 'flush'], '', {'out': ('Flush outbound RIB', 'option')}),
    (['rib', 'clear'], '', RIB_CLEAR),
    (['rib', 'bogus'], '', {}),
    (
        ['system'],
        '',
        {
            'api': ('API version management', 'command'),
            'crash': ('Crash daemon (debug only)', 'command'),
            'help': ('Show available commands', 'command'),
            'queue-status': ('Show write queue status', 'command'),
            'version': ('Show ExaBGP version', 'command'),
        },
    ),
    (['system', 'api'], 'v', {'version': ('Show/set API version', 'option')}),
    # CLI settings
    (
        ['set'],
        '',
        {'display': ('Set display format', 'option'), 'sync': ('Set sync mode for announce/withdraw', 'option')},
    ),
    (['set', 'display'], '', {'json': ('Show raw JSON', 'option'), 'text': ('Format as tables', 'option')}),
    (
        ['set', 'sync'],
        '',
        {'off': ('Return ACK immediately (default)', 'option'), 'on': ('Wait for routes on wire before ACK', 'option')},
    ),
    (['set', 'bogus'], '', {}),
    (['set', 'display', 'json'], '', {}),
    # show neighbor, and its shortcut
    (['show', 'neighbor'], '', NEIGHBOR_IPS),
    (['show', 'neighbor', '127.0.0.1'], '', {}),
    (['s', 'n'], '', NEIGHBOR_IPS),
    # peer actions
    (
        ['peer', '127.0.0.1', 'show'],
        '',
        {
            'configuration': ('Show configuration', 'option'),
            'extensive': ('Detailed view', 'option'),
            'summary': ('Brief summary view', 'option'),
        },
    ),
    (['peer', '127.0.0.1', 'flush'], '', {}),
    (['peer', '*', 'announce', 'route'], '', {'refresh': ('Send route refresh request', 'command')}),
    (['peer', '*', 'withdraw', 'route'], '', {}),
    (['peer', '*', 'announce', 'eor'], '', {}),
    (['peer', '*', 'announce', 'route', 'refresh'], '', {}),
    # the command tree walk
    (
        ['session', 'ack'],
        'e',
        {'enable': (None, 'command')},
    ),
    (['session', 'pi'], '', {'ping': (None, 'command')}),
    (['session', 'zz'], '', {}),
    (['system', 'api', 'version'], '', {'4': (None, 'option'), '6': (None, 'option')}),
    (['system', 'api', 'version', 'zz'], '', {'4': (None, 'option'), '6': (None, 'option')}),
    (['rib', 'show', 'in'], '', {'extensive': ('Detailed neighbor information', 'option')}),
    (['group'], '', {'end': (None, 'command'), 'start': (None, 'command')}),
    # v4 action-first commands are not offered anything
    (['announce'], '', {}),
    (['#'], '', {}),
    (['foo'], '', {}),
    # abbreviations spanning two levels
    ([], 'dst', {'daemon status': ('Expands from "dst"', 'command')}),
]


@pytest.mark.parametrize(('tokens', 'text', 'expected'), CASES, ids=[' '.join(c[0]) + f'|{c[1]}' for c in CASES])
def test_what_each_context_offers(
    completer: CommandCompleter, tokens: list[str], text: str, expected: dict[str, tuple[str | None, str]]
) -> None:
    assert offered(completer, tokens, text) == expected


def test_the_first_word_offers_its_groups_separated_by_blanks(completer: CommandCompleter) -> None:
    assert completer._get_completions([], '') == [
        'daemon',
        'peer',
        'rib',
        'system',
        '',
        'history',
        'set',
        '',
        'json',
        'text',
        '',
        'exit',
        'quit',
    ]


def test_a_display_prefix_offers_every_base_command(completer: CommandCompleter) -> None:
    assert completer._get_completions(['json'], '') == [
        'daemon',
        'exit',
        'history',
        'peer',
        'quit',
        'rib',
        'session',
        'set',
        'system',
    ]
    assert completer.match_metadata['session'].description == 'Session management (ack, sync, ping, reset, bye)'


def test_a_route_prefix_offers_the_route_attributes(completer: CommandCompleter) -> None:
    matches = completer._get_completions(['peer', '*', 'announce', 'route', '10.0.0.0/24'], '')
    assert matches[:3] == ['aigp', 'as-path', 'async']
    assert 'next-hop' in matches
    assert completer.match_metadata['next-hop'].item_type == 'keyword'


def test_a_neighbor_offers_its_filters(completer: CommandCompleter) -> None:
    assert completer._get_completions(['neighbor', '127.0.0.1'], '') == [
        'family-allowed',
        'id',
        'local-as',
        'local-ip',
        'peer-as',
    ]
    assert completer.match_metadata['peer-as'].item_type == 'keyword'


def test_an_end_of_rib_outside_a_peer_offers_the_families(completer: CommandCompleter) -> None:
    # 'group' is the one command tree root which reaches these hand-offs
    assert completer._get_completions(['group', 'eor'], '') == ['bgp-ls', 'ipv4', 'ipv6', 'l2vpn']
    assert completer.match_metadata['ipv4'].description == 'Address Family Identifier'
    assert completer._get_completions(['group', 'route', 'refresh'], '') == ['bgp-ls', 'ipv4', 'ipv6', 'l2vpn']
    safis = completer._get_completions(['group', 'ipv4', 'eor'], '')
    assert safis[:3] == ['flow', 'flow-vpn', 'labeled-unicast']
    assert completer.match_metadata['flow'].description == 'SAFI for ipv4'


def test_a_route_outside_a_peer_offers_the_route_keywords_unless_withdrawn(completer: CommandCompleter) -> None:
    for tokens in (['group', 'route'], ['group', 'ipv6']):
        matches = completer._get_completions(tokens, '')
        assert matches[:2] == ['aigp', 'as-path'] and len(matches) == 20
        assert completer.match_metadata['aigp'].description == 'Route specification parameter'
    assert completer._get_completions(['group', 'withdraw', 'route'], '') == []


def test_typing_the_options_key_walks_onto_the_options_list(completer: CommandCompleter) -> None:
    # The tree keeps a command's options under '__options__', and the walk looks every typed
    # word up in the tree, that one included. So the list branches of the walk, which no
    # command in today's tree reaches otherwise, run for it.
    options = {'4': (None, 'option'), '6': (None, 'option')}
    assert offered(completer, ['system', 'api', 'version', '__options__']) == options
    assert completer._get_completions(['rib', 'show', 'in', '__options__', 'x'], '') == ['extensive']
