"""Tests for exabgp.application.environ module.

Tests environment variable display functionality.
"""

from __future__ import annotations

import argparse
from io import StringIO
from unittest.mock import patch


from exabgp.application.environ import setargs, cmdline, default
from exabgp.environment import Env


class TestSetargs:
    """Test the argument parser setup for environ."""

    def test_setargs_creates_valid_parser(self) -> None:
        """setargs should create a valid argument parser."""
        parser = argparse.ArgumentParser()
        setargs(parser)

        args = parser.parse_args([])
        assert hasattr(args, 'diff')
        assert hasattr(args, 'env')

    def test_setargs_default_values(self) -> None:
        """Default values should be False."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        assert args.diff is False
        assert args.env is False

    def test_setargs_diff_flag(self) -> None:
        """--diff flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-d'])

        assert args.diff is True

    def test_setargs_env_flag(self) -> None:
        """--env flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-e'])

        assert args.env is True

    def test_setargs_both_flags(self) -> None:
        """Both flags should work together."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-d', '-e'])

        assert args.diff is True
        assert args.env is True


class TestCmdline:
    """Test the cmdline function."""

    def test_cmdline_ini_format(self) -> None:
        """Default output should be ini format."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        # Should have output
        assert len(output) > 0

    def test_cmdline_env_format(self) -> None:
        """--env should output environment variable format."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-e'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        # Environment format uses exabgp_ prefix
        # Should have output
        assert len(output) > 0

    def test_cmdline_diff_mode(self) -> None:
        """--diff should show only non-default values."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-d'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        # Output may be empty if all values are defaults
        # Just verify it doesn't crash
        assert output is not None


class TestDefault:
    """Test the default function."""

    def test_default_outputs_header(self) -> None:
        """default() should output header text."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            default()
            output = mock_stdout.getvalue()

        assert 'Environment values are:' in output

    def test_default_outputs_values(self) -> None:
        """default() should output environment values."""
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            default()
            output = mock_stdout.getvalue()

        # Should have multiple lines
        lines = output.strip().split('\n')
        assert len(lines) > 1


class TestEnvClass:
    """Test the Env class methods used by environ."""

    def test_env_default_returns_list(self) -> None:
        """Env.default() should return iterable."""
        defaults = list(Env.default())
        assert len(defaults) > 0

    def test_env_iter_ini_returns_iterable(self) -> None:
        """Env.iter_ini() should return iterable."""
        lines = list(Env.iter_ini(diff=False))
        assert len(lines) > 0

    def test_env_iter_env_returns_iterable(self) -> None:
        """Env.iter_env() should return iterable."""
        lines = list(Env.iter_env(diff=False))
        assert len(lines) > 0

    def test_env_iter_ini_diff_mode(self) -> None:
        """Env.iter_ini(diff=True) should work."""
        # May return empty if all defaults
        lines = list(Env.iter_ini(diff=True))
        assert isinstance(lines, list)

    def test_env_iter_env_diff_mode(self) -> None:
        """Env.iter_env(diff=True) should work."""
        # May return empty if all defaults
        lines = list(Env.iter_env(diff=True))
        assert isinstance(lines, list)
