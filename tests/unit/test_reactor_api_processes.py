"""Unit tests for Processes.start() change detection."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from exabgp.environment import Environment


@pytest.fixture(autouse=True)
def mock_logger():
    """Mock the logger to avoid initialization issues."""
    with patch('exabgp.reactor.api.processes.log') as mock_log:
        yield mock_log


def helper_process() -> MagicMock:
    """What Popen returns for a helper: two pipes with a descriptor each."""
    child = MagicMock()
    child.stdout.fileno.return_value = 31
    child.stdin.fileno.return_value = 32
    return child


class Recorded:
    """A real Processes, with the helpers it starts and terminates written down.

    The compiled Processes does not let a test replace _start or _terminate on the
    instance, so the two are observed where they reach outside: _start through Popen,
    which creates the helper, and _terminate through the Thread which stops it. Every
    other attribute is the Processes' own.
    """

    def __init__(self, processes: Any) -> None:
        object.__setattr__(self, '_processes', processes)
        object.__setattr__(self, '_children', [])
        object.__setattr__(self, '_terminated', [])

    def __getattr__(self, name: str) -> Any:
        return getattr(self._processes, name)

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._processes, name, value)

    @property
    def _started(self) -> list[str]:
        return [name for name, child in self._processes._process.items() if child in self._children]

    def popen(self, *args: Any, **kwargs: Any) -> Any:
        child = helper_process()
        self._children.append(child)
        return child

    def thread(self, target: Any, args: tuple[Any, str]) -> Any:
        self._terminated.append(args[1])
        return MagicMock()


class TestProcessesStart:
    """Test Processes.start() method - process change detection."""

    @pytest.fixture
    def processes(self) -> Iterator[Recorded]:
        """A Processes which starts and terminates helpers without creating any."""
        with patch('exabgp.reactor.api.processes.getenv') as mock_getenv:
            environment = Environment()
            environment.api.respawn = False
            environment.api.terminate = False
            environment.api.ack = True
            mock_getenv.return_value = environment

            from exabgp.reactor.api.processes import Processes

            recorded = Recorded(Processes())

        with (
            patch('exabgp.reactor.api.processes.subprocess.Popen', side_effect=recorded.popen),
            patch('exabgp.reactor.api.processes.fcntl.fcntl'),
            patch('exabgp.reactor.api.processes.Thread', side_effect=recorded.thread),
        ):
            yield recorded

    def test_new_process_started(self, processes):
        """New processes should be started."""
        config = {
            'process-a': {'run': '/bin/true', 'encoder': 'text', 'respawn': True},
        }

        processes.start(config, restart=False)

        assert 'process-a' in processes._started
        assert len(processes._terminated) == 0

    def test_removed_process_terminated(self, processes):
        """Processes removed from config should be terminated."""
        # Simulate existing running process
        processes._process['process-a'] = helper_process()
        processes._configuration = {
            'process-a': {'run': '/bin/true', 'encoder': 'text', 'respawn': True},
        }

        # New config without process-a
        new_config = {}

        processes.start(new_config, restart=False)

        assert 'process-a' in processes._terminated
        assert len(processes._started) == 0

    def test_unchanged_process_not_restarted(self, processes):
        """Processes with unchanged config should NOT be restarted."""
        config = {
            'process-a': {'run': '/bin/true', 'encoder': 'text', 'respawn': True},
        }

        # Simulate existing running process with same config
        processes._process['process-a'] = helper_process()
        processes._configuration = config.copy()

        # Call start with restart=True but same config
        processes.start(config, restart=True)

        # Should NOT restart (config unchanged)
        assert 'process-a' not in processes._terminated
        assert 'process-a' not in processes._started

    def test_changed_process_restarted(self, processes):
        """Processes with changed config should be restarted."""
        old_config = {
            'process-a': {'run': '/bin/true', 'encoder': 'text', 'respawn': True},
        }
        new_config = {
            'process-a': {'run': '/bin/false', 'encoder': 'text', 'respawn': True},  # Changed 'run'
        }

        # Simulate existing running process
        processes._process['process-a'] = helper_process()
        processes._configuration = old_config

        processes.start(new_config, restart=True)

        # Should restart (config changed)
        assert 'process-a' in processes._terminated
        assert 'process-a' in processes._started

    def test_changed_encoder_triggers_restart(self, processes):
        """Changing encoder should trigger restart."""
        old_config = {
            'process-a': {'run': '/bin/true', 'encoder': 'text', 'respawn': True},
        }
        new_config = {
            'process-a': {'run': '/bin/true', 'encoder': 'json', 'respawn': True},  # Changed encoder
        }

        processes._process['process-a'] = helper_process()
        processes._configuration = old_config

        processes.start(new_config, restart=True)

        assert 'process-a' in processes._terminated
        assert 'process-a' in processes._started

    def test_restart_false_never_restarts_existing(self, processes):
        """With restart=False, existing processes should never be restarted."""
        old_config = {
            'process-a': {'run': '/bin/true', 'encoder': 'text', 'respawn': True},
        }
        new_config = {
            'process-a': {'run': '/bin/false', 'encoder': 'json', 'respawn': False},  # All changed
        }

        processes._process['process-a'] = helper_process()
        processes._configuration = old_config

        # restart=False should skip change detection entirely
        processes.start(new_config, restart=False)

        assert 'process-a' not in processes._terminated
        assert 'process-a' not in processes._started

    def test_multiple_processes_selective_restart(self, processes):
        """Only changed processes should restart, unchanged should be kept."""
        old_config = {
            'unchanged': {'run': '/bin/a', 'encoder': 'text', 'respawn': True},
            'changed': {'run': '/bin/b', 'encoder': 'text', 'respawn': True},
            'removed': {'run': '/bin/c', 'encoder': 'text', 'respawn': True},
        }
        new_config = {
            'unchanged': {'run': '/bin/a', 'encoder': 'text', 'respawn': True},  # Same
            'changed': {'run': '/bin/b-new', 'encoder': 'text', 'respawn': True},  # Changed
            'added': {'run': '/bin/d', 'encoder': 'text', 'respawn': True},  # New
        }

        # Simulate running processes
        processes._process['unchanged'] = helper_process()
        processes._process['changed'] = helper_process()
        processes._process['removed'] = helper_process()
        processes._configuration = old_config

        processes.start(new_config, restart=True)

        # 'removed' should be terminated (not in new config)
        assert 'removed' in processes._terminated

        # 'unchanged' should NOT be restarted
        assert 'unchanged' not in processes._terminated
        assert 'unchanged' not in processes._started

        # 'changed' should be restarted
        assert 'changed' in processes._terminated
        assert 'changed' in processes._started

        # 'added' should be started (new process)
        assert 'added' in processes._started
        assert 'added' not in processes._terminated

    def test_configuration_updated_after_start(self, processes):
        """Configuration should be updated after start() call."""
        new_config = {
            'process-a': {'run': '/bin/true', 'encoder': 'text', 'respawn': True},
        }

        processes.start(new_config, restart=False)

        assert processes._configuration == new_config

    def test_empty_old_config_starts_all(self, processes):
        """With empty old config, all processes should be started."""
        new_config = {
            'process-a': {'run': '/bin/a', 'respawn': True},
            'process-b': {'run': '/bin/b', 'respawn': True},
        }

        # Empty initial state
        processes._configuration = {}

        processes.start(new_config, restart=True)

        assert 'process-a' in processes._started
        assert 'process-b' in processes._started
        assert len(processes._terminated) == 0
