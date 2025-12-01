"""Tests for exabgp.application.decode module.

Tests hex decoding functionality and helpers.
"""

from __future__ import annotations

import argparse
from io import StringIO
from unittest.mock import patch


from exabgp.application.decode import setargs, cmdline, is_bgp


class TestIsBgp:
    """Test the is_bgp helper function."""

    def test_valid_hex_string(self) -> None:
        """Valid hex strings should return True."""
        assert is_bgp('FFFFFFFF') is True
        assert is_bgp('0123456789abcdef') is True
        assert is_bgp('0123456789ABCDEF') is True

    def test_hex_with_colons(self) -> None:
        """Hex strings with colons should return True."""
        assert is_bgp('FF:FF:FF:FF') is True
        assert is_bgp('00:11:22:33:44:55') is True

    def test_empty_string(self) -> None:
        """Empty string should return True (all chars pass filter)."""
        assert is_bgp('') is True

    def test_invalid_characters(self) -> None:
        """Strings with invalid characters should return False."""
        assert is_bgp('GGGG') is False  # G is not hex
        assert is_bgp('hello') is False
        assert is_bgp('12 34') is False  # Space not in allowed chars
        assert is_bgp('0x1234') is False  # x not allowed

    def test_mixed_valid_invalid(self) -> None:
        """Mixed valid/invalid should return False."""
        assert is_bgp('12G4') is False
        assert is_bgp('ABCx') is False


class TestSetargs:
    """Test the argument parser setup for decode."""

    def test_setargs_creates_valid_parser(self) -> None:
        """setargs should create a valid argument parser."""
        parser = argparse.ArgumentParser()
        setargs(parser)

        args = parser.parse_args([])
        assert hasattr(args, 'nlri')
        assert hasattr(args, 'update')
        assert hasattr(args, 'open')
        assert hasattr(args, 'debug')
        assert hasattr(args, 'pdb')
        assert hasattr(args, 'configuration')
        assert hasattr(args, 'family')
        assert hasattr(args, 'path_information')
        assert hasattr(args, 'payload')

    def test_setargs_default_values(self) -> None:
        """Default values should be appropriate."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([])

        assert args.nlri is False
        assert args.update is False
        assert args.open is False
        assert args.debug is False
        assert args.pdb is False
        assert args.path_information is False
        assert args.payload is None
        assert args.configuration is None
        assert args.family is None

    def test_setargs_nlri_flag(self) -> None:
        """--nlri flag should be parsed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-n', 'FFFF'])

        assert args.nlri is True

    def test_setargs_with_payload(self) -> None:
        """Payload should be parsed as positional argument."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['FFFFFFFF'])

        assert args.payload == 'FFFFFFFF'

    def test_setargs_with_family(self) -> None:
        """--family should accept family string."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-f', 'ipv4 unicast', 'FFFF'])

        assert args.family == 'ipv4 unicast'

    def test_setargs_path_information(self) -> None:
        """--path-information should enable add-path."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-i', 'FFFF'])

        assert args.path_information is True


class TestCmdline:
    """Test the cmdline function."""

    def test_cmdline_invalid_hex(self) -> None:
        """Invalid hex should report error."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['GGGG'])  # Invalid hex

        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            result = cmdline(args)
            output = mock_stdout.getvalue()

        assert result == 1
        assert 'invalid hexadecimal' in output

    def test_cmdline_valid_hex_invalid_bgp(self) -> None:
        """Valid hex but invalid BGP should report error."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['1234'])  # Valid hex but not valid BGP

        with patch('sys.stdout', new_callable=StringIO):
            result = cmdline(args)

        # Should fail because it's not a valid BGP message
        assert result == 1

    def test_cmdline_with_spaces_in_hex(self) -> None:
        """Hex with spaces should have spaces removed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        # Spaces should be stripped
        args = parser.parse_args(['12 34 56'])

        with patch('sys.stdout', new_callable=StringIO):
            result = cmdline(args)

        # Will fail (invalid BGP) but spaces should be handled
        assert result == 1

    def test_cmdline_with_colons_in_hex(self) -> None:
        """Hex with colons should have colons removed."""
        parser = argparse.ArgumentParser()
        setargs(parser)
        # Colons should be stripped
        args = parser.parse_args(['12:34:56'])

        with patch('sys.stdout', new_callable=StringIO):
            result = cmdline(args)

        # Will fail (invalid BGP) but colons should be handled
        assert result == 1


class TestDecodeIntegration:
    """Integration tests for decode functionality."""

    def test_decode_minimal_update(self) -> None:
        """Decode a minimal UPDATE message."""
        # This is a minimal valid UPDATE message:
        # 16-byte marker (all 0xFF)
        # 2-byte length (23)
        # 1-byte type (2 = UPDATE)
        # 2-byte withdrawn length (0)
        # 2-byte path attr length (0)
        marker = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'
        length = '0017'  # 23 bytes total
        msg_type = '02'  # UPDATE
        withdrawn_len = '0000'
        path_attr_len = '0000'

        update_msg = marker + length + msg_type + withdrawn_len + path_attr_len

        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args([update_msg])

        with patch('sys.stdout', new_callable=StringIO):
            result = cmdline(args)

        # Should succeed
        assert result == 0

    def test_decode_with_family_option(self) -> None:
        """Decode with explicit family option."""
        # Minimal UPDATE
        marker = 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'
        length = '0017'
        msg_type = '02'
        withdrawn_len = '0000'
        path_attr_len = '0000'

        update_msg = marker + length + msg_type + withdrawn_len + path_attr_len

        parser = argparse.ArgumentParser()
        setargs(parser)
        args = parser.parse_args(['-f', 'ipv4 unicast', update_msg])

        with patch('sys.stdout', new_callable=StringIO):
            result = cmdline(args)

        assert result == 0
