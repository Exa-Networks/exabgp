"""test_history.py

Unit tests for CLI command history tracking.

Tests:
- History persistence (save/load)
- Command recording with success/failure tracking
- Privacy (IP anonymization)
- XDG Base Directory compliance
- Ranking algorithm (frequency, recency, success rate)
- Cleanup/pruning of old entries
- Environment variable control
"""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

from exabgp.cli.history import CommandStats, HistoryTracker


@pytest.fixture(autouse=True, scope='function')
def clean_env():
    """Clean up environment variables before and after each test."""
    # Save original value
    original = os.environ.get('exabgp_cli_history')

    # Clean before test
    if 'exabgp_cli_history' in os.environ:
        del os.environ['exabgp_cli_history']

    yield

    # Restore after test
    if 'exabgp_cli_history' in os.environ:
        del os.environ['exabgp_cli_history']
    if original is not None:
        os.environ['exabgp_cli_history'] = original


class TestCommandStats:
    """Test CommandStats dataclass."""

    def test_default_values(self):
        """Test CommandStats default initialization."""
        stats = CommandStats()
        assert stats.count == 0
        assert stats.last_used == 0.0
        assert stats.success_count == 0
        assert stats.failure_count == 0

    def test_success_rate_no_data(self):
        """Test success_rate with no executions."""
        stats = CommandStats()
        assert stats.success_rate == 1.0  # Assume success if no data

    def test_success_rate_all_success(self):
        """Test success_rate with all successful executions."""
        stats = CommandStats(success_count=10, failure_count=0)
        assert stats.success_rate == 1.0

    def test_success_rate_all_failures(self):
        """Test success_rate with all failed executions."""
        stats = CommandStats(success_count=0, failure_count=10)
        assert stats.success_rate == 0.0

    def test_success_rate_mixed(self):
        """Test success_rate with mixed results."""
        stats = CommandStats(success_count=7, failure_count=3)
        assert stats.success_rate == 0.7


class TestHistoryTracker:
    """Test HistoryTracker class."""

    @pytest.fixture
    def temp_history_file(self):
        """Create a temporary history file path (uses tempfile to avoid pytest tmp_path issues)."""
        # Use Python's tempfile directly to avoid pytest tmp_path lock contention
        tmp_dir = Path(tempfile.mkdtemp(prefix='exabgp_test_'))
        history_file = tmp_dir / 'test_cli_history.json'
        yield history_file
        # Cleanup after test
        try:
            shutil.rmtree(tmp_dir)
        except (OSError, PermissionError):
            pass

    @pytest.fixture
    def tracker_disabled(self):
        """Create a disabled tracker (for testing without side effects)."""
        return HistoryTracker(enabled=False)

    @pytest.fixture
    def tracker_enabled(self, temp_history_file, monkeypatch):
        """Create an enabled tracker with temporary storage."""
        # Ensure parent directory exists
        temp_history_file.parent.mkdir(parents=True, exist_ok=True)

        # Mock _get_history_path to use temp file
        def mock_get_path(self):
            return temp_history_file

        monkeypatch.setattr(HistoryTracker, '_get_history_path', mock_get_path)
        tracker = HistoryTracker(enabled=True)
        # Ensure history path is set
        if tracker._history_path is None:
            tracker._history_path = temp_history_file
        return tracker

    def test_disabled_by_default(self, monkeypatch):
        """Test that tracker respects exabgp_cli_history=false."""
        monkeypatch.setenv('exabgp_cli_history', 'false')
        tracker = HistoryTracker()
        assert not tracker.enabled

    def test_enabled_by_default(self, monkeypatch, tmp_path):
        """Test that tracker is enabled by default."""
        monkeypatch.setenv('exabgp_cli_history', 'true')

        # Mock path to avoid filesystem issues
        def mock_get_path(self):
            return tmp_path / 'test_history.json'

        monkeypatch.setattr(HistoryTracker, '_get_history_path', mock_get_path)
        tracker = HistoryTracker()
        assert tracker.enabled

    def test_env_var_variations(self, monkeypatch):
        """Test various environment variable values for disabling."""
        for value in ['false', 'False', '0', 'no', 'off']:
            monkeypatch.setenv('exabgp_cli_history', value)
            tracker = HistoryTracker()
            assert not tracker.enabled, f'Should be disabled for value: {value}'

    def test_record_command_disabled(self, tracker_disabled):
        """Test that disabled tracker doesn't record commands."""
        tracker_disabled.record_command('show neighbor', success=True)
        assert len(tracker_disabled._stats) == 0

    def test_record_command_basic(self, tracker_enabled):
        """Test basic command recording."""
        tracker_enabled.record_command('show neighbor', success=True)

        assert 'show neighbor' in tracker_enabled._stats
        stats = tracker_enabled._stats['show neighbor']
        assert stats.count == 1
        assert stats.success_count == 1
        assert stats.failure_count == 0
        assert stats.last_used > 0

    def test_record_command_failure(self, tracker_enabled):
        """Test recording failed commands."""
        tracker_enabled.record_command('invalid command', success=False)

        stats = tracker_enabled._stats['invalid command']
        assert stats.count == 1
        assert stats.success_count == 0
        assert stats.failure_count == 1

    def test_record_command_multiple(self, tracker_enabled):
        """Test recording same command multiple times."""
        tracker_enabled.record_command('show neighbor', success=True)
        tracker_enabled.record_command('show neighbor', success=True)
        tracker_enabled.record_command('show neighbor', success=False)

        stats = tracker_enabled._stats['show neighbor']
        assert stats.count == 3
        assert stats.success_count == 2
        assert stats.failure_count == 1

    def test_anonymize_ipv4(self, tracker_enabled):
        """Test IPv4 address anonymization."""
        tracker_enabled.record_command('show neighbor 192.168.1.1', success=True)

        # Should be stored as 'show neighbor *'
        assert 'show neighbor *' in tracker_enabled._stats
        assert 'show neighbor 192.168.1.1' not in tracker_enabled._stats

    def test_anonymize_ipv6(self, tracker_enabled):
        """Test IPv6 address anonymization."""
        tracker_enabled.record_command('show neighbor 2001:db8::1', success=True)

        # Should be stored as 'show neighbor *'
        assert 'show neighbor *' in tracker_enabled._stats
        assert 'show neighbor 2001:db8::1' not in tracker_enabled._stats

    def test_anonymize_multiple_ips(self, tracker_enabled):
        """Test anonymization of multiple IPs in one command."""
        tracker_enabled.record_command('announce route 10.0.0.1 next-hop 192.168.1.1', success=True)

        # Both IPs should be replaced
        assert 'announce route * next-hop *' in tracker_enabled._stats

    def test_persistence_save_load(self, tracker_enabled, temp_history_file):
        """Test saving and loading history."""
        # Record some commands
        tracker_enabled.record_command('show neighbor', success=True)
        tracker_enabled.record_command('announce route', success=True)
        tracker_enabled.record_command('announce route', success=False)

        # File should exist
        assert temp_history_file.exists()

        # Load into new tracker
        tracker2 = HistoryTracker(enabled=True)
        # Mock the path for tracker2
        tracker2._history_path = temp_history_file
        tracker2._load_history()

        # Should have same stats
        assert len(tracker2._stats) == 2
        assert tracker2._stats['show neighbor'].count == 1
        assert tracker2._stats['announce route'].count == 2
        assert tracker2._stats['announce route'].success_count == 1
        assert tracker2._stats['announce route'].failure_count == 1

    def test_persistence_json_format(self, tracker_enabled, temp_history_file):
        """Test that history file is valid JSON with expected structure."""
        tracker_enabled.record_command('show neighbor', success=True)

        with open(temp_history_file) as f:
            data = json.load(f)

        assert 'version' in data
        assert data['version'] == 1
        assert 'commands' in data
        assert 'show neighbor' in data['commands']

        cmd_data = data['commands']['show neighbor']
        assert 'count' in cmd_data
        assert 'last_used' in cmd_data
        assert 'success_count' in cmd_data
        assert 'failure_count' in cmd_data

    def test_corrupted_history_recovery(self, tracker_enabled, temp_history_file):
        """Test recovery from corrupted history file."""
        # Create corrupted file
        with open(temp_history_file, 'w') as f:
            f.write('{ invalid json }')

        # Should recover gracefully
        tracker2 = HistoryTracker(enabled=True)
        tracker2._history_path = temp_history_file
        tracker2._load_history()

        # Should have empty stats (file deleted)
        assert len(tracker2._stats) == 0
        # File should be deleted
        assert not temp_history_file.exists()

    def test_frequency_bonus_disabled(self, tracker_disabled):
        """Test frequency bonus when tracker is disabled."""
        bonus = tracker_disabled.get_frequency_bonus('show neighbor')
        assert bonus == 0

    def test_frequency_bonus_unknown_command(self, tracker_enabled):
        """Test frequency bonus for unknown command."""
        bonus = tracker_enabled.get_frequency_bonus('unknown command')
        assert bonus == 0

    def test_frequency_bonus_scaling(self, tracker_enabled):
        """Test frequency bonus scaling."""
        # Record command multiple times
        for _ in range(10):
            tracker_enabled.record_command('show neighbor', success=True)

        bonus = tracker_enabled.get_frequency_bonus('show neighbor')
        # 10 uses * 5 points/use = 50 points (capped at 50)
        assert bonus == 50

    def test_frequency_bonus_low_usage(self, tracker_enabled):
        """Test frequency bonus with low usage."""
        tracker_enabled.record_command('show neighbor', success=True)

        bonus = tracker_enabled.get_frequency_bonus('show neighbor')
        # 1 use * 5 points/use = 5 points
        assert bonus == 5

    def test_recency_bonus_disabled(self, tracker_disabled):
        """Test recency bonus when tracker is disabled."""
        bonus = tracker_disabled.get_recency_bonus('show neighbor')
        assert bonus == 0

    def test_recency_bonus_recent(self, tracker_enabled):
        """Test recency bonus for recently used command."""
        tracker_enabled.record_command('show neighbor', success=True)

        bonus = tracker_enabled.get_recency_bonus('show neighbor')
        # Used just now (< 5 minutes ago) = 25 points
        assert bonus == 25

    def test_recency_bonus_old(self, tracker_enabled):
        """Test recency bonus for old command."""
        tracker_enabled.record_command('show neighbor', success=True)

        # Manually set last_used to 2 days ago
        stats = tracker_enabled._stats['show neighbor']
        stats.last_used = time.time() - (2 * 86400)

        bonus = tracker_enabled.get_recency_bonus('show neighbor')
        # Used > 1 day ago = 0 points
        assert bonus == 0

    def test_success_rate_bonus_disabled(self, tracker_disabled):
        """Test success rate bonus when tracker is disabled."""
        bonus = tracker_disabled.get_success_rate_bonus('show neighbor')
        assert bonus == 0

    def test_success_rate_bonus_unknown(self, tracker_enabled):
        """Test success rate bonus for unknown command."""
        bonus = tracker_enabled.get_success_rate_bonus('unknown command')
        # Unknown command = assume 100% success = 25 points
        assert bonus == 25

    def test_success_rate_bonus_perfect(self, tracker_enabled):
        """Test success rate bonus with 100% success."""
        tracker_enabled.record_command('show neighbor', success=True)
        tracker_enabled.record_command('show neighbor', success=True)

        bonus = tracker_enabled.get_success_rate_bonus('show neighbor')
        # 100% success = 25 points
        assert bonus == 25

    def test_success_rate_bonus_partial(self, tracker_enabled):
        """Test success rate bonus with partial success."""
        tracker_enabled.record_command('announce route', success=True)
        tracker_enabled.record_command('announce route', success=False)

        bonus = tracker_enabled.get_success_rate_bonus('announce route')
        # 50% success = 12 points (25 * 0.5 = 12.5, rounded down)
        assert bonus == 12

    def test_cleanup_old_entries(self, tracker_enabled):
        """Test cleanup of old entries."""
        # Add old entry
        tracker_enabled.record_command('old command', success=True)
        stats = tracker_enabled._stats['old command']
        stats.last_used = time.time() - (100 * 86400)  # 100 days ago

        # Add recent entry
        tracker_enabled.record_command('new command', success=True)

        # Cleanup (90 day threshold)
        tracker_enabled._cleanup_old_entries(max_age_days=90)

        # Old command should be removed
        assert 'old command' not in tracker_enabled._stats
        assert 'new command' in tracker_enabled._stats

    def test_cleanup_excess_entries(self, tracker_enabled):
        """Test cleanup when too many entries."""
        # Add 10 commands
        for i in range(10):
            tracker_enabled.record_command(f'command {i}', success=True)
            # Stagger timestamps so we can test ordering
            time.sleep(0.001)

        # Cleanup with low max_entries
        tracker_enabled._cleanup_old_entries(max_entries=5)

        # Should keep only 5 most recent
        assert len(tracker_enabled._stats) == 5

        # Should keep the most recent ones (commands 5-9)
        for i in range(5, 10):
            assert f'command {i}' in tracker_enabled._stats

    def test_xdg_state_home_priority(self, monkeypatch, tmp_path):
        """Test XDG_STATE_HOME takes priority."""
        state_dir = tmp_path / 'state'
        monkeypatch.setenv('XDG_STATE_HOME', str(state_dir))

        tracker = HistoryTracker(enabled=True)
        path = tracker._get_history_path()

        assert path == state_dir / 'exabgp' / 'cli_history.json'

    def test_xdg_config_home_fallback(self, monkeypatch, tmp_path):
        """Test XDG_CONFIG_HOME as fallback."""
        config_dir = tmp_path / 'config'
        monkeypatch.setenv('XDG_CONFIG_HOME', str(config_dir))
        # Ensure XDG_STATE_HOME doesn't exist
        monkeypatch.delenv('XDG_STATE_HOME', raising=False)

        tracker = HistoryTracker(enabled=True)
        # Create a file in config to make it exist
        config_path = config_dir / 'exabgp' / 'cli_history.json'
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.touch()

        path = tracker._get_history_path()
        assert path == config_path

    def test_legacy_migration(self, monkeypatch, tmp_path):
        """Test migration from legacy path."""
        # Create legacy file
        legacy_path = tmp_path / '.exabgp_cli_history.json'
        legacy_path.write_text('{"version": 1, "commands": {}}')

        # Mock home directory
        monkeypatch.setattr(Path, 'home', lambda: tmp_path)

        # Mock XDG paths to non-existent locations
        state_dir = tmp_path / 'state'
        monkeypatch.setenv('XDG_STATE_HOME', str(state_dir))

        tracker = HistoryTracker(enabled=True)
        path = tracker._get_history_path()

        # Should migrate to state path
        assert path == state_dir / 'exabgp' / 'cli_history.json'
        # Legacy file should be moved
        assert not legacy_path.exists()

    def test_atomic_write(self, tracker_enabled, temp_history_file):
        """Test atomic write to prevent corruption."""
        tracker_enabled.record_command('test command', success=True)

        # Should not have temp file after write
        temp_file = temp_history_file.with_suffix('.json.tmp')
        assert not temp_file.exists()

        # Main file should exist and be valid
        assert temp_history_file.exists()
        with open(temp_history_file) as f:
            _ = json.load(f)  # Should not raise


class TestIntegration:
    """Integration tests for history tracking."""

    def test_full_workflow(self, tmp_path, monkeypatch):
        """Test complete workflow: record, save, load, rank."""
        history_file = tmp_path / 'history.json'

        def mock_get_path(self):
            return history_file

        monkeypatch.setattr(HistoryTracker, '_get_history_path', mock_get_path)

        # Create tracker and record commands
        tracker1 = HistoryTracker(enabled=True)
        tracker1.record_command('show neighbor', success=True)
        tracker1.record_command('show neighbor', success=True)
        tracker1.record_command('announce route', success=True)
        tracker1.record_command('announce route', success=False)

        # Load into new tracker
        tracker2 = HistoryTracker(enabled=True)

        # Verify stats
        assert tracker2._stats['show neighbor'].count == 2
        assert tracker2._stats['show neighbor'].success_rate == 1.0
        assert tracker2._stats['announce route'].success_rate == 0.5

        # Test ranking bonuses
        freq_bonus = tracker2.get_frequency_bonus('show neighbor')
        assert freq_bonus == 10  # 2 uses * 5 points = 10

        recency_bonus = tracker2.get_recency_bonus('show neighbor')
        assert recency_bonus == 25  # Recent use

        success_bonus = tracker2.get_success_rate_bonus('show neighbor')
        assert success_bonus == 25  # 100% success

    def test_privacy_no_ip_leakage(self, tmp_path, monkeypatch):
        """Test that IPs are never stored in history file."""
        history_file = tmp_path / 'history.json'

        def mock_get_path(self):
            return history_file

        monkeypatch.setattr(HistoryTracker, '_get_history_path', mock_get_path)

        tracker = HistoryTracker(enabled=True)

        # Record commands with various IP addresses
        tracker.record_command('show neighbor 192.168.1.1', success=True)
        tracker.record_command('announce route 10.0.0.0/24 next-hop 1.2.3.4', success=True)
        tracker.record_command('teardown 2001:db8::1', success=True)

        # Read file content
        with open(history_file) as f:
            content = f.read()

        # Verify no IPs in file
        assert '192.168.1.1' not in content
        assert '10.0.0.0' not in content
        assert '1.2.3.4' not in content
        assert '2001:db8::1' not in content

        # Verify anonymized commands exist
        data = json.loads(content)
        commands = list(data['commands'].keys())
        assert 'show neighbor *' in commands
        # The CIDR notation /24 is preserved, only IPs are anonymized
        assert 'announce route */24 next-hop *' in commands
        assert 'teardown *' in commands
