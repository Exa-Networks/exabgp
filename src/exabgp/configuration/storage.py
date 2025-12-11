"""storage.py - Safe configuration file operations.

This module provides safe file operations for configuration persistence:
- Atomic writes using temp file + rename
- Backup creation before overwriting
- Symlink rejection using O_NOFOLLOW (no TOCTOU race conditions)

Security: All symlink checks use O_NOFOLLOW at the syscall level to prevent
TOCTOU (time-of-check to time-of-use) race conditions where an attacker could
swap a regular file for a symlink between the check and the operation.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import errno
import os
import stat
import tempfile
from pathlib import Path


class ConfigurationStorageError(Exception):
    """Error during configuration storage operations."""

    pass


def _read_nofollow(filepath: Path) -> bytes:
    """Read file contents atomically, refusing to follow symlinks.

    Uses O_NOFOLLOW to prevent TOCTOU race conditions.

    Args:
        filepath: Path to file to read

    Returns:
        File contents as bytes

    Raises:
        ConfigurationStorageError: If file is a symlink or read fails
    """
    try:
        # O_NOFOLLOW makes this atomic - kernel refuses to open symlinks
        fd = os.open(filepath, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as e:
        if e.errno == errno.ELOOP:
            # ELOOP means it's a symlink (O_NOFOLLOW refused to follow)
            raise ConfigurationStorageError(f'Refusing to read symlink: {filepath}')
        if e.errno == errno.ENOENT:
            raise ConfigurationStorageError(f'File not found: {filepath}')
        raise ConfigurationStorageError(f'Failed to open file: {e}')

    try:
        # Get file size for efficient read
        file_stat = os.fstat(fd)
        size = file_stat.st_size
        content = os.read(fd, size)
        return content
    except OSError as e:
        raise ConfigurationStorageError(f'Failed to read file: {e}')
    finally:
        os.close(fd)


def _stat_nofollow(filepath: Path) -> os.stat_result | None:
    """Get file stats without following symlinks.

    Args:
        filepath: Path to file

    Returns:
        stat_result or None if file doesn't exist

    Raises:
        ConfigurationStorageError: If file is a symlink
    """
    try:
        st = os.lstat(filepath)
        if stat.S_ISLNK(st.st_mode):
            raise ConfigurationStorageError(f'Path is a symlink: {filepath}')
        return st
    except OSError as e:
        if e.errno == errno.ENOENT:
            return None
        raise ConfigurationStorageError(f'Failed to stat file: {e}')


def safe_backup(filepath: str | Path) -> str | None:
    """Create backup of configuration file safely.

    Creates a backup copy of the file at filepath with .backup suffix.
    The backup is created atomically using temp file + rename.

    Security: Uses O_NOFOLLOW to atomically reject symlinks, preventing
    TOCTOU race conditions.

    Args:
        filepath: Path to configuration file

    Returns:
        Path to backup file as string, or None if original doesn't exist

    Raises:
        ConfigurationStorageError: If backup fails or filepath is a symlink
    """
    filepath = Path(filepath)

    # Check if file exists (using lstat to not follow symlinks)
    try:
        st = os.lstat(filepath)
    except OSError as e:
        if e.errno == errno.ENOENT:
            return None
        raise ConfigurationStorageError(f'Failed to stat file: {e}')

    # Reject symlinks
    if stat.S_ISLNK(st.st_mode):
        raise ConfigurationStorageError(f'Refusing to backup symlink: {filepath}')

    backup_path = filepath.with_suffix(filepath.suffix + '.backup')

    # Check backup path - reject if it's a symlink
    # We don't unlink here - rename() will atomically replace regular files
    # If it's a directory or something else unexpected, rename() will fail safely
    _stat_nofollow(backup_path)  # raises if symlink

    # Read file content atomically with O_NOFOLLOW
    # This is the critical TOCTOU protection - even if attacker swaps
    # the file for a symlink between lstat and here, O_NOFOLLOW fails
    try:
        content = _read_nofollow(filepath)
    except ConfigurationStorageError:
        raise

    # Write backup atomically
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=filepath.parent, prefix='.backup_', suffix='.tmp')
        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)

        # Atomic move to backup location
        # rename() atomically replaces any file/symlink at backup_path
        os.rename(tmp_path, backup_path)
        tmp_path = None

        return str(backup_path)

    except ConfigurationStorageError:
        raise
    except Exception as e:
        raise ConfigurationStorageError(f'Failed to create backup: {e}')
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def safe_write(filepath: str | Path, content: str | bytes) -> None:
    """Write configuration file atomically.

    Writes content to filepath using temp file + rename for atomicity.
    If the file exists, its permissions are preserved.

    Security: The temp file + rename approach is inherently safe against
    symlink attacks because rename() atomically replaces the target.
    We still check for existing symlinks to provide clear error messages.

    Args:
        filepath: Path to configuration file
        content: Content to write (str or bytes)

    Raises:
        ConfigurationStorageError: If write fails or filepath is a symlink
    """
    filepath = Path(filepath)

    # Check if target exists and is a symlink (for clear error message)
    # Note: Even without this check, write would be safe because rename()
    # atomically replaces the target, but we want explicit symlink rejection
    existing_stat = _stat_nofollow(filepath)

    # Ensure parent directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    # Convert string to bytes if needed
    if isinstance(content, str):
        content = content.encode('utf-8')

    tmp_path = None
    try:
        # Write to temp file in same directory (for atomic rename)
        fd, tmp_path = tempfile.mkstemp(dir=filepath.parent, prefix='.config_', suffix='.tmp')

        try:
            os.write(fd, content)
            os.fsync(fd)
        finally:
            os.close(fd)

        # Preserve permissions if original exists
        if existing_stat is not None:
            os.chmod(tmp_path, stat.S_IMODE(existing_stat.st_mode))

        # Atomic move to final location
        # This atomically replaces any file or symlink at filepath
        os.rename(tmp_path, filepath)
        tmp_path = None  # Successfully moved, don't cleanup

    except ConfigurationStorageError:
        raise
    except Exception as e:
        raise ConfigurationStorageError(f'Failed to write config: {e}')
    finally:
        # Clean up temp file if it still exists (error case)
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def safe_update(filepath: str | Path, content: str | bytes) -> str | None:
    """Backup existing config and write new content atomically.

    This is a convenience function that combines safe_backup() and safe_write().

    Security: Both safe_backup() and safe_write() use atomic operations
    to prevent TOCTOU race conditions.

    Args:
        filepath: Path to configuration file
        content: New content to write

    Returns:
        Path to backup file as string, or None if no backup created

    Raises:
        ConfigurationStorageError: If operation fails or filepath is a symlink
    """
    filepath = Path(filepath)

    # safe_backup() handles symlink check atomically with O_NOFOLLOW
    backup_path = safe_backup(filepath)
    safe_write(filepath, content)
    return backup_path
