"""Tests for exabgp.application.encode module.

Tests route encoding to BGP UPDATE messages.
"""

from __future__ import annotations

import argparse
from io import StringIO
from unittest.mock import patch

import pytest

from exabgp.application.encode import setargs, cmdline


class TestSetargs:
    """Test the argument parser setup for encode."""

    def test_setargs_creates_valid_parser(self) -> None:
        """setargs should create a valid argument parser."""
        parser = argparse.ArgumentParser()
        setargs(parser)

        args = parser.parse_args([])
        assert hasattr(args, 'route')
        assert hasattr(args, 'family')
        assert hasattr(args, 'local_as')
        assert hasattr(args, 'peer_as')
        assert hasattr(args, 'path_information')
        assert hasattr(args, 'nlri_only')
        assert hasattr(args, 'no_header')
        assert hasattr(args, 'configuration')
        assert hasattr(args, 'debug')
        assert hasattr(args, 'pdb')

    def test_setargs_default_values(self) -> None:
        """Default values should be appropriate."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        assert args.route is None
        assert args.family == 'ipv4 unicast'
        assert args.local_as == 65533
        assert args.peer_as == 65533
        assert args.path_information is False
        assert args.nlri_only is False
        assert args.no_header is False
        assert args.debug is False
        assert args.pdb is False

    def test_setargs_with_route(self) -> None:
        """Route argument should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['route 10.0.0.0/24 next-hop 1.2.3.4'])

        assert args.route == 'route 10.0.0.0/24 next-hop 1.2.3.4'

    def test_setargs_with_family(self) -> None:
        """--family should accept family string."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-f', 'ipv6 unicast', 'route 2001:db8::/32 next-hop 2001:db8::1'])

        assert args.family == 'ipv6 unicast'

    def test_setargs_with_as_numbers(self) -> None:
        """AS numbers should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-a', '65000', '-z', '65001', 'route 10.0.0.0/24 next-hop 1.2.3.4'])

        assert args.local_as == 65000
        assert args.peer_as == 65001

    def test_setargs_nlri_only(self) -> None:
        """--nlri-only flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-n', 'route 10.0.0.0/24 next-hop 1.2.3.4'])

        assert args.nlri_only is True

    def test_setargs_no_header(self) -> None:
        """--no-header flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['--no-header', 'route 10.0.0.0/24 next-hop 1.2.3.4'])

        assert args.no_header is True

    def test_setargs_path_information(self) -> None:
        """--path-information flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-i', 'route 10.0.0.0/24 next-hop 1.2.3.4'])

        assert args.path_information is True


class TestCmdline:
    """Test the cmdline function."""

    def test_cmdline_simple_route(self) -> None:
        """Encode a simple IPv4 route."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['route 10.0.0.0/24 next-hop 1.2.3.4'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = cmdline(args)
            output = mock_stdout.getvalue()

        assert result == 0
        # Output should be hex string
        assert len(output.strip()) > 0
        # Should be valid hex
        hex_output = output.strip()
        assert all(c in '0123456789ABCDEF\n' for c in hex_output)

    def test_cmdline_route_with_as_path(self) -> None:
        """Encode a route with AS path."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['route 10.0.0.0/24 next-hop 1.2.3.4 as-path [65000 65001]'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = cmdline(args)
            output = mock_stdout.getvalue()

        assert result == 0
        assert len(output.strip()) > 0

    def test_cmdline_nlri_only(self) -> None:
        """Encode with NLRI-only output."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-n', 'route 10.0.0.0/24 next-hop 1.2.3.4'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = cmdline(args)
            output = mock_stdout.getvalue()

        assert result == 0
        # NLRI-only should be shorter
        # /24 network = 1 byte prefix len + 3 bytes prefix = 4 bytes = 8 hex chars
        hex_output = output.strip()
        assert len(hex_output) == 8  # 180A0000 for 10.0.0.0/24

    def test_cmdline_no_header(self) -> None:
        """Encode without BGP header."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args_with_header = parser.parse_args(['route 10.0.0.0/24 next-hop 1.2.3.4'])
        args_no_header = parser.parse_args(['--no-header', 'route 10.0.0.0/24 next-hop 1.2.3.4'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args_with_header)
            output_with_header = mock_stdout.getvalue()

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            cmdline(args_no_header)
            output_no_header = mock_stdout.getvalue()

        # Without header should be 19 bytes (38 hex chars) shorter
        assert len(output_no_header.strip()) == len(output_with_header.strip()) - 38

    def test_cmdline_ipv6_route(self) -> None:
        """Encode an IPv6 route."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-f', 'ipv6 unicast', 'route 2001:db8::/32 next-hop 2001:db8::1'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = cmdline(args)
            output = mock_stdout.getvalue()

        assert result == 0
        assert len(output.strip()) > 0

    def test_cmdline_invalid_route(self) -> None:
        """Invalid route syntax should fail."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['invalid route syntax'])

        with patch('sys.stdout', new_callable=StringIO):
            with pytest.raises(SystemExit) as exc_info:
                cmdline(args)

        assert exc_info.value.code == 1

    def test_cmdline_invalid_family(self) -> None:
        """Invalid family should fail."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-f', 'invalid', 'route 10.0.0.0/24 next-hop 1.2.3.4'])

        with patch('sys.stdout', new_callable=StringIO):
            with pytest.raises(SystemExit) as exc_info:
                cmdline(args)

        assert exc_info.value.code == 1


class TestEncodeDecodeRoundTrip:
    """Test that encode output can be decoded."""

    def test_roundtrip_simple_route(self) -> None:
        """Encoded route should be decodable."""
        from exabgp.application.decode import cmdline as decode_cmdline
        from exabgp.application.decode import setargs as decode_setargs

        # Encode
        encode_parser = argparse.ArgumentParser()
        setargs(encode_parser)
        encode_args = encode_parser.parse_args(['route 10.0.0.0/24 next-hop 1.2.3.4'])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            encode_result = cmdline(encode_args)
            encoded = mock_stdout.getvalue().strip()

        assert encode_result == 0

        # Decode
        decode_parser = argparse.ArgumentParser()
        decode_setargs(decode_parser)
        decode_args = decode_parser.parse_args([encoded])

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            decode_result = decode_cmdline(decode_args)
            decoded = mock_stdout.getvalue()

        assert decode_result == 0
        # Decoded output should contain the route info
        assert '10.0.0' in decoded or 'announce' in decoded.lower()
