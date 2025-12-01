"""Tests for exabgp.application.version module.

Tests version display functionality.
"""

from __future__ import annotations

import argparse
from io import StringIO
from unittest.mock import patch


from exabgp.application.version import setargs, cmdline
from exabgp.version import version


class TestSetargs:
    """Test the argument parser setup for version."""

    def test_setargs_creates_valid_parser(self) -> None:
        """setargs should create a valid argument parser (no extra args)."""
        parser = argparse.ArgumentParser()
        setargs(parser)

        # Should be able to parse empty args
        args = parser.parse_args([])
        assert args is not None


class TestCmdline:
    """Test the cmdline function."""

    def test_cmdline_outputs_version(self) -> None:
        """Should output ExaBGP version."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        assert 'ExaBGP' in output
        assert version in output

    def test_cmdline_outputs_python_version(self) -> None:
        """Should output Python version."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        assert 'Python' in output

    def test_cmdline_outputs_uname(self) -> None:
        """Should output uname information."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        assert 'Uname' in output

    def test_cmdline_outputs_root_path(self) -> None:
        """Should output installation root path."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        assert 'From' in output

    def test_cmdline_output_format(self) -> None:
        """Output should have expected format with colons."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args)
            output = mock_stdout.getvalue()

        lines = output.strip().split('\n')
        assert len(lines) == 4

        # Each line should have format "Label : value"
        for line in lines:
            assert ' : ' in line
