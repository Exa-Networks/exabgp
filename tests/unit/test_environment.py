# encoding: utf-8
"""test_environment.py

Unit tests for exabgp.environment modules
"""

from unittest.mock import patch

from typing import Any

from exabgp.environment.hashtable import HashTable, GlobalHashTable
from exabgp.environment.base import _find_root, APPLICATION, ROOT


class TestHashTable:
    """Test HashTable class"""

    def test_hashtable_init(self) -> None:
        """Test HashTable initialization"""
        h = HashTable()
        assert isinstance(h, dict)

    def test_hashtable_setitem(self) -> None:
        """Test HashTable __setitem__ with underscore replacement"""
        h = HashTable()
        h['test_key'] = 'value'
        # Underscore should be replaced with dash
        assert 'test-key' in h
        assert h['test_key'] == 'value'

    def test_hashtable_getitem(self) -> None:
        """Test HashTable __getitem__ with underscore replacement"""
        h = HashTable()
        h['test_key'] = 'value'
        # Can access with underscores
        assert h['test_key'] == 'value'
        # Can also access with dashes
        assert h['test-key'] == 'value'

    def test_hashtable_setattr(self) -> None:
        """Test HashTable __setattr__ attribute-style access"""
        h = HashTable()
        h.test_key = 'value'
        # Should be stored with dashes
        assert 'test-key' in h
        assert h.test_key == 'value'

    def test_hashtable_getattr(self) -> None:
        """Test HashTable __getattr__ attribute-style access"""
        h = HashTable()
        h['test_key'] = 'value'
        # Can access via attribute
        assert h.test_key == 'value'

    def test_hashtable_no_underscore(self) -> None:
        """Test HashTable with keys without underscores"""
        h = HashTable()
        h['testkey'] = 'value'
        assert h['testkey'] == 'value'
        assert h.testkey == 'value'

    def test_hashtable_multiple_underscores(self) -> None:
        """Test HashTable with multiple underscores"""
        h = HashTable()
        h['test_key_name'] = 'value'
        # All underscores replaced
        assert 'test-key-name' in h
        assert h['test_key_name'] == 'value'


class TestGlobalHashTable:
    """Test GlobalHashTable (singleton) class"""

    def test_globalhash_singleton(self) -> None:
        """Test GlobalHashTable is a singleton"""
        h1 = GlobalHashTable()
        h2 = GlobalHashTable()
        # Should be the same instance
        assert h1 is h2

    def test_globalhash_shared_state(self) -> None:
        """Test GlobalHashTable shares state across instances"""
        h1 = GlobalHashTable()
        h2 = GlobalHashTable()

        h1['test_key'] = 'value1'
        # h2 should see the same value
        assert h2['test_key'] == 'value1'

        h2['test_key'] = 'value2'
        # h1 should see the updated value
        assert h1['test_key'] == 'value2'

    def test_globalhash_inheritance(self) -> None:
        """Test GlobalHashTable inherits HashTable behavior"""
        h = GlobalHashTable()
        h['test_key'] = 'value'
        # Should use underscore replacement
        assert 'test-key' in h
        assert h.test_key == 'value'


class TestBase:
    """Test base module functions"""

    def test_application_constant(self) -> None:
        """Test APPLICATION constant"""
        assert APPLICATION == 'exabgp'

    def test_root_is_string(self) -> None:
        """Test ROOT is a string path"""
        assert isinstance(ROOT, str)
        assert len(ROOT) > 0

    @patch('os.environ.get')
    @patch('sys.argv', ['/usr/local/bin/exabgp'])
    def test_find_root_from_argv(self, mock_env_get: Any) -> None:
        """Test _find_root() uses sys.argv when EXABGP_ROOT not set"""
        mock_env_get.return_value = ''
        root = _find_root()
        assert isinstance(root, str)
        # Should be normalized path
        assert not root.endswith('/')

    @patch('os.environ.get')
    def test_find_root_from_env(self, mock_env_get: Any) -> None:
        """Test _find_root() uses EXABGP_ROOT environment variable"""
        mock_env_get.return_value = '/custom/exabgp/path'
        root = _find_root()
        # Should use the environment variable
        assert '/custom/exabgp/path' in root or root == '/custom/exabgp/path'

    @patch('os.environ.get')
    @patch('sys.argv', ['/usr/local/bin/exabgp'])
    def test_find_root_strips_bin(self, mock_env_get: Any) -> None:
        """Test _find_root() strips /bin and /sbin from path"""
        mock_env_get.return_value = ''
        root = _find_root()
        # Should not end with /bin or /sbin
        assert not root.endswith('/bin')
        assert not root.endswith('/sbin')

    @patch('os.environ.get')
    @patch('sys.argv', ['/home/user/exabgp/src/exabgp/application/main.py'])
    def test_find_root_strips_app_folder(self, mock_env_get: Any) -> None:
        """Test _find_root() strips application folder from path"""
        mock_env_get.return_value = ''
        root = _find_root()
        # Should not contain application folder
        assert not root.endswith('src/exabgp/application')

    @patch('os.environ.get')
    @patch('sys.argv', ['/path/to/exabgp/'])
    def test_find_root_strips_trailing_slash(self, mock_env_get: Any) -> None:
        """Test _find_root() removes trailing slash"""
        mock_env_get.return_value = ''
        root = _find_root()
        # Should not end with slash
        assert not root.endswith('/')
