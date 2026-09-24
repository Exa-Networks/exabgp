"""A failed neighbour lookup must not be remembered as an answer.

CommandCompleter caches the neighbour addresses it offers for five minutes.  It used to
cache whatever it ended up with, and a query which raised or which the daemon refused
ended up with an empty list, so one unlucky TAB left the completer offering no neighbours
at all for the next three hundred seconds, long after the daemon was answering again.

Created by Thomas Mangin on 2026-09-24.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.cli.completer import CommandCompleter


def _no_daemon(command: str) -> str:
    raise AssertionError(f'the completer should not have sent {command!r}')


def test_a_raising_callback_is_not_cached_as_an_empty_neighbour_list() -> None:
    attempts: list[int] = []

    def get_neighbors() -> list[str]:
        attempts.append(len(attempts))
        if len(attempts) == 1:
            raise OSError('connection reset by peer')
        return ['10.0.0.1', '10.0.0.2']

    completer = CommandCompleter(send_command=_no_daemon, get_neighbors=get_neighbors)

    assert completer._get_neighbor_ips() == []
    # The second TAB is within the cache timeout: it must still ask, because the first
    # answer was a failure and not a fact.
    assert completer._get_neighbor_ips() == ['10.0.0.1', '10.0.0.2']
    assert len(attempts) == 2


def test_a_refused_daemon_reply_is_not_cached_as_an_empty_neighbour_list() -> None:
    replies = ['Error: unknown command', '[{"peer-address": "10.0.0.1"}]']

    def send_command(command: str) -> str:
        assert command == 'show neighbor json'
        return replies.pop(0)

    completer = CommandCompleter(send_command=send_command)

    assert completer._get_neighbor_ips() == []
    assert completer._get_neighbor_ips() == ['10.0.0.1']
    assert replies == []


def test_unparsable_json_is_not_cached_as_an_empty_neighbour_list() -> None:
    replies = ['{ this is not json', '[{"peer-address": "10.0.0.1"}]']

    def send_command(command: str) -> str:
        return replies.pop(0)

    completer = CommandCompleter(send_command=send_command)

    assert completer._get_neighbor_ips() == []
    assert completer._get_neighbor_ips() == ['10.0.0.1']


def test_a_daemon_with_no_neighbours_is_an_answer_and_is_cached() -> None:
    sent: list[str] = []

    def send_command(command: str) -> str:
        sent.append(command)
        return '[]'

    completer = CommandCompleter(send_command=send_command)

    assert completer._get_neighbor_ips() == []
    assert completer._get_neighbor_ips() == []
    # An honest empty list is still worth caching: asking again on every TAB is what the
    # cache exists to avoid.
    assert sent == ['show neighbor json']


def test_the_addresses_survive_every_shape_the_daemon_uses() -> None:
    reply = (
        '[{"peer-address": "10.0.0.1"},'
        ' {"remote-addr": "10.0.0.2"},'
        ' {"peer": {"address": "10.0.0.3"}},'
        ' {"peer": {"ip": "10.0.0.4"}},'
        ' {"nothing-we-know": true},'
        ' "not a neighbour"]done'
    )
    completer = CommandCompleter(send_command=lambda command: reply)

    assert completer._get_neighbor_ips() == ['10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4']
