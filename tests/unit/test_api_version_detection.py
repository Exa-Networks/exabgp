"""Each helper speaks API 4 or 6, detected from the commands it writes.

exabgp.api.version used to apply one version to every helper, so a 5.x helper writing
`announce route ...` got `error` for every command from a 6.0 daemon left at its default.
Left at auto, each helper is held to the version of the first command which tells; set to 4
or 6, every helper is held to it. A helper which does not read its answers stops being
answered once its pipe has stayed full, instead of growing ExaBGP's memory.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import collections
import os
import struct
import sys
import termios
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from exabgp.environment import Environment
from exabgp.reactor.api.dispatch.common import UnknownCommand
from exabgp.reactor.api.dispatch.version import (
    API_AUTO,
    API_V4,
    API_V6,
    command_api_version,
    dispatch_for,
)
from exabgp.reactor.api import processes as processes_module
from exabgp.reactor.api.processes import NETBSD_FIONWRITE, Processes, _is_answer, _unread_bytes
from exabgp.reactor.api.response.json import JSON
from exabgp.reactor.api.response.v4.json import V4JSON
from exabgp.reactor.api.response.v4.text import V4Text
from tests import negotiation


@pytest.fixture(autouse=True)
def quiet_logger() -> Any:
    with patch('exabgp.reactor.api.processes.log') as logger:
        yield logger


def environment(version: int) -> Any:
    env = Environment()
    env.api.respawn = True
    env.api.terminate = False
    env.api.ack = True
    env.api.version = version
    return env


def started(version: int, encoder: str, name: str = 'helper') -> Processes:
    """A Processes which has just started `name`, as _start does before spawning it."""
    with patch('exabgp.reactor.api.processes.getenv', return_value=environment(version)):
        processes = Processes()
        processes._configuration = {name: {'run': ['/bin/cat'], 'encoder': encoder}}
        processes._select_encoder(name, processes._configuration[name])
    processes._ack[name] = True
    return processes


class TestCommandVersion:
    @pytest.mark.parametrize(
        'command',
        [
            'peer * announce route 192.0.2.1/32 next-hop self',
            'peer 192.0.2.1 withdraw route 192.0.2.1/32',
            'session ack disable',
            'daemon shutdown',
            'system api version',
            'rib show out',
        ],
    )
    def test_v6_commands(self, command: str) -> None:
        assert command_api_version(command) == API_V6

    @pytest.mark.parametrize(
        'command',
        [
            'announce route 192.0.2.1/32 next-hop self',
            'withdraw route 192.0.2.1/32',
            'neighbor 192.0.2.1 announce route 192.0.2.1/32 next-hop self',
            'disable-ack',
            'shutdown',
            'show neighbor summary',
            'announce watchdog dnsr',
        ],
    )
    def test_v4_commands(self, command: str) -> None:
        assert command_api_version(command) == API_V4

    @pytest.mark.parametrize('command', ['', '   ', '# comment', 'group start', 'this is not a command'])
    def test_commands_which_do_not_tell(self, command: str) -> None:
        # a mistyped first command must not hold a helper to the wrong version
        assert command_api_version(command) == API_AUTO


class TestDispatchFor:
    def test_a_v4_helper_is_refused_a_v6_command(self) -> None:
        with pytest.raises(UnknownCommand):
            dispatch_for(API_V4, 'peer * announce route 192.0.2.1/32 next-hop self', MagicMock(), 'helper')

    def test_a_v6_helper_is_refused_a_v4_command(self) -> None:
        with pytest.raises(UnknownCommand):
            dispatch_for(API_V6, 'announce route 192.0.2.1/32 next-hop self', MagicMock(), 'helper')

    def test_a_v4_helper_keeps_its_commands(self) -> None:
        reactor = MagicMock()
        reactor.peers.return_value = ['peer-1']
        handler, _, remaining = dispatch_for(API_V4, 'announce route 192.0.2.1/32 next-hop self', reactor, 'helper')
        assert 'route 192.0.2.1/32' in remaining
        assert callable(handler)

    def test_an_undecided_helper_may_group(self) -> None:
        # group decides nothing
        handler, _, _ = dispatch_for(API_AUTO, 'group start', MagicMock(), 'helper')
        assert handler.__name__ == 'group_start'

    @pytest.mark.parametrize(
        'command,name',
        [
            ('group start', 'group_start'),
            ('group end', 'group_end'),
        ],
    )
    def test_a_v4_helper_may_group(self, command: str, name: str) -> None:
        # The commands inside a group are the v4 `announce ...`, so `group start`,
        # `announce route ...` held the helper to v4, and its `group end` was refused.
        handler, _, _ = dispatch_for(API_V4, command, MagicMock(), 'helper')
        assert handler.__name__ == name


class TestVersionPerHelper:
    def test_auto_json_helper_starts_undecided_with_v6_json(self) -> None:
        processes = started(API_AUTO, 'json')
        assert processes.api_version('helper') == API_AUTO
        assert type(processes._encoder['helper']) is JSON

    def test_auto_text_helper_starts_undecided_with_v4_text(self) -> None:
        # the encoder does not decide: a 6.0 helper may still ask for text
        processes = started(API_AUTO, 'text')
        assert processes.api_version('helper') == API_AUTO
        assert type(processes._encoder['helper']) is V4Text

    def test_a_text_helper_writing_v6_commands_gets_v6_json(self) -> None:
        processes = started(API_AUTO, 'text')
        assert processes.detect_api_version('helper', 'peer * announce route 192.0.2.1/32 next-hop self') == API_V6
        assert type(processes._encoder['helper']) is JSON

    def test_a_text_helper_writing_v4_commands_keeps_v4_text(self) -> None:
        processes = started(API_AUTO, 'text')
        assert processes.detect_api_version('helper', 'announce route 192.0.2.1/32 next-hop self') == API_V4
        assert type(processes._encoder['helper']) is V4Text

    def test_the_first_v4_command_holds_a_json_helper_to_v4(self) -> None:
        processes = started(API_AUTO, 'json')
        assert processes.detect_api_version('helper', 'announce route 192.0.2.1/32 next-hop self') == API_V4
        assert type(processes._encoder['helper']) is V4JSON
        # held for good: a later v6 command does not change it
        assert processes.detect_api_version('helper', 'peer * announce route 192.0.2.1/32 next-hop self') == API_V4

    def test_the_first_v6_command_holds_a_helper_to_v6(self) -> None:
        processes = started(API_AUTO, 'json')
        assert processes.detect_api_version('helper', 'peer * announce route 192.0.2.1/32 next-hop self') == API_V6
        assert type(processes._encoder['helper']) is JSON
        assert processes.detect_api_version('helper', 'announce route 192.0.2.1/32 next-hop self') == API_V6

    def test_a_group_of_v4_commands_can_be_ended(self) -> None:
        processes = started(API_AUTO, 'json')
        assert processes.detect_api_version('helper', 'group start') == API_AUTO
        assert processes.detect_api_version('helper', 'announce route 192.0.2.1/32 next-hop self') == API_V4
        version = processes.detect_api_version('helper', 'group end')
        handler, _, _ = dispatch_for(version, 'group end', MagicMock(), 'helper')
        assert handler.__name__ == 'group_end'

    def test_a_command_which_does_not_tell_leaves_it_undecided(self) -> None:
        processes = started(API_AUTO, 'json')
        assert processes.detect_api_version('helper', 'group start') == API_AUTO
        assert processes.api_version('helper') == API_AUTO

    @pytest.mark.parametrize('forced', [API_V4, API_V6])
    def test_a_forced_version_holds_every_helper(self, forced: int) -> None:
        processes = started(forced, 'json')
        assert processes.api_version('helper') == forced
        other = API_V6 if forced == API_V4 else API_V4
        command = 'peer * announce route 192.0.2.1/32 next-hop self' if other == API_V6 else 'shutdown'
        assert processes.detect_api_version('helper', command) == forced

    def test_exabgp_own_helpers_are_v6_even_when_v4_is_forced(self) -> None:
        # the internal CLI helper writes `session ack enable` whatever the operator chose
        from exabgp.configuration.cli_process import API_PREFIX

        processes = started(API_V4, 'json', name=f'{API_PREFIX}-cli')
        assert processes.api_version(f'{API_PREFIX}-cli') == API_V6

    def test_a_restart_forgets_the_version(self) -> None:
        processes = started(API_AUTO, 'json')
        processes.detect_api_version('helper', 'shutdown')
        with patch('exabgp.reactor.api.processes.getenv', return_value=environment(API_AUTO)):
            processes._select_encoder('helper', processes._configuration['helper'])
        assert processes.api_version('helper') == API_AUTO


class TestUnreadAnswers:
    @pytest.mark.parametrize('line', [b'done\n', b'error\n', b'error: no such peer\n'])
    def test_answers(self, line: bytes) -> None:
        assert _is_answer(line)

    @pytest.mark.parametrize('line', [b'{ "type": "update" }\n', b'neighbor 192.0.2.1 up\n', b'done and more\n'])
    def test_not_answers(self, line: bytes) -> None:
        assert not _is_answer(line)

    def test_unread_bytes_counts_what_the_reader_left(self) -> None:
        read_end, write_end = os.pipe()
        try:
            os.write(write_end, b'done\n' * 3)
            if sys.platform.startswith(('linux', 'darwin', 'netbsd')):
                # macOS answered FIONREAD on the writing end with 0, its count is the pipe size
                assert _unread_bytes(write_end) == 15
                os.read(read_end, 5)
                assert _unread_bytes(write_end) == 10
            else:
                # FreeBSD, and what was not read: saying nothing rather than a 0 which may be wrong
                assert _unread_bytes(write_end) == -1
        finally:
            os.close(read_end)
            os.close(write_end)

    @pytest.mark.parametrize(
        'platform,request_code',
        [('linux', termios.FIONREAD), ('netbsd10', NETBSD_FIONWRITE)],
    )
    def test_each_system_is_asked_what_its_kernel_answers(self, platform: str, request_code: int) -> None:
        # run where the kernel is not this one: the request is checked, not its answer
        module = negotiation.interpreted(processes_module)
        asked: list[int] = []

        def ioctl(fd: int, request: int, arg: bytes) -> bytes:
            asked.append(request)
            return struct.pack('i', 15)

        with patch.object(module.sys, 'platform', platform), patch.object(module.fcntl, 'ioctl', ioctl):
            assert module._unread_bytes(0) == 15
        assert asked == [request_code]

    def test_freebsd_does_not_say(self) -> None:
        # sys_pipe.c answers FIONREAD with 0 without FREAD, and has no FIONWRITE for a pipe
        module = negotiation.interpreted(processes_module)
        with patch.object(module.sys, 'platform', 'freebsd14'), patch.object(module.fcntl, 'ioctl') as ioctl:
            assert module._unread_bytes(0) == -1
        ioctl.assert_not_called()

    def full_pipe(self, queued: list[bytes], seconds: float) -> tuple[Processes, collections.deque[bytes]]:
        """A helper whose pipe has been full for `seconds`, with `queued` waiting behind it."""
        processes = started(API_AUTO, 'json')
        processes._process['helper'] = MagicMock()
        processes._process['helper'].stdin.fileno.return_value = -1
        queue = collections.deque(queued)
        with patch('exabgp.reactor.api.processes.time.monotonic', return_value=1000.0):
            processes._stop_unread_answers('helper', queue)
        with patch('exabgp.reactor.api.processes.time.monotonic', return_value=1000.0 + seconds):
            processes._stop_unread_answers('helper', queue)
        return processes, queue

    def test_a_helper_not_reading_its_answers_stops_being_answered(self) -> None:
        processes, queue = self.full_pipe([b'done\n'] * 50, Processes.UNREAD_ANSWERS_SECONDS)
        assert not queue
        assert processes._ack['helper'] is False

    def test_a_helper_reading_slowly_is_still_answered(self) -> None:
        processes, queue = self.full_pipe([b'done\n'] * 50, Processes.UNREAD_ANSWERS_SECONDS - 1)
        assert len(queue) == 50
        assert processes._ack['helper'] is True

    def test_messages_the_helper_asked_for_are_kept(self) -> None:
        queued = [b'done\n', b'{ "type": "update" }\n', b'done\n']
        processes, queue = self.full_pipe(queued, Processes.UNREAD_ANSWERS_SECONDS * 2)
        assert list(queue) == queued
        assert processes._ack['helper'] is True
