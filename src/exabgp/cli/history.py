"""history.py

Command history tracking for CLI auto-complete ranking.

Tracks command usage frequency, recency, and success rates to provide
smarter auto-complete suggestions. Stores data in XDG-compliant location
with automatic migration from legacy paths.

Privacy: Never stores actual IP addresses - all IPs are anonymized to '*'.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass
class CommandStats:
    """Statistics for a single command."""

    count: int = 0  # Number of times executed
    last_used: float = 0.0  # Timestamp of last execution
    success_count: int = 0  # Number of successful executions
    failure_count: int = 0  # Number of failed executions

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 to 1.0)."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0  # Assume success if no data
        return self.success_count / total


class HistoryTracker:
    """Track CLI command usage for smarter auto-complete.

    Features:
    - XDG Base Directory compliant storage
    - Automatic migration from legacy paths
    - Privacy protection (anonymize IPs)
    - Opt-out via exabgp_cli_history=false
    - Automatic cleanup (prune old entries)

    Example:
        >>> tracker = HistoryTracker()
        >>> tracker.record_command('show neighbor', success=True)
        >>> score = tracker.get_frequency_bonus('show neighbor')
        >>> score
        5
    """

    def __init__(self, enabled: bool | None = None):
        """Initialize history tracker.

        Args:
            enabled: If True, enable tracking. If None, check environment variable.
                    Set to False to disable (for testing or privacy).
        """
        # Check if history tracking is enabled
        if enabled is None:
            env_value = os.environ.get('exabgp_cli_history', 'true').lower()
            self.enabled = env_value not in ('false', '0', 'no', 'off')
        else:
            self.enabled = enabled

        # Command statistics
        self._stats: dict[str, CommandStats] = {}

        # History file path (XDG compliant)
        self._history_path: Path | None = None

        # Load history if enabled
        if self.enabled:
            self._history_path = self._get_history_path()
            self._load_history()

    def _get_history_path(self) -> Path:
        """Get history file path following XDG Base Directory spec.

        Priority:
        1. $XDG_STATE_HOME/exabgp/cli_history.json
        2. $XDG_CONFIG_HOME/exabgp/cli_history.json
        3. ~/.exabgp_cli_history.json (legacy, migrated)

        Returns:
            Path to history file
        """
        # Try XDG_STATE_HOME first (proper location for state/history)
        xdg_state_home = os.environ.get('XDG_STATE_HOME')
        if not xdg_state_home:
            xdg_state_home = str(Path.home() / '.local' / 'state')

        state_path = Path(xdg_state_home) / 'exabgp' / 'cli_history.json'

        # Try XDG_CONFIG_HOME as fallback
        xdg_config_home = os.environ.get('XDG_CONFIG_HOME')
        if not xdg_config_home:
            xdg_config_home = str(Path.home() / '.config')

        config_path = Path(xdg_config_home) / 'exabgp' / 'cli_history.json'

        # Legacy path
        legacy_path = Path.home() / '.exabgp_cli_history.json'

        # Check if state path already exists (handle permission errors)
        try:
            if state_path.exists():
                return state_path
        except (OSError, PermissionError):
            pass  # Can't access state path, try config path

        # Check if config path exists
        try:
            if config_path.exists():
                return config_path
        except (OSError, PermissionError):
            pass  # Can't access config path, try legacy

        # Check if legacy path exists and migrate
        try:
            if legacy_path.exists():
                # Migrate to state path
                try:
                    state_path.parent.mkdir(parents=True, exist_ok=True)
                    legacy_path.rename(state_path)
                    return state_path
                except (OSError, PermissionError):
                    # Migration failed, fall back to config path
                    try:
                        config_path.parent.mkdir(parents=True, exist_ok=True)
                        legacy_path.rename(config_path)
                        return config_path
                    except (OSError, PermissionError):
                        # Can't migrate, use legacy path
                        return legacy_path
        except (OSError, PermissionError):
            pass  # Can't access legacy path

        # No existing file, create in state path (or fall back to config/legacy)
        # Try state path first
        try:
            # Test if we can write to state path
            state_path.parent.mkdir(parents=True, exist_ok=True)
            return state_path
        except (OSError, PermissionError):
            # Try config path
            try:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                return config_path
            except (OSError, PermissionError):
                # Fall back to legacy path (home directory should always be writable)
                return legacy_path

    def _load_history(self) -> None:
        """Load history from disk."""
        if not self._history_path:
            return

        # Check if file exists (handle permission errors)
        try:
            if not self._history_path.exists():
                return
        except (OSError, PermissionError):
            # Can't access file - disable history
            self.enabled = False
            return

        try:
            with open(self._history_path, 'r') as f:
                data = json.load(f)

            # Parse command stats
            commands = data.get('commands', {})
            for cmd, stats in commands.items():
                self._stats[cmd] = CommandStats(
                    count=stats.get('count', 0),
                    last_used=stats.get('last_used', 0.0),
                    success_count=stats.get('success_count', 0),
                    failure_count=stats.get('failure_count', 0),
                )

            # Auto-cleanup old entries
            self._cleanup_old_entries()

        except (json.JSONDecodeError, OSError, KeyError):
            # Corrupted history file - delete and start fresh
            try:
                self._history_path.unlink()
            except OSError:
                pass
            self._stats = {}

    def _save_history(self) -> None:
        """Save history to disk."""
        if not self.enabled or not self._history_path:
            return

        try:
            # Ensure parent directory exists
            self._history_path.parent.mkdir(parents=True, exist_ok=True)

            # Serialize stats
            data = {
                'version': 1,
                'commands': {
                    cmd: {
                        'count': stats.count,
                        'last_used': stats.last_used,
                        'success_count': stats.success_count,
                        'failure_count': stats.failure_count,
                    }
                    for cmd, stats in self._stats.items()
                },
            }

            # Write atomically (write to temp file, then rename)
            temp_path = self._history_path.with_suffix('.json.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)

            # Atomic rename
            temp_path.replace(self._history_path)

        except (OSError, PermissionError):
            # Can't write history - silently continue
            pass

    def _anonymize_command(self, command: str) -> str:
        """Anonymize a command by replacing IP addresses with '*'.

        Args:
            command: Raw command string

        Returns:
            Anonymized command with IPs replaced

        Example:
            >>> _anonymize_command('show neighbor 192.168.1.1')
            "show neighbor *"
        """
        # Replace IPv4 addresses with *
        command = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '*', command)

        # Replace IPv6 addresses with *
        # Simple pattern - matches most IPv6 formats
        command = re.sub(r'\b[0-9a-fA-F:]+:[0-9a-fA-F:]+\b', '*', command)

        return command

    def _cleanup_old_entries(self, max_age_days: int = 90, max_entries: int = 500) -> None:
        """Remove old or excess entries.

        Args:
            max_age_days: Remove entries older than this many days
            max_entries: Keep at most this many entries
        """
        if not self._stats:
            return

        current_time = time.time()
        max_age_seconds = max_age_days * 24 * 60 * 60

        # Remove entries older than max_age_days
        self._stats = {
            cmd: stats for cmd, stats in self._stats.items() if (current_time - stats.last_used) < max_age_seconds
        }

        # If still too many entries, keep only the most recent
        if len(self._stats) > max_entries:
            # Sort by last_used descending
            sorted_stats = sorted(self._stats.items(), key=lambda x: x[1].last_used, reverse=True)

            # Keep only top max_entries
            self._stats = dict(sorted_stats[:max_entries])

    def record_command(self, command: str, success: bool = True) -> None:
        """Record a command execution.

        Args:
            command: Command string (will be anonymized)
            success: Whether the command succeeded
        """
        if not self.enabled:
            return

        # Anonymize the command (remove IP addresses)
        anon_command = self._anonymize_command(command)

        # Get or create stats
        if anon_command not in self._stats:
            self._stats[anon_command] = CommandStats()

        stats = self._stats[anon_command]

        # Update stats
        stats.count += 1
        stats.last_used = time.time()

        if success:
            stats.success_count += 1
        else:
            stats.failure_count += 1

        # Save to disk
        self._save_history()

    def get_frequency_bonus(self, command: str) -> int:
        """Get frequency bonus for a command (0-50 points).

        Args:
            command: Command string

        Returns:
            Bonus score based on usage frequency
        """
        if not self.enabled:
            return 0

        # Anonymize for lookup
        anon_command = self._anonymize_command(command)

        stats = self._stats.get(anon_command)
        if not stats:
            return 0

        # Frequency bonus: 0-50 points based on count
        # Scale: 1 use = 5 points, 10+ uses = 50 points
        return min(50, stats.count * 5)

    def get_recency_bonus(self, command: str) -> int:
        """Get recency bonus for a command (0-25 points).

        Args:
            command: Command string

        Returns:
            Bonus score based on how recently used
        """
        if not self.enabled:
            return 0

        # Anonymize for lookup
        anon_command = self._anonymize_command(command)

        stats = self._stats.get(anon_command)
        if not stats:
            return 0

        # Recency bonus based on time since last use
        seconds_ago = time.time() - stats.last_used

        if seconds_ago < 300:  # 5 minutes
            return 25
        elif seconds_ago < 3600:  # 1 hour
            return 15
        elif seconds_ago < 86400:  # 1 day
            return 5
        else:
            return 0

    def get_success_rate_bonus(self, command: str) -> int:
        """Get success rate bonus for a command (0-25 points).

        Args:
            command: Command string

        Returns:
            Bonus score based on success rate
        """
        if not self.enabled:
            return 0

        # Anonymize for lookup
        anon_command = self._anonymize_command(command)

        stats = self._stats.get(anon_command)
        if not stats:
            return 25  # Assume success if no data

        # Success rate bonus: 0-25 points
        return int(stats.success_rate * 25)

    def get_total_bonus(self, command: str) -> int:
        """Get total bonus score for a command.

        Args:
            command: Command string

        Returns:
            Total bonus score (frequency + recency + success rate)
        """
        if not self.enabled:
            return 0

        return (
            self.get_frequency_bonus(command) + self.get_recency_bonus(command) + self.get_success_rate_bonus(command)
        )

    def invalidate_cache(self) -> None:
        """Clear all history data (for testing or user request)."""
        self._stats = {}
        if self._history_path and self._history_path.exists():
            try:
                self._history_path.unlink()
            except OSError:
                pass
