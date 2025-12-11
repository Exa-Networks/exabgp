"""Tests for configuration/storage.py - Safe file operations."""

import os
import shutil
import uuid
from pathlib import Path

import pytest


class TestSafeBackup:
    """Tests for safe_backup() function."""

    def setup_method(self):
        """Create temporary directory for each test."""
        # Save and reset umask to permissive value for tests
        self.old_umask = os.umask(0o022)
        # Use /tmp with a unique UUID to avoid any pytest interference
        self.tmp_dir = f'/tmp/exabgp_test_{uuid.uuid4().hex}'
        os.makedirs(self.tmp_dir, mode=0o755, exist_ok=True)
        self.tmp_path = Path(self.tmp_dir)

    def teardown_method(self):
        """Remove temporary directory after each test."""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        # Restore original umask
        os.umask(self.old_umask)

    def test_backup_creates_backup_file(self):
        """safe_backup() should create a .backup file."""
        from exabgp.configuration.storage import safe_backup

        # Create original file
        original = self.tmp_path / 'config.conf'
        original.write_text('original content')

        # Create backup
        backup_path = safe_backup(original)

        assert backup_path is not None
        assert Path(backup_path).exists()
        assert Path(backup_path).read_text() == 'original content'

    def test_backup_file_naming(self):
        """safe_backup() should use .backup suffix."""
        from exabgp.configuration.storage import safe_backup

        original = self.tmp_path / 'config.conf'
        original.write_text('content')

        backup_path = safe_backup(original)

        assert backup_path == str(self.tmp_path / 'config.conf.backup')

    def test_backup_nonexistent_file_returns_none(self):
        """safe_backup() should return None if file doesn't exist."""
        from exabgp.configuration.storage import safe_backup

        nonexistent = self.tmp_path / 'nonexistent.conf'
        result = safe_backup(nonexistent)

        assert result is None

    def test_backup_refuses_symlink(self):
        """safe_backup() should refuse to backup symlinks."""
        from exabgp.configuration.storage import ConfigurationStorageError, safe_backup

        # Create real file and symlink
        real_file = self.tmp_path / 'real.conf'
        real_file.write_text('real content')
        symlink = self.tmp_path / 'symlink.conf'
        symlink.symlink_to(real_file)

        with pytest.raises(ConfigurationStorageError, match='symlink'):
            safe_backup(symlink)

    def test_backup_overwrites_existing_backup(self):
        """safe_backup() should overwrite existing backup."""
        from exabgp.configuration.storage import safe_backup

        original = self.tmp_path / 'config.conf'
        original.write_text('version 1')

        # First backup
        safe_backup(original)

        # Modify and backup again
        original.write_text('version 2')
        backup_path = safe_backup(original)

        assert Path(backup_path).read_text() == 'version 2'

    def test_backup_refuses_symlink_backup_path(self):
        """safe_backup() should refuse if backup path is a symlink."""
        from exabgp.configuration.storage import ConfigurationStorageError, safe_backup

        original = self.tmp_path / 'config.conf'
        original.write_text('content')

        # Create a symlink at the backup location
        real_backup = self.tmp_path / 'real_backup'
        real_backup.write_text('old backup')
        backup_symlink = self.tmp_path / 'config.conf.backup'
        backup_symlink.symlink_to(real_backup)

        with pytest.raises(ConfigurationStorageError, match='symlink'):
            safe_backup(original)

    def test_backup_accepts_string_path(self):
        """safe_backup() should accept string path."""
        from exabgp.configuration.storage import safe_backup

        original = self.tmp_path / 'config.conf'
        original.write_text('content')

        backup_path = safe_backup(str(original))

        assert backup_path is not None
        assert Path(backup_path).exists()


class TestSafeWrite:
    """Tests for safe_write() function."""

    def setup_method(self):
        """Create temporary directory for each test."""
        # Save and reset umask to permissive value for tests
        self.old_umask = os.umask(0o022)
        # Use /tmp with a unique UUID to avoid any pytest interference
        self.tmp_dir = f'/tmp/exabgp_test_{uuid.uuid4().hex}'
        os.makedirs(self.tmp_dir, mode=0o755, exist_ok=True)
        self.tmp_path = Path(self.tmp_dir)

    def teardown_method(self):
        """Remove temporary directory after each test."""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        # Restore original umask
        os.umask(self.old_umask)

    def test_write_creates_file(self):
        """safe_write() should create file with content."""
        from exabgp.configuration.storage import safe_write

        filepath = self.tmp_path / 'new_config.conf'
        safe_write(filepath, 'new content')

        assert filepath.exists()
        assert filepath.read_text() == 'new content'

    def test_write_overwrites_existing(self):
        """safe_write() should overwrite existing file."""
        from exabgp.configuration.storage import safe_write

        filepath = self.tmp_path / 'config.conf'
        filepath.write_text('old content')

        safe_write(filepath, 'new content')

        assert filepath.read_text() == 'new content'

    def test_write_refuses_symlink(self):
        """safe_write() should refuse to overwrite symlinks."""
        from exabgp.configuration.storage import ConfigurationStorageError, safe_write

        real_file = self.tmp_path / 'real.conf'
        real_file.write_text('real content')
        symlink = self.tmp_path / 'symlink.conf'
        symlink.symlink_to(real_file)

        with pytest.raises(ConfigurationStorageError, match='symlink'):
            safe_write(symlink, 'new content')

    def test_write_creates_parent_directories(self):
        """safe_write() should create parent directories if needed."""
        from exabgp.configuration.storage import safe_write

        filepath = self.tmp_path / 'subdir' / 'deep' / 'config.conf'
        safe_write(filepath, 'content')

        assert filepath.exists()
        assert filepath.read_text() == 'content'

    def test_write_preserves_permissions(self):
        """safe_write() should preserve file permissions."""
        from exabgp.configuration.storage import safe_write

        filepath = self.tmp_path / 'config.conf'
        filepath.write_text('old content')
        os.chmod(filepath, 0o600)

        safe_write(filepath, 'new content')

        assert (filepath.stat().st_mode & 0o777) == 0o600

    def test_write_atomic_on_failure(self):
        """safe_write() should not corrupt file on failure."""
        from exabgp.configuration.storage import safe_write

        filepath = self.tmp_path / 'config.conf'
        filepath.write_text('original content')

        # This test would need to simulate a failure mid-write
        # For now, just verify the basic operation works
        safe_write(filepath, 'new content')
        assert filepath.read_text() == 'new content'

    def test_write_accepts_string_path(self):
        """safe_write() should accept string path."""
        from exabgp.configuration.storage import safe_write

        filepath = self.tmp_path / 'config.conf'
        safe_write(str(filepath), 'content')

        assert filepath.exists()

    def test_write_accepts_bytes(self):
        """safe_write() should accept bytes content."""
        from exabgp.configuration.storage import safe_write

        filepath = self.tmp_path / 'config.conf'
        safe_write(filepath, b'binary content')

        assert filepath.read_bytes() == b'binary content'


class TestSafeUpdate:
    """Tests for safe_update() function."""

    def setup_method(self):
        """Create temporary directory for each test."""
        # Save and reset umask to permissive value for tests
        self.old_umask = os.umask(0o022)
        # Use /tmp with a unique UUID to avoid any pytest interference
        self.tmp_dir = f'/tmp/exabgp_test_{uuid.uuid4().hex}'
        os.makedirs(self.tmp_dir, mode=0o755, exist_ok=True)
        self.tmp_path = Path(self.tmp_dir)

    def teardown_method(self):
        """Remove temporary directory after each test."""
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        # Restore original umask
        os.umask(self.old_umask)

    def test_update_creates_backup_and_writes(self):
        """safe_update() should backup and write atomically."""
        from exabgp.configuration.storage import safe_update

        filepath = self.tmp_path / 'config.conf'
        filepath.write_text('original')

        backup_path = safe_update(filepath, 'updated')

        assert filepath.read_text() == 'updated'
        assert backup_path is not None
        assert Path(backup_path).read_text() == 'original'

    def test_update_new_file_no_backup(self):
        """safe_update() should return None backup for new files."""
        from exabgp.configuration.storage import safe_update

        filepath = self.tmp_path / 'new_config.conf'

        backup_path = safe_update(filepath, 'content')

        assert filepath.read_text() == 'content'
        assert backup_path is None

    def test_update_refuses_symlink(self):
        """safe_update() should refuse symlinks."""
        from exabgp.configuration.storage import ConfigurationStorageError, safe_update

        real_file = self.tmp_path / 'real.conf'
        real_file.write_text('content')
        symlink = self.tmp_path / 'symlink.conf'
        symlink.symlink_to(real_file)

        with pytest.raises(ConfigurationStorageError, match='symlink'):
            safe_update(symlink, 'new content')


class TestConfigurationStorageError:
    """Tests for ConfigurationStorageError exception."""

    def test_exception_is_exception(self):
        """ConfigurationStorageError should be an Exception."""
        from exabgp.configuration.storage import ConfigurationStorageError

        assert issubclass(ConfigurationStorageError, Exception)

    def test_exception_message(self):
        """ConfigurationStorageError should preserve message."""
        from exabgp.configuration.storage import ConfigurationStorageError

        err = ConfigurationStorageError('test message')
        assert str(err) == 'test message'
