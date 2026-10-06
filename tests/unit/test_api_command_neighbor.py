"""The neighbor commands: list, show, teardown, disable and enable.

    peer list
    peer [<selector>] show [summary|extensive|configuration]
    peer <selector> teardown [<code>] [<subcode>] [<text>]
    peer <selector> disable [<text>], peer <selector> enable

and the API 4 forms, `show neighbor [<ip>] ...` and `neighbor <ip> teardown ...`. Each runs
on a real Reactor (tests/api_daemon.py) with two neighbors; tests/unit/test_api_teardown.py
covers the NOTIFICATION teardown builds from its arguments.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from exabgp.bgp.neighbor import NeighborTemplate
from tests.api_daemon import FIRST, SECOND, Daemon, answer

CEASE = 6
ADMINISTRATIVE_SHUTDOWN = 2
ADMINISTRATIVE_RESET = 4


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    yield created
    created.close()


@pytest.fixture
def text_daemon() -> Iterator[Daemon]:
    """A daemon whose helper is configured `encoder text`, for the API 4 forms."""
    created = Daemon(encoder='text')
    yield created
    created.close()


# ============================================================================== list


def test_list_names_every_neighbor_with_its_state(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    lines = daemon.send('peer list')
    assert answer(lines) == [
        [
            {'peer-address': FIRST, 'peer-as': 65001, 'state': 'IDLE'},
            {'peer-address': SECOND, 'peer-as': 65002, 'state': 'ESTABLISHED'},
        ]
    ]
    assert lines[-1] == 'done'


def test_list_gives_no_state_for_a_neighbor_with_no_peer(daemon: Daemon) -> None:
    del daemon.reactor._peers[daemon.key(SECOND)]
    (listed,) = answer(daemon.send('peer list'))
    assert listed[1] == {'peer-address': SECOND, 'peer-as': 65002, 'state': None}


# ============================================================================== show


def test_show_in_json_describes_every_neighbor(daemon: Daemon) -> None:
    lines = daemon.send('peer show')
    (shown,) = answer(lines)
    assert [entry['peer']['address'] for entry in shown] == [FIRST, SECOND]
    assert [entry['peer']['as'] for entry in shown] == [65001, 65002]
    assert shown[0]['local']['address'] == '127.0.0.100'
    assert list(shown[1]['local']['families']) == ['ipv4 unicast']
    assert lines[-1] == 'done'


def test_show_in_json_of_a_neighbor_with_no_peer_is_its_configuration(daemon: Daemon) -> None:
    del daemon.reactor._peers[daemon.key(SECOND)]
    (shown,) = answer(daemon.send('peer show'))
    assert shown[1] == {'peer-address': SECOND, 'local-address': '127.0.0.100', 'peer-as': 65002, 'local-as': 65000}


def test_show_summary_has_a_line_per_peer(text_daemon: Daemon) -> None:
    text_daemon.establish(FIRST)
    lines = text_daemon.send('show neighbor summary')
    assert lines[0] == NeighborTemplate.summary_header
    rows = [line.split() for line in lines[1:-1]]
    assert [(row[0], row[1], row[3]) for row in rows] == [(FIRST, '65001', 'established'), (SECOND, '65002', 'idle')]
    assert lines[-1] == 'done'


def test_show_summary_of_one_neighbor(text_daemon: Daemon) -> None:
    lines = text_daemon.send(f'show neighbor {FIRST} summary')
    assert [line.split()[0] for line in lines[1:-1]] == [FIRST]


def test_show_extensive_of_a_connected_peer(text_daemon: Daemon) -> None:
    text_daemon.establish(FIRST)
    lines = text_daemon.send('show neighbor extensive')
    assert lines[0] == f'Neighbor {FIRST}'
    assert any(line.split() == ['state', 'ESTABLISHED'] for line in lines)
    assert f'Neighbor {SECOND}' in lines
    assert lines[-1] == 'done'


def test_show_extensive_of_a_neighbor_with_no_peer(text_daemon: Daemon) -> None:
    del text_daemon.reactor._peers[text_daemon.key(SECOND)]
    lines = text_daemon.send('show neighbor extensive')
    start = lines.index(f'Neighbor {SECOND}')
    assert lines[start : start + 8] == [
        f'Neighbor {SECOND}',
        '',
        '    Session                         Local',
        f'    {"local-address":<20} {"127.0.0.100":>15}',
        f'    {"state":<20} down (not connected)',
        '',
        '    Setup                           Local          Remote',
        f'    {"AS":<20} {65000:>15} {65002:>15}',
    ]


def test_show_configuration_prints_the_neighbor_sections(text_daemon: Daemon) -> None:
    lines = text_daemon.send('show neighbor configuration')
    assert f'neighbor {FIRST} {{' in lines
    assert f'neighbor {SECOND} {{' in lines
    assert '  peer-as 65002;' in lines
    assert lines[-1] == 'done'


def test_show_with_no_mode_says_how_to_use_it(text_daemon: Daemon) -> None:
    assert text_daemon.send('show neighbor') == ['usage: peer <ip> show [summary|extensive|configuration]', 'done']


# ========================================================================== teardown


def test_teardown_closes_the_established_sessions_of_the_selector(daemon: Daemon) -> None:
    daemon.establish()
    assert daemon.send(f'peer {FIRST} teardown 4 maintenance') == ['done']
    notify = daemon.peer(FIRST)._teardown
    assert notify is not None
    assert (notify.code, notify.subcode) == (CEASE, ADMINISTRATIVE_RESET)
    assert daemon.peer(SECOND)._teardown is None


def test_teardown_leaves_a_session_which_is_not_established(daemon: Daemon) -> None:
    daemon.establish(SECOND)
    assert daemon.send('peer * teardown') == ['done']
    assert daemon.peer(FIRST)._teardown is None
    notify = daemon.peer(SECOND)._teardown
    assert notify is not None
    assert (notify.code, notify.subcode) == (CEASE, ADMINISTRATIVE_SHUTDOWN)


@pytest.mark.parametrize('arguments', ['300', '6 256', 'shutdown', '6 2 "unbalanced'])
def test_teardown_refuses_what_can_not_be_put_on_the_wire(daemon: Daemon, arguments: str) -> None:
    daemon.establish()
    lines = daemon.send(f'peer * teardown {arguments}')
    assert lines[-1] == 'error'
    assert lines[0].startswith('error: ')
    assert daemon.peer(FIRST)._teardown is None


def test_api_4_teardown_of_a_neighbor(text_daemon: Daemon) -> None:
    text_daemon.establish()
    assert text_daemon.send(f'neighbor {SECOND} teardown 3 1 testing') == ['done']
    notify = text_daemon.peer(SECOND)._teardown
    assert notify is not None
    assert (notify.code, notify.subcode, notify.data) == (3, 1, b'testing')
    assert text_daemon.peer(FIRST)._teardown is None


# =================================================================== disable, enable


def test_disable_keeps_a_peer_down_until_enable(daemon: Daemon) -> None:
    assert daemon.send(f'peer {SECOND} disable "back in 2h"') == ['done']
    assert daemon.peer(SECOND).disabled()
    assert not daemon.peer(FIRST).disabled()
    notify = daemon.peer(SECOND)._teardown
    assert notify is not None
    assert (notify.code, notify.subcode) == (CEASE, ADMINISTRATIVE_SHUTDOWN)
    assert notify.data == b'\x0aback in 2h'

    assert daemon.send(f'peer {SECOND} enable') == ['done']
    assert not daemon.peer(SECOND).disabled()
    # the session never acted on the disable, which is withdrawn rather than carried out later
    assert daemon.peer(SECOND)._teardown is None


def test_disable_refuses_an_unbalanced_quote(daemon: Daemon) -> None:
    assert daemon.send(f'peer {FIRST} disable "back') == ['error: No closing quotation', 'error']
    assert not daemon.peer(FIRST).disabled()


def test_enable_takes_no_argument(daemon: Daemon) -> None:
    daemon.send(f'peer {FIRST} disable')
    assert daemon.send(f'peer {FIRST} enable now')[-1] == 'error'
    assert daemon.peer(FIRST).disabled()


def test_api_4_disable_and_enable_of_a_neighbor(text_daemon: Daemon) -> None:
    assert text_daemon.send(f'neighbor {FIRST} disable') == ['done']
    assert text_daemon.peer(FIRST).disabled()
    assert text_daemon.send(f'neighbor {FIRST} enable') == ['done']
    assert not text_daemon.peer(FIRST).disabled()
