# encoding: utf-8
"""test_environment.py

Unit tests for exabgp.environment modules
"""

from unittest.mock import patch

from typing import Any

from exabgp.environment import getenv, Environment
from exabgp.environment.base import _find_root, APPLICATION, ROOT
from exabgp.environment.config import ConfigSection, option


class TestConfigOption:
    """Test ConfigOption descriptor"""

    def test_option_default(self) -> None:
        """Test ConfigOption returns default value"""

        class TestSection(ConfigSection):
            _section_name = 'test'
            value: bool = option(True, 'test option')

        section = TestSection()
        assert section.value is True

    def test_option_set(self) -> None:
        """Test ConfigOption can be set"""

        class TestSection(ConfigSection):
            _section_name = 'test'
            value: str = option('default', 'test option')

        section = TestSection()
        section.value = 'modified'
        assert section.value == 'modified'

    def test_option_dict_access(self) -> None:
        """Test ConfigSection supports dict-style access"""

        class TestSection(ConfigSection):
            _section_name = 'test'
            test_key: str = option('value', 'test option')

        section = TestSection()
        assert section['test_key'] == 'value'
        # Also test with dash (underscore replacement)
        assert section['test-key'] == 'value'

    def test_option_dict_set(self) -> None:
        """Test ConfigSection supports dict-style setting"""

        class TestSection(ConfigSection):
            _section_name = 'test'
            test_key: str = option('default', 'test option')

        section = TestSection()
        section['test_key'] = 'modified'
        assert section.test_key == 'modified'

    def test_option_contains(self) -> None:
        """Test ConfigSection supports 'in' operator"""

        class TestSection(ConfigSection):
            _section_name = 'test'
            test_key: str = option('value', 'test option')

        section = TestSection()
        assert 'test_key' in section
        assert 'test-key' in section
        assert 'nonexistent' not in section


class TestEnvironment:
    """Test Environment singleton class"""

    def test_environment_singleton(self) -> None:
        """Test Environment is a singleton"""
        e1 = Environment()
        e2 = Environment()
        assert e1 is e2

    def test_environment_sections(self) -> None:
        """Test Environment has all expected sections"""
        env = getenv()
        expected = ['profile', 'pdb', 'daemon', 'log', 'tcp', 'bgp', 'cache', 'api', 'reactor', 'debug']
        for section in expected:
            assert hasattr(env, section), f'Missing section: {section}'

    def test_environment_api_section(self) -> None:
        """Test Environment API section has expected options"""
        env = getenv()
        assert hasattr(env.api, 'ack')
        assert hasattr(env.api, 'chunk')
        assert hasattr(env.api, 'encoder')
        assert hasattr(env.api, 'cli')

    def test_environment_dict_access(self) -> None:
        """Test Environment supports dict-style access"""
        env = getenv()
        api = env['api']
        assert api is env.api
        assert api.ack == env.api.ack

    def test_environment_contains(self) -> None:
        """Test Environment supports 'in' operator"""
        env = getenv()
        assert 'api' in env
        assert 'log' in env
        assert 'nonexistent' not in env

    def test_environment_iteration(self) -> None:
        """Test Environment supports iteration"""
        env = getenv()
        sections = list(env.keys())
        assert 'api' in sections
        assert 'log' in sections
        assert len(sections) == 10  # All 10 sections


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
