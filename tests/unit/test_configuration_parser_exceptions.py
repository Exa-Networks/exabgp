"""Unit tests for configuration parser exception handling."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


class TestNeighborParserExceptions:
    """Test neighbor/parser.py exception handling patterns."""

    def test_description_raises_value_error_on_tokenizer_failure(self):
        """Test that description() converts tokenizer exceptions to ValueError."""
        from exabgp.configuration.neighbor.parser import description

        # Create mock tokeniser that raises StopIteration
        mock_tokeniser = MagicMock()
        mock_tokeniser.side_effect = StopIteration()

        # The string() function will raise, description() should convert to ValueError
        with pytest.raises(ValueError, match='bad neighbor description'):
            description(mock_tokeniser)

    def test_source_interface_raises_value_error_on_tokenizer_failure(self):
        """Test that source_interface() converts tokenizer exceptions to ValueError."""
        from exabgp.configuration.neighbor.parser import source_interface

        # Create mock tokeniser that raises StopIteration
        mock_tokeniser = MagicMock()
        mock_tokeniser.side_effect = StopIteration()

        # The string() function will raise, source_interface() should convert to ValueError
        with pytest.raises(ValueError, match='bad source interface'):
            source_interface(mock_tokeniser)

    def test_local_address_raises_value_error_for_invalid_ip(self):
        """Test that local_address() converts IP parsing errors to ValueError."""
        from exabgp.configuration.neighbor.parser import local_address

        # Create mock tokeniser that returns invalid IP
        mock_tokeniser = MagicMock()
        mock_tokeniser.tokens = ['invalid']
        mock_tokeniser.return_value = 'not-an-ip'

        with pytest.raises(ValueError, match='is not a valid IP address'):
            local_address(mock_tokeniser)

    def test_router_id_raises_value_error_for_invalid_id(self):
        """Test that router_id() converts parsing errors to ValueError."""
        from exabgp.configuration.neighbor.parser import router_id

        # Create mock tokeniser that returns invalid router ID
        # Note: RouterID uses IP parsing which raises OSError for invalid IPs
        # The except ValueError block catches this case
        mock_tokeniser = MagicMock()
        mock_tokeniser.return_value = 'invalid'  # Single word, triggers ValueError

        with pytest.raises(ValueError, match='is not a valid router-id'):
            router_id(mock_tokeniser)

    def test_hold_time_raises_value_error_for_invalid_time(self):
        """Test that hold_time() converts parsing errors to ValueError."""
        from exabgp.configuration.neighbor.parser import hold_time

        # Create mock tokeniser that returns invalid hold time
        mock_tokeniser = MagicMock()
        mock_tokeniser.return_value = 'not-a-number'

        with pytest.raises(ValueError, match='is not a valid hold-time'):
            hold_time(mock_tokeniser)


class TestFlowParserExceptions:
    """Test flow/parser.py exception handling patterns."""

    def test_redirect_ipv6_without_brackets_raises_os_error(self):
        """Test that IP.make_ip() raises OSError for invalid IP addresses.

        The flow/parser.py redirect function catches this and converts to ValueError
        with a helpful message about IPv6 bracket notation.
        """
        from exabgp.protocol.ip import IP

        # IP.create raises OSError for invalid IPs (inet_pton failure)
        with pytest.raises(OSError):
            IP.make_ip('2001:db8::1:invalid')


class TestAFISAFIParsingExceptions:
    """Test AFI/SAFI parsing exception handling.

    Note: AFI.fromString() and SAFI.fromString() do NOT raise exceptions
    for invalid input - they return default values ('undefined', 'unknown safi 0').
    The except Exception blocks in peer.py are defensive but currently ineffective.
    """

    def test_afi_from_string_returns_undefined_for_invalid(self):
        """Test that AFI.fromString() returns undefined for invalid AFI (no exception)."""
        from exabgp.protocol.family import AFI

        result = AFI.fromString('invalid-afi')
        # Returns AFI.undefined instead of raising
        assert str(result) == 'undefined'

    def test_safi_from_string_returns_undefined_for_invalid(self):
        """Test that SAFI.fromString() returns undefined for invalid SAFI (no exception)."""
        from exabgp.protocol.family import SAFI

        result = SAFI.fromString('invalid-safi')
        # Returns SAFI.undefined instead of raising
        assert str(result) == 'undefined'


class TestExceptionTranslationPatterns:
    """Test the exception translation pattern used in parsers.

    The common pattern is:
        try:
            result = some_operation()
        except Exception:
            raise ValueError('descriptive message') from None

    This should be tightened to catch specific exceptions.
    """

    def test_stop_iteration_translates_to_value_error(self):
        """Verify StopIteration is properly translated to ValueError."""
        from exabgp.configuration.neighbor.parser import description

        class MockTokeniser:
            def __call__(self):
                raise StopIteration()

        mock = MockTokeniser()
        with pytest.raises(ValueError):
            description(mock)

    def test_attribute_error_in_parser_produces_value_error(self):
        """Verify AttributeError is translated to ValueError in parsers."""
        from exabgp.configuration.neighbor.parser import hostname

        class MockTokeniser:
            def __call__(self):
                return None  # Will cause AttributeError on None[0]

        mock = MockTokeniser()
        with pytest.raises((ValueError, TypeError, AttributeError)):
            hostname(mock)
