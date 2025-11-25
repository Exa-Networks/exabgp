"""Unit tests for Processes.start() change detection."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture(autouse=True)
def mock_logger():
    """Mock the logger to avoid initialization issues."""
    with patch('exabgp.reactor.api.processes.log') as mock_log:
        yield mock_log


class TestProcessesStart:
    """Test Processes.start() method - process change detection."""

    @pytest.fixture
    def processes(self):
        """Create a Processes instance with mocked subprocess calls."""
        with patch('exabgp.reactor.api.processes.getenv') as mock_getenv:
            # Mock environment
            mock_env = MagicMock()
            mock_env.api.respawn = False
            mock_env.api.terminate = False
            mock_env.api.ack = True
            mock_getenv.return_value = mock_env

            from exabgp.reactor.api.processes import Processes

            proc = Processes()
            # Track method calls
            proc._started = []
            proc._terminated = []

            # Mock _start to track calls without actually starting processes
            def mock_start(process):
                proc._started.append(process)

            proc._start = mock_start

            # Mock _terminate to track calls without actually terminating
            def mock_terminate(process):
                proc._terminated.append(process)
                # Remove from _process dict as real _terminate does
                if process in proc._process:
                    del proc._process[process]

            proc._terminate = mock_terminate

            yield proc

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
        processes._process['process-a'] = MagicMock()
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
        processes._process['process-a'] = MagicMock()
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
        processes._process['process-a'] = MagicMock()
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

        processes._process['process-a'] = MagicMock()
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

        processes._process['process-a'] = MagicMock()
        processes._configuration = old_config

        # restart=False should skip change detection entirely
        processes.start(new_config, restart=False)

        assert 'process-a' not in processes._terminated
        assert 'process-a' not in processes._started

    def test_multiple_processes_selective_restart(self, processes):
        """Only changed processes should restart, unchanged should be kept."""
        old_config = {
            'unchanged': {'run': '/bin/a', 'encoder': 'text'},
            'changed': {'run': '/bin/b', 'encoder': 'text'},
            'removed': {'run': '/bin/c', 'encoder': 'text'},
        }
        new_config = {
            'unchanged': {'run': '/bin/a', 'encoder': 'text'},  # Same
            'changed': {'run': '/bin/b-new', 'encoder': 'text'},  # Changed
            'added': {'run': '/bin/d', 'encoder': 'text'},  # New
        }

        # Simulate running processes
        processes._process['unchanged'] = MagicMock()
        processes._process['changed'] = MagicMock()
        processes._process['removed'] = MagicMock()
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
            'process-a': {'run': '/bin/true', 'encoder': 'text'},
        }

        processes.start(new_config, restart=False)

        assert processes._configuration == new_config

    def test_empty_old_config_starts_all(self, processes):
        """With empty old config, all processes should be started."""
        new_config = {
            'process-a': {'run': '/bin/a'},
            'process-b': {'run': '/bin/b'},
        }

        # Empty initial state
        processes._configuration = {}

        processes.start(new_config, restart=True)

        assert 'process-a' in processes._started
        assert 'process-b' in processes._started
        assert len(processes._terminated) == 0
