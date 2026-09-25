"""What spawning an API helper does, pinned before the code is rearranged.

`Processes._start` had no unit test at all, which is uncomfortable for a method that
decides three separate things: which encoder a helper speaks, what environment it is
handed, and whether it has crashed often enough to be given up on. The respawn limit in
particular is the only thing standing between a helper which dies on startup and a fork
loop, and nothing anywhere asserted that it fires.

These tests describe the behaviour as it is today, so that moving the code cannot change
it quietly. They assert on observable state, the encoder recorded for the process, the
environment handed to Popen, the respawn counters, rather than on how `_start` is built.
"""

from __future__ import annotations

import os
import subprocess
import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from exabgp.reactor.api.processes import ProcessError, Processes
from exabgp.reactor.api.response import Response


@pytest.fixture(autouse=True)
def quiet_logger() -> Any:
    with patch('exabgp.reactor.api.processes.log') as logger:
        yield logger


@pytest.fixture
def environment() -> Any:
    """The env() the module reads, with the API knobs a test is likely to want."""
    with patch('exabgp.reactor.api.processes.getenv') as getenv:
        env = MagicMock()
        env.api.respawn = True
        env.api.terminate = False
        env.api.ack = True
        env.api.version = 6
        getenv.return_value = env
        yield env


@pytest.fixture
def spawn() -> Any:
    """Stand in for Popen and for the two fcntl calls which follow it."""
    child = MagicMock()
    child.stdout.fileno.return_value = 31
    child.stdin.fileno.return_value = 32
    with patch('exabgp.reactor.api.processes.subprocess.Popen', return_value=child) as popen:
        with patch('exabgp.reactor.api.processes.fcntl.fcntl') as fcntl_call:
            yield popen, fcntl_call, child


def configured(environment: Any, **overrides: Any) -> Any:
    """A Processes holding one configured helper named 'helper'."""
    processes = Processes()
    configuration = {'run': ['/bin/cat'], 'encoder': 'json', 'respawn': True}
    configuration.update(overrides)
    processes._configuration = {'helper': configuration}
    return processes


class TestStartGuards:
    def test_a_helper_asked_not_to_restart_is_not_spawned(self, environment: Any, spawn: Any) -> None:
        popen, _, _ = spawn
        processes = configured(environment)
        processes._restart['helper'] = False

        processes._start('helper')

        popen.assert_not_called()

    def test_a_helper_already_running_is_not_spawned_twice(self, environment: Any, spawn: Any) -> None:
        popen, _, _ = spawn
        processes = configured(environment)
        processes._process['helper'] = MagicMock()

        processes._start('helper')

        popen.assert_not_called()

    def test_a_helper_with_no_configuration_is_not_spawned(self, environment: Any, spawn: Any) -> None:
        popen, _, _ = spawn
        processes = Processes()

        processes._start('helper')

        popen.assert_not_called()

    def test_a_configuration_with_no_command_spawns_nothing(self, environment: Any, spawn: Any) -> None:
        popen, _, _ = spawn
        processes = configured(environment, run='')

        processes._start('helper')

        popen.assert_not_called()
        assert 'helper' not in processes._encoder


class TestStartEncoder:
    def test_v6_gives_every_helper_the_json_encoder(self, environment: Any, spawn: Any) -> None:
        processes = configured(environment)

        processes._start('helper')

        assert isinstance(processes._encoder['helper'], Response.JSON)

    def test_v6_ignores_a_request_for_text(self, environment: Any, spawn: Any, quiet_logger: Any) -> None:
        """v6 is JSON only; asking for text is answered with a warning, not an error."""
        processes = configured(environment, encoder='text')

        processes._start('helper')

        assert isinstance(processes._encoder['helper'], Response.JSON)
        assert quiet_logger.warning.called

    def test_v4_still_honours_the_text_encoder(self, environment: Any, spawn: Any) -> None:
        environment.api.version = 4
        processes = configured(environment, encoder='text')

        processes._start('helper')

        assert isinstance(processes._encoder['helper'], Response.V4.Text)

    def test_v4_still_honours_the_json_encoder(self, environment: Any, spawn: Any) -> None:
        environment.api.version = 4
        processes = configured(environment)

        processes._start('helper')

        assert isinstance(processes._encoder['helper'], Response.V4.JSON)

    def test_acknowledgements_are_never_json(self, environment: Any, spawn: Any) -> None:
        """There is no ack-format option yet, so an ACK is the plain text one."""
        processes = configured(environment)

        processes._start('helper')

        assert processes._ackjson['helper'] is False

    def test_the_helper_configuration_overrides_the_global_ack_default(self, environment: Any, spawn: Any) -> None:
        processes = configured(environment, ack=False)

        processes._start('helper')

        assert processes._ack['helper'] is False

    def test_without_a_setting_the_global_ack_default_is_used(self, environment: Any, spawn: Any) -> None:
        processes = configured(environment)

        processes._start('helper')

        assert processes._ack['helper'] is True


class TestStartEnvironment:
    def test_the_cli_pipe_is_hidden_from_an_ordinary_helper(self, environment: Any, spawn: Any) -> None:
        """Only the internal CLI helper may talk on the CLI pipe."""
        popen, _, _ = spawn
        processes = configured(environment)

        with patch.dict(os.environ, {'exabgp_cli_pipe': '/run/exabgp'}):
            processes._start('helper')

        assert 'exabgp_cli_pipe' not in popen.call_args.kwargs['env']

    def test_the_cli_pipe_is_kept_for_the_internal_cli_helper(self, environment: Any, spawn: Any) -> None:
        popen, _, _ = spawn
        processes = configured(environment)
        processes._configuration['api-internal-cli-1'] = processes._configuration['helper']

        with patch.dict(os.environ, {'exabgp_cli_pipe': '/run/exabgp'}):
            processes._start('api-internal-cli-1')

        assert popen.call_args.kwargs['env']['exabgp_cli_pipe'] == '/run/exabgp'

    def test_configured_variables_are_added_to_the_child_environment(self, environment: Any, spawn: Any) -> None:
        popen, _, _ = spawn
        processes = configured(environment, env={'MY_SETTING': 'on'})

        processes._start('helper')

        assert popen.call_args.kwargs['env']['MY_SETTING'] == 'on'

    def test_the_terminal_is_declared_dumb(self, environment: Any, spawn: Any) -> None:
        """A capable TERM makes the shell emit escape codes into the start of the pipe."""
        popen, _, _ = spawn
        processes = configured(environment)

        with patch.dict(os.environ, {'TERM': 'xterm-256color'}):
            processes._start('helper')
            assert os.environ['TERM'] == 'dumb'

    def test_both_pipes_are_made_non_blocking(self, environment: Any, spawn: Any) -> None:
        """A blocking write to a slow helper would stop the whole reactor."""
        _, fcntl_call, _ = spawn
        processes = configured(environment)

        processes._start('helper')

        assert [call.args[0] for call in fcntl_call.call_args_list] == [31, 32]


class TestStartRespawn:
    """The limit counts respawns. An ordinary start is not one.

    These five tests used to describe `_start` keeping the count, and one of them pinned the
    consequence as behaviour rather than fixing it: with respawning switched off the limit is
    zero, so the second `_start` of a helper in one window raised ProcessError, which reached
    the reactor and shut the daemon down on two configuration reloads. The count now lives on
    the respawn path, so the tests follow it there.
    """

    def test_an_ordinary_start_records_nothing(self, environment: Any, spawn: Any) -> None:
        """A helper started because the configuration was read has not respawned."""
        processes = configured(environment)

        processes._start('helper')

        assert 'helper' not in processes._respawning

    def test_a_first_respawn_records_one(self, environment: Any, spawn: Any) -> None:
        processes = configured(environment)
        processes._start('helper')

        processes._handle_problem('helper')

        assert list(processes._respawning['helper'].values()) == [1]

    def test_a_second_respawn_in_the_same_window_counts_up(self, environment: Any, spawn: Any) -> None:
        processes = configured(environment)
        processes._start('helper')

        processes._handle_problem('helper')
        processes._handle_problem('helper')

        assert list(processes._respawning['helper'].values()) == [2]

    def test_a_respawn_in_a_new_window_resets_the_count(self, environment: Any, spawn: Any) -> None:
        """The counter is per time bucket, so a helper which is merely long lived is fine."""
        processes = configured(environment)
        processes._start('helper')
        processes._respawning['helper'] = {0: 99}

        processes._handle_problem('helper')

        assert list(processes._respawning['helper'].values()) == [1]

    def test_respawning_too_fast_gives_up_on_the_helper(self, environment: Any, spawn: Any) -> None:
        """Without this the daemon forks a dying helper forever.

        _handle_problem terminates before it counts, and suppresses the ProcessError, so a
        helper past its budget is left stopped and the asyncio callback this runs in is not
        taken down with it.
        """
        processes = configured(environment)
        processes._start('helper')

        for _ in range(processes.respawn_number + 1):
            processes._handle_problem('helper')

        assert list(processes._respawning['helper'].values()) == [processes.respawn_number + 1]
        assert 'helper' not in processes._process

    def test_the_limit_is_what_raises_and_nothing_else(self, environment: Any, spawn: Any) -> None:
        """ProcessError comes from the counter, so the suppression above has something to catch."""
        processes = configured(environment)
        processes._respawning['helper'] = {int(time.time()) & processes.respawn_timemask: 99}

        with pytest.raises(ProcessError):
            processes._record_respawn('helper')

    def test_with_respawn_disabled_a_second_start_in_the_window_is_allowed(self, environment: Any, spawn: Any) -> None:
        """The defect this file used to pin.

        exabgp_api_respawn=false sets respawn_number to 0. While `_start` kept the count, the
        second start of a helper inside one window exceeded it although nothing had died, and
        the ProcessError reaching the reactor was read as a reason to shut the daemon down.
        Two configuration reloads a second apart did that. Nothing on this path counts now.
        """
        environment.api.respawn = False
        processes = configured(environment)

        processes._start('helper')
        del processes._process['helper']
        processes._start('helper')

        assert 'helper' in processes._process
        assert 'helper' not in processes._respawning


class TestStartFailure:
    def test_a_command_which_will_not_run_marks_the_helper_broken(self, environment: Any) -> None:
        processes = configured(environment)

        with patch('exabgp.reactor.api.processes.subprocess.Popen', side_effect=OSError('no such file')):
            processes._start('helper')

        assert processes._broken == ['helper']
        assert 'helper' not in processes._process

    def test_a_command_rejected_by_the_shell_marks_the_helper_broken(self, environment: Any) -> None:
        failure = subprocess.CalledProcessError(1, '/bin/cat')
        processes = configured(environment)

        with patch('exabgp.reactor.api.processes.subprocess.Popen', side_effect=failure):
            processes._start('helper')

        assert processes._broken == ['helper']


class TestStartAsyncReader:
    def test_the_new_stdout_joins_the_event_loop(self, environment: Any, spawn: Any) -> None:
        """A helper spawned after setup_async_readers() must still be read from."""
        processes = configured(environment)
        processes._async_mode = True
        processes._loop = MagicMock()

        processes._start('helper')

        processes._loop.add_reader.assert_called_once_with(31, processes._async_reader_callback, 'helper')

    def test_no_reader_is_registered_in_sync_mode(self, environment: Any, spawn: Any) -> None:
        processes = configured(environment)
        processes._loop = MagicMock()

        processes._start('helper')

        processes._loop.add_reader.assert_not_called()
