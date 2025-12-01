"""Tests for exabgp.application.validate module.

Tests configuration validation functionality.
"""

from __future__ import annotations

import argparse
import tempfile
import os

import pytest

from exabgp.application.validate import setargs, cmdline


class TestSetargs:
    """Test the argument parser setup for validate."""

    def test_setargs_creates_valid_parser(self) -> None:
        """setargs should create a valid argument parser."""
        parser = argparse.ArgumentParser()
        setargs(parser)

        # Should have the expected arguments
        args = parser.parse_args(['test.conf'])
        assert hasattr(args, 'neighbor')
        assert hasattr(args, 'route')
        assert hasattr(args, 'verbose')
        assert hasattr(args, 'pdb')
        assert hasattr(args, 'configuration')

    def test_setargs_default_values(self) -> None:
        """Default values should be False for flags."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['test.conf'])

        assert args.neighbor is False
        assert args.route is False
        assert args.verbose is False
        assert args.pdb is False

    def test_setargs_neighbor_flag(self) -> None:
        """--neighbor flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-n', 'test.conf'])

        assert args.neighbor is True

    def test_setargs_route_flag(self) -> None:
        """--route flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-r', 'test.conf'])

        assert args.route is True

    def test_setargs_verbose_flag(self) -> None:
        """--verbose flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-v', 'test.conf'])

        assert args.verbose is True

    def test_setargs_multiple_configs(self) -> None:
        """Should accept multiple configuration files."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['config1.conf', 'config2.conf', 'config3.conf'])

        assert args.configuration == ['config1.conf', 'config2.conf', 'config3.conf']

    def test_setargs_all_flags(self) -> None:
        """All flags together should work."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-n', '-r', '-v', '-p', 'test.conf'])

        assert args.neighbor is True
        assert args.route is True
        assert args.verbose is True
        assert args.pdb is True


class TestCmdline:
    """Test the cmdline function."""

    @pytest.fixture
    def valid_config(self) -> str:
        """Create a temporary valid configuration file."""
        config_content = """
neighbor 127.0.0.1 {
    router-id 10.0.0.1;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65001;
}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write(config_content)
            return f.name

    @pytest.fixture
    def invalid_config(self) -> str:
        """Create a temporary invalid configuration file."""
        config_content = """
this is not valid bgp configuration
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write(config_content)
            return f.name

    def test_cmdline_with_nonexistent_file(self) -> None:
        """Should exit with error for nonexistent file."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['/nonexistent/path/to/config.conf'])

        with pytest.raises(SystemExit) as exc_info:
            cmdline(args)

        assert exc_info.value.code == 1

    def test_cmdline_with_valid_config(self, valid_config: str) -> None:
        """Should succeed with valid configuration."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([valid_config])

        # Should not raise
        try:
            cmdline(args)
        except SystemExit as e:
            # If it exits, should be success (0) or not exit at all
            if e.code is not None and e.code != 0:
                pytest.fail(f'cmdline exited with non-zero code: {e.code}')
        finally:
            os.unlink(valid_config)

    def test_cmdline_with_invalid_config(self, invalid_config: str) -> None:
        """Should exit with error for invalid configuration."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([invalid_config])

        with pytest.raises(SystemExit) as exc_info:
            cmdline(args)

        assert exc_info.value.code == 1
        os.unlink(invalid_config)

    def test_cmdline_with_verbose(self, valid_config: str) -> None:
        """Verbose mode should enable debug logging."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-v', valid_config])

        # Should not raise
        try:
            cmdline(args)
        except SystemExit as e:
            if e.code is not None and e.code != 0:
                pytest.fail(f'cmdline exited with non-zero code: {e.code}')
        finally:
            os.unlink(valid_config)
