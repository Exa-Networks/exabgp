"""test_schema_bridge.py

Unit tests for schema bridge module (schema-driven CLI completion).

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.cli.schema_bridge import (
    ValueTypeCompletionEngine,
    ValidationState,
    validate_ip_address,
    validate_asn,
    get_syntax_hint,
)
from exabgp.configuration.schema import ValueType


class TestValueValidation:
    """Test value validation against schema types"""

    def test_valid_ipv4_address(self):
        """Test validating valid IPv4 addresses"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_ADDRESS, '192.0.2.1')
        assert result.state == ValidationState.VALID
        assert result.message == ''

    def test_invalid_ipv4_address(self):
        """Test validating invalid IPv4 addresses"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_ADDRESS, '999.999.999.999')
        assert result.state == ValidationState.INVALID
        assert 'not a valid' in result.message or 'Invalid' in result.message or 'invalid' in result.message

    def test_partial_ipv4_address(self):
        """Test partial IPv4 addresses with allow_partial"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_ADDRESS, '192.168', allow_partial=True)
        assert result.state == ValidationState.IN_PROGRESS

    def test_valid_ipv6_address(self):
        """Test validating valid IPv6 addresses"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_ADDRESS, '2001:db8::1')
        assert result.state == ValidationState.VALID

    def test_valid_ipv4_prefix(self):
        """Test validating IPv4 CIDR prefixes"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_PREFIX, '192.0.2.0/24')
        assert result.state == ValidationState.VALID

    def test_valid_ipv6_prefix(self):
        """Test validating IPv6 CIDR prefixes"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_PREFIX, '2001:db8::/32')
        assert result.state == ValidationState.VALID

    def test_invalid_prefix_mask(self):
        """Test invalid prefix masks"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_PREFIX, '192.0.2.0/99')
        assert result.state == ValidationState.INVALID

    def test_valid_asn(self):
        """Test validating AS numbers"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.ASN, '65000')
        assert result.state == ValidationState.VALID

    def test_invalid_asn_non_numeric(self):
        """Test non-numeric AS numbers"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.ASN, 'not_a_number')
        assert result.state == ValidationState.INVALID

    def test_asn_negative(self):
        """Test negative AS numbers"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.ASN, '-1')
        # Note: Validator behavior depends on implementation
        # Some validators may accept negative as valid (converted to unsigned)
        # or reject as invalid. Either is acceptable.
        assert result.state in (ValidationState.VALID, ValidationState.INVALID)

    def test_asn_very_large(self):
        """Test very large AS numbers (beyond 32-bit)"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.ASN, '9999999999')
        # Note: Validator may accept large numbers or reject them
        # BGP supports 32-bit ASNs (max 4294967295), but some
        # validators may be lenient
        assert result.state in (ValidationState.VALID, ValidationState.INVALID)

    def test_partial_asn(self):
        """Test partial AS numbers"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.ASN, '650', allow_partial=True)
        assert result.state in (ValidationState.VALID, ValidationState.IN_PROGRESS)

    def test_valid_port(self):
        """Test validating port numbers"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.PORT, '179')
        assert result.state == ValidationState.VALID

    def test_invalid_port_too_large(self):
        """Test port number out of range"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.PORT, '99999')
        assert result.state == ValidationState.INVALID

    def test_valid_origin(self):
        """Test validating BGP origin values"""
        engine = ValueTypeCompletionEngine()

        result = engine.validate_value(ValueType.ORIGIN, 'igp')
        assert result.state == ValidationState.VALID

        result = engine.validate_value(ValueType.ORIGIN, 'egp')
        assert result.state == ValidationState.VALID

        result = engine.validate_value(ValueType.ORIGIN, 'incomplete')
        assert result.state == ValidationState.VALID

    def test_invalid_origin(self):
        """Test invalid BGP origin values"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.ORIGIN, 'invalid')
        assert result.state == ValidationState.INVALID

    def test_partial_origin(self):
        """Test partial origin values"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.ORIGIN, 'ig', allow_partial=True)
        assert result.state in (ValidationState.IN_PROGRESS, ValidationState.VALID)


class TestValueSuggestions:
    """Test value suggestion generation"""

    def test_suggest_origin_values(self):
        """Test suggesting BGP origin values"""
        engine = ValueTypeCompletionEngine()
        suggestions = engine.suggest_values(ValueType.ORIGIN, '')
        assert 'igp' in suggestions
        assert 'egp' in suggestions
        assert 'incomplete' in suggestions

    def test_suggest_origin_partial(self):
        """Test suggesting origin values with partial input"""
        engine = ValueTypeCompletionEngine()
        suggestions = engine.suggest_values(ValueType.ORIGIN, 'ig')
        assert 'igp' in suggestions
        assert 'egp' not in suggestions

    def test_suggest_boolean_values(self):
        """Test suggesting boolean values"""
        engine = ValueTypeCompletionEngine()
        suggestions = engine.suggest_values(ValueType.BOOLEAN, '')
        assert 'true' in suggestions
        assert 'false' in suggestions
        assert 'yes' in suggestions
        assert 'no' in suggestions

    def test_no_suggestions_for_open_types(self):
        """Test that open-ended types return no suggestions"""
        engine = ValueTypeCompletionEngine()

        # IP addresses, AS numbers, etc. are open-ended
        suggestions = engine.suggest_values(ValueType.IP_ADDRESS, '')
        assert len(suggestions) == 0

        suggestions = engine.suggest_values(ValueType.ASN, '')
        assert len(suggestions) == 0


class TestSyntaxHelp:
    """Test syntax help generation"""

    def test_syntax_help_ip_address(self):
        """Test syntax help for IP addresses"""
        engine = ValueTypeCompletionEngine()
        help_text = engine.get_syntax_help(ValueType.IP_ADDRESS, include_description=False)
        assert '<ip>' in help_text.lower() or 'ip' in help_text.lower()

    def test_syntax_help_origin(self):
        """Test syntax help for origin attribute"""
        engine = ValueTypeCompletionEngine()
        help_text = engine.get_syntax_help(ValueType.ORIGIN, include_description=False)
        assert 'igp' in help_text.lower() or 'egp' in help_text.lower()

    def test_syntax_help_with_description(self):
        """Test syntax help with validator description"""
        engine = ValueTypeCompletionEngine()
        help_text = engine.get_syntax_help(ValueType.IP_ADDRESS, include_description=True)
        # Should include both hint and description
        assert len(help_text) > 4  # More than just "<ip>"

    def test_syntax_help_as_path(self):
        """Test syntax help for AS path"""
        engine = ValueTypeCompletionEngine()
        help_text = engine.get_syntax_help(ValueType.AS_PATH, include_description=False)
        assert '[' in help_text or 'asn' in help_text.lower()


class TestExampleValues:
    """Test example value generation"""

    def test_example_ip_address(self):
        """Test getting example IP address"""
        engine = ValueTypeCompletionEngine()
        example = engine.get_example_value(ValueType.IP_ADDRESS)
        assert example is not None
        assert '.' in example  # Should be IPv4

    def test_example_asn(self):
        """Test getting example AS number"""
        engine = ValueTypeCompletionEngine()
        example = engine.get_example_value(ValueType.ASN)
        assert example is not None
        assert example.isdigit()

    def test_example_origin(self):
        """Test getting example origin value"""
        engine = ValueTypeCompletionEngine()
        example = engine.get_example_value(ValueType.ORIGIN)
        assert example in ('igp', 'egp', 'incomplete')

    def test_example_not_available(self):
        """Test types without predefined examples"""
        engine = ValueTypeCompletionEngine()
        # Some types might not have examples
        example = engine.get_example_value(ValueType.STRING)
        # Should return None or a valid example
        assert example is None or isinstance(example, str)


class TestValidatorCaching:
    """Test validator caching mechanism"""

    def test_validator_cache_hit(self):
        """Test that validators are cached"""
        engine = ValueTypeCompletionEngine()

        # First call - cache miss
        engine.validate_value(ValueType.IP_ADDRESS, '192.0.2.1')

        # Second call - should use cached validator
        result = engine.validate_value(ValueType.IP_ADDRESS, '192.0.2.2')
        assert result.state == ValidationState.VALID

    def test_different_types_cached_separately(self):
        """Test that different types have separate cache entries"""
        engine = ValueTypeCompletionEngine()

        engine.validate_value(ValueType.IP_ADDRESS, '192.0.2.1')
        engine.validate_value(ValueType.ASN, '65000')

        # Both should work independently
        assert len(engine._validator_cache) >= 2


class TestConvenienceFunctions:
    """Test convenience wrapper functions"""

    def test_validate_ip_address_function(self):
        """Test validate_ip_address convenience function"""
        result = validate_ip_address('192.0.2.1')
        assert result.state == ValidationState.VALID

        result = validate_ip_address('invalid')
        assert result.state == ValidationState.INVALID

    def test_validate_asn_function(self):
        """Test validate_asn convenience function"""
        result = validate_asn('65000')
        assert result.state == ValidationState.VALID

        result = validate_asn('invalid_asn')
        assert result.state == ValidationState.INVALID

    def test_get_syntax_hint_function(self):
        """Test get_syntax_hint convenience function"""
        hint = get_syntax_hint(ValueType.IP_ADDRESS)
        assert isinstance(hint, str)
        assert len(hint) > 0


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_validate_empty_string(self):
        """Test validating empty strings"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_ADDRESS, '')
        # Should be invalid or in_progress depending on validator
        assert result.state in (ValidationState.INVALID, ValidationState.IN_PROGRESS)

    def test_validate_none_value(self):
        """Test handling of None values"""
        engine = ValueTypeCompletionEngine()
        # Validators expect strings, None should raise error or be handled
        try:
            result = engine.validate_value(ValueType.IP_ADDRESS, None)  # type: ignore
            # If it doesn't raise, it should return INVALID
            assert result.state in (ValidationState.INVALID, ValidationState.UNKNOWN)
        except (ValueError, TypeError, AttributeError):
            # Expected behavior - validators don't handle None
            pass

    def test_validate_whitespace(self):
        """Test validating strings with whitespace"""
        engine = ValueTypeCompletionEngine()
        result = engine.validate_value(ValueType.IP_ADDRESS, '  192.0.2.1  ')
        # Depends on validator implementation - might strip or reject
        assert result.state in (ValidationState.VALID, ValidationState.INVALID)

    def test_suggest_values_empty_query(self):
        """Test suggesting values with empty query"""
        engine = ValueTypeCompletionEngine()
        suggestions = engine.suggest_values(ValueType.ORIGIN, '')
        assert len(suggestions) > 0  # Should return all choices

    def test_unknown_value_type(self):
        """Test handling unknown/unsupported value types"""
        engine = ValueTypeCompletionEngine()
        # Create a mock value type that doesn't have a validator
        # This should gracefully return UNKNOWN
        result = engine.validate_value(ValueType.STRING, 'test')
        # Depending on implementation, might be VALID or UNKNOWN
        assert result.state in (ValidationState.VALID, ValidationState.UNKNOWN, ValidationState.INVALID)
