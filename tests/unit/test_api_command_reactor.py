"""The daemon, session and system commands: what each answers, and what it changes.

    daemon shutdown | reload | restart | status
    session ack enable | disable | silence, session sync enable | disable
    session reset | ping | bye
    system help | version | queue-status | api version [auto|4|6]

Each runs on a real Reactor and answers a helper through the real Processes (see
tests/api_daemon.py). A helper written for API 6 is answered in JSON; one written for API 4
in text, or in JSON when its command ends with `json`.
"""

from __future__ import annotations

import collections
import os
from collections.abc import Iterator

import pytest

from exabgp.environment import getenv
from exabgp.reactor.api.dispatch.version import API_AUTO, API_V4, API_V6
from exabgp.version import version
from tests.api_daemon import FIRST, HELPER, SECOND, Daemon, answer


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


@pytest.fixture
def api_version() -> Iterator[None]:
    """`system api version` changes the setting of the whole process: put it back."""
    saved = getenv().api.version
    yield
    getenv().api.version = saved


# ============================================================================ daemon


@pytest.mark.parametrize(
    ('command', 'signal', 'status'),
    [
        ('daemon shutdown', 'SHUTDOWN', 'shutdown in progress'),
        ('daemon reload', 'RELOAD', 'reload in progress'),
        ('daemon restart', 'RESTART', 'restart in progress'),
    ],
)
def test_a_daemon_command_raises_its_signal_and_says_so(daemon: Daemon, command: str, signal: str, status: str) -> None:
    lines = daemon.send(command)
    assert daemon.reactor.signal.received == getattr(daemon.reactor.signal, signal)
    assert answer(lines) == [{'status': status}]
    assert lines[-1] == 'done'


@pytest.mark.parametrize(
    ('command', 'signal', 'status'),
    [
        ('shutdown', 'SHUTDOWN', 'shutdown in progress'),
        ('reload', 'RELOAD', 'reload in progress'),
        ('restart', 'RESTART', 'restart in progress'),
    ],
)
def test_the_api_4_daemon_commands_answer_in_text(text_daemon: Daemon, command: str, signal: str, status: str) -> None:
    assert text_daemon.send(command) == [status, 'done']
    assert text_daemon.reactor.signal.received == getattr(text_daemon.reactor.signal, signal)


def test_status_reports_the_daemon_and_the_state_of_every_peer(daemon: Daemon) -> None:
    daemon.establish(FIRST)
    lines = daemon.send('daemon status')
    (status,) = answer(lines)
    assert status['version'] == version
    assert status['uuid'] == daemon.reactor.daemon_uuid
    assert status['pid'] == os.getpid()
    assert status['start_time'] == daemon.reactor.daemon_start_time
    assert status['uptime'] >= 0
    assert status['peers'] == {daemon.key(FIRST): 'ESTABLISHED', daemon.key(SECOND): 'IDLE'}
    assert lines[-1] == 'done'


def test_status_in_text_lists_the_peers(text_daemon: Daemon) -> None:
    lines = text_daemon.send('status')
    assert lines[0] == 'ExaBGP Daemon Status'
    assert f'Version: {version}' in lines
    assert f'UUID: {text_daemon.reactor.daemon_uuid}' in lines
    assert 'Peers: 2' in lines
    assert f'  - {text_daemon.key(SECOND)}: IDLE' in lines
    assert lines[-1] == 'done'


# =========================================================================== session


def test_with_ack_disabled_a_command_is_answered_with_no_done(daemon: Daemon) -> None:
    # the command turning it off is still acknowledged, so the helper is not left waiting
    assert daemon.send('session ack disable') == ['done']
    assert daemon.reactor.processes.get_ack(HELPER) is False
    assert answer(daemon.send('system version')) == [{'version': version, 'application': 'exabgp'}]
    assert daemon.send('peer * announce route 10.0.0.0/24 next-hop 1.2.3.4') == []
    assert daemon.announced(FIRST) == ['10.0.0.0/24']

    assert daemon.send('session ack enable') == ['done']
    assert daemon.reactor.processes.get_ack(HELPER) is True
    assert daemon.send('peer * announce route 10.0.1.0/24 next-hop 1.2.3.4') == ['done']


def test_silence_turns_ack_off_without_acknowledging_itself(daemon: Daemon) -> None:
    assert daemon.send('session ack silence') == []
    assert daemon.reactor.processes.get_ack(HELPER) is False


def test_sync_is_set_for_the_helper_which_asks(daemon: Daemon) -> None:
    assert daemon.reactor.processes.get_sync(HELPER) is False
    assert daemon.send('session sync enable') == ['done']
    assert daemon.reactor.processes.get_sync(HELPER) is True
    assert daemon.send('session sync disable') == ['done']
    assert daemon.reactor.processes.get_sync(HELPER) is False


def test_reset_drops_the_commands_of_the_helper_not_yet_run(daemon: Daemon) -> None:
    # written, scheduled, and not yet given its turn by the reactor
    daemon.reactor.api.process(daemon.reactor, HELPER, 'peer * announce route 10.0.0.0/24 next-hop 1.2.3.4')
    lines = daemon.send('session reset')
    assert answer(lines) == [{'status': 'asynchronous queue cleared'}]
    assert lines[-1] == 'done'
    assert daemon.announced(FIRST) == []


def test_reset_leaves_the_commands_of_another_helper(daemon: Daemon) -> None:
    async def other() -> None:
        ran.append(True)

    ran: list[bool] = []
    daemon.reactor.asynchronous.schedule('another-helper', 'its command', other())
    daemon.send('session reset')
    assert ran == [True]


def test_ping_answers_the_uuid_of_the_daemon(daemon: Daemon) -> None:
    lines = daemon.send('session ping')
    assert answer(lines) == [{'pong': daemon.reactor.daemon_uuid, 'active': True}]
    assert lines[-1] == 'done'


def test_ping_takes_the_arguments_the_cli_sends_and_answers_text_when_asked(daemon: Daemon) -> None:
    uuid = daemon.reactor.daemon_uuid
    assert daemon.send('session ping 0f1e2d3c 1700000000 text') == [f'pong {uuid} active=true', 'done']


def test_bye_is_acknowledged(daemon: Daemon) -> None:
    assert daemon.send('session bye') == ['done']


def test_a_comment_is_acknowledged_and_does_nothing(daemon: Daemon) -> None:
    assert daemon.send('# announce route 10.0.0.0/24 next-hop 1.2.3.4') == ['done']
    assert daemon.announced(FIRST) == []


# ============================================================================ system


def test_version(daemon: Daemon) -> None:
    assert daemon.send('system version') == [f'{{"version": "{version}", "application": "exabgp"}}', 'done']


def test_version_in_text_and_in_json_for_an_api_4_helper(text_daemon: Daemon) -> None:
    assert text_daemon.send('version') == [f'exabgp {version}', 'done']
    assert answer(text_daemon.send('version json')) == [{'version': version, 'application': 'exabgp'}]


def test_help_lists_every_command_the_dispatcher_takes(daemon: Daemon) -> None:
    from exabgp.reactor.api.dispatch.common import get_commands

    lines = daemon.send('system help')
    (listing,) = answer(lines)
    assert [entry['command'] for entry in listing['commands']] == sorted(name for name, _, _ in get_commands())
    by_name = {entry['command']: entry for entry in listing['commands']}
    assert by_name['peer announce route']['neighbor_support'] is True
    assert by_name['daemon shutdown']['neighbor_support'] is False
    assert by_name['system api version']['options'] == ['auto', '4', '6']
    assert lines[-1] == 'done'


def test_help_in_text_prefixes_the_commands_taking_a_selector(text_daemon: Daemon) -> None:
    lines = text_daemon.send('help')
    assert 'available API commands (v6 format):' in lines
    assert '[peer <ip> [filters]] peer announce route' in lines
    assert 'daemon shutdown ' in lines
    assert 'rib show in [ extensive ] ' in lines
    assert lines[-1] == 'done'


def test_queue_status_with_nothing_queued(daemon: Daemon, text_daemon: Daemon) -> None:
    assert daemon.send('system queue-status') == ['{}', 'done']
    assert text_daemon.send('queue-status') == ['no queued messages', 'done']


def test_queue_status_counts_what_waits_for_each_helper(daemon: Daemon) -> None:
    daemon.reactor.processes._write_queue['slow-helper'] = collections.deque([b'one\n', b'three\n'])
    assert answer(daemon.send('system queue-status')) == [{'slow-helper': {'items': 2, 'bytes': 10}}]


def test_queue_status_in_text(text_daemon: Daemon) -> None:
    text_daemon.reactor.processes._write_queue['slow-helper'] = collections.deque([b'one\n'])
    assert text_daemon.send('queue-status') == ['slow-helper: 1 items (4 bytes)', 'done']


def test_api_version_shows_the_setting_and_the_version_of_this_helper(daemon: Daemon, api_version: None) -> None:
    getenv().api.version = API_AUTO
    lines = daemon.send('system api version')
    assert answer(lines) == [{'api_version': 'auto', 'helper_api_version': '6'}]
    assert lines[-1] == 'done'


def test_api_version_of_an_api_4_helper_in_text(text_daemon: Daemon, api_version: None) -> None:
    getenv().api.version = API_AUTO
    assert text_daemon.send('api version') == ['API version: auto (this helper: 4)', 'done']


@pytest.mark.parametrize(
    ('given', 'setting', 'name'), [('4', API_V4, '4'), ('6', API_V6, '6'), ('auto', API_AUTO, 'auto')]
)
def test_api_version_sets_the_version_of_the_helpers_started_next(
    daemon: Daemon, api_version: None, given: str, setting: int, name: str
) -> None:
    lines = daemon.send(f'system api version {given}')
    assert getenv().api.version == setting
    assert answer(lines) == [
        {'status': 'API version set', 'version': name, 'note': 'effective for helpers started afterwards'}
    ]
    assert lines[-1] == 'done'
    # this helper keeps the version it was detected with
    assert daemon.reactor.processes.api_version(HELPER) == API_V6


@pytest.mark.parametrize('given', ['5', '7', 'six', '-4'])
def test_api_version_refuses_a_version_which_does_not_exist(daemon: Daemon, api_version: None, given: str) -> None:
    before = getenv().api.version
    lines = daemon.send(f'system api version {given}')
    assert getenv().api.version == before
    (refusal,) = answer(lines)
    assert given in refusal['error']
    assert lines[-1] == 'error'


def test_api_version_refusal_in_text(text_daemon: Daemon, api_version: None) -> None:
    assert text_daemon.send('api version 9') == ['error: API version must be auto, 4 or 6, got 9', 'error']


def test_an_unknown_command_is_answered_error(daemon: Daemon) -> None:
    assert daemon.send('system reboot') == ['error']
    assert daemon.send('daemon') == ['error']
