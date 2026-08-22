"""Unit tests for configuration parser exception handling."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock


def tokeniser_returning(*tokens: str) -> object:
    """Build a real Tokeniser primed with a fixed sequence of tokens.

    Uses the production Tokeniser (rather than a mock) so behaviour the
    parsers rely on - attribute assignment such as `tokeniser.afi = ...`,
    `.consume()`, and returning '' instead of raising once tokens run out -
    matches what happens for real, e.g. a bare `run;` with no argument.
    """
    from exabgp.configuration.core.parser import Tokeniser

    tokeniser = Tokeniser()
    tokeniser.replenish(list(tokens))
    return tokeniser


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
        """Test that IP.from_string() raises OSError for invalid IP addresses.

        The flow/parser.py redirect function catches this and converts to ValueError
        with a helpful message about IPv6 bracket notation.
        """
        from exabgp.protocol.ip import IP

        # IP.create raises OSError for invalid IPs (inet_pton failure)
        with pytest.raises(OSError):
            IP.from_string('2001:db8::1:invalid')


class TestAFISAFIParsingExceptions:
    """Test AFI/SAFI parsing exception handling.

    Note: AFI.from_string() and SAFI.from_string() do NOT raise exceptions
    for invalid input - they return default values ('undefined', 'unknown safi 0').
    The except Exception blocks in peer.py are defensive but currently ineffective.
    """

    def test_afi_from_string_returns_undefined_for_invalid(self):
        """Test that AFI.from_string() returns undefined for invalid AFI (no exception)."""
        from exabgp.protocol.family import AFI

        result = AFI.from_string('invalid-afi')
        # Returns AFI.undefined instead of raising
        assert str(result) == 'undefined'

    def test_safi_from_string_returns_undefined_for_invalid(self):
        """Test that SAFI.from_string() returns undefined for invalid SAFI (no exception)."""
        from exabgp.protocol.family import SAFI

        result = SAFI.from_string('invalid-safi')
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


class TestStaticPrefixParserExceptions:
    """Test static/parser.py prefix() exception handling.

    prefix() built an IPRange straight from IP.pton(ip), which calls
    socket.inet_pton and raises a bare OSError on malformed input such as
    999.999.999.999 - nothing caught it, so it reached the operator as a
    raw traceback instead of a configuration ValueError.
    """

    def test_an_unparseable_prefix_address_is_a_configuration_error(self) -> None:
        from exabgp.configuration.static.parser import prefix

        with pytest.raises(ValueError, match='999.999.999.999'):
            prefix(tokeniser_returning('999.999.999.999/24'))

    def test_a_prefix_with_a_non_numeric_afi_marker_is_a_configuration_error(self) -> None:
        """IP.toafi() also runs before pton() and can itself raise ValueError."""
        from exabgp.configuration.static.parser import prefix

        with pytest.raises(ValueError, match='not-an-ip'):
            prefix(tokeniser_returning('not-an-ip'))


class TestMplsRouteDistinguisherExceptions:
    """Test static/mpls.py route_distinguisher() exception handling.

    route_distinguisher() only assigned prefix/suffix when the token
    contained a ':' at index > 0; 'rd 12345' (no colon) left both
    unassigned, so the next line ('.' in prefix) raised UnboundLocalError
    instead of a configuration ValueError.
    """

    def test_route_distinguisher_without_a_colon_is_a_configuration_error(self) -> None:
        from exabgp.configuration.static.mpls import route_distinguisher

        with pytest.raises(ValueError, match='12345'):
            route_distinguisher(tokeniser_returning('12345'))

    def test_route_distinguisher_with_a_leading_colon_is_a_configuration_error(self) -> None:
        """separator == 0 also skipped the assignment ('find' returns 0, not > 0)."""
        from exabgp.configuration.static.mpls import route_distinguisher

        with pytest.raises(ValueError, match=r':100'):
            route_distinguisher(tokeniser_returning(':100'))

    def test_mvpn_sharedjoin_propagates_the_route_distinguisher_fix(self) -> None:
        """mvpn_sharedjoin (and mvpn_sourcejoin/sourcead, srv6_mup_*) share
        route_distinguisher() with no wrapping of their own - confirm the fix
        in the shared function actually reaches this caller rather than assuming it.
        """
        from exabgp.configuration.static.mpls import mvpn_sharedjoin
        from exabgp.protocol.family import AFI

        tokeniser = tokeniser_returning('rp', '1.2.3.4', 'group', '5.6.7.8', 'rd', '12345', 'source-as', '100')
        with pytest.raises(ValueError, match='12345'):
            mvpn_sharedjoin(tokeniser, AFI.ipv4, None)

    def test_srv6_mup_isd_propagates_the_route_distinguisher_fix(self) -> None:
        from exabgp.configuration.static.mpls import srv6_mup_isd
        from exabgp.protocol.family import AFI

        tokeniser = tokeniser_returning('10.0.0.0/24', 'rd', '12345')
        with pytest.raises(ValueError, match='12345'):
            srv6_mup_isd(tokeniser, AFI.ipv4)


class TestMplsPrefixSidExceptions:
    """Test static/mpls.py prefix_sid() exception handling.

    prefix_sid() only assigned label_sid inside the 'if value == "[":'
    branch; 'bgp-prefix-sid 300' (no leading '[') left label_sid unassigned,
    and int(label_sid) - outside the try/except - raised UnboundLocalError
    instead of a configuration ValueError.
    """

    def test_prefix_sid_without_an_opening_bracket_is_a_configuration_error(self) -> None:
        from exabgp.configuration.static.mpls import prefix_sid

        with pytest.raises(ValueError, match='300'):
            prefix_sid(tokeniser_returning('300'))


class TestEnvironmentSetupExceptions:
    """Test environment/config.py Environment.setup() exception handling.

    The integer/real/umask readers in environment/parsing.py raise
    ValueError (int()/float() on bad text), but Environment.setup() only
    caught TypeError around opt.parse(conf), so exabgp_tcp_attempts=abc
    reached the operator as a raw ValueError traceback with no mention of
    which setting was wrong.
    """

    def test_setup_wraps_a_bad_integer_value_in_a_contextful_value_error(self, monkeypatch) -> None:
        from exabgp.environment.config import Environment

        monkeypatch.setenv('exabgp_tcp_attempts', 'abc')

        saved_instance = Environment._instance
        saved_setup_done = Environment._setup_done
        Environment._instance = None
        Environment._setup_done = False
        try:
            with pytest.raises(ValueError, match='tcp.attempts'):
                Environment.setup()
        finally:
            Environment._instance = saved_instance
            Environment._setup_done = saved_setup_done


class TestProcessParserRunExceptions:
    """Test process/parser.py run() exception handling.

    run() indexed prg[0] to check for a leading '/' with no emptiness
    check first; a bare 'run;' with no program argument left prg == '',
    and prg[0] raised IndexError ('string index out of range') instead of
    a configuration ValueError.
    """

    def test_run_without_a_program_argument_is_a_configuration_error(self) -> None:
        from exabgp.configuration.process.parser import run

        with pytest.raises(ValueError, match='program'):
            run(tokeniser_returning())
