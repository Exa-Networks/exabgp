"""Tests for IntegerOrKeywordValidator and IntValidators factory."""

import pytest

from exabgp.configuration.validator import IntegerOrKeywordValidator, IntValidators


class TestIntegerOrKeywordValidator:
    """Tests for IntegerOrKeywordValidator."""

    def test_parse_integer(self):
        """Test parsing valid integers."""
        v = IntegerOrKeywordValidator()
        assert v.validate_string('0') == 0
        assert v.validate_string('100') == 100
        assert v.validate_string('4095') == 4095

    def test_parse_integer_with_range(self):
        """Test parsing integers with range constraint."""
        v = IntegerOrKeywordValidator().in_range(0, 100)
        assert v.validate_string('0') == 0
        assert v.validate_string('50') == 50
        assert v.validate_string('100') == 100

    def test_parse_integer_below_minimum(self):
        """Test error when integer is below minimum."""
        v = IntegerOrKeywordValidator().in_range(10, 100)
        with pytest.raises(ValueError, match='below minimum'):
            v.validate_string('5')

    def test_parse_integer_above_maximum(self):
        """Test error when integer exceeds maximum."""
        v = IntegerOrKeywordValidator().in_range(0, 100)
        with pytest.raises(ValueError, match='exceeds maximum'):
            v.validate_string('150')

    def test_parse_keyword(self):
        """Test parsing keyword alternatives."""
        v = IntegerOrKeywordValidator(keywords={'disable': False, 'disabled': False})
        assert v.validate_string('disable') is False
        assert v.validate_string('disabled') is False
        assert v.validate_string('DISABLE') is False  # Case insensitive

    def test_parse_keyword_with_range(self):
        """Test parsing keywords with range constraint on integers."""
        v = IntegerOrKeywordValidator(keywords={'disable': False, 'disabled': False}).in_range(0, 4095)
        assert v.validate_string('disable') is False
        assert v.validate_string('100') == 100
        assert v.validate_string('4095') == 4095

    def test_invalid_value_with_keywords(self):
        """Test error message includes keywords when invalid."""
        v = IntegerOrKeywordValidator(keywords={'disable': False}).in_range(0, 100)
        with pytest.raises(ValueError, match="'disable'"):
            v.validate_string('invalid')

    def test_invalid_value_without_keywords(self):
        """Test error message for plain integer validator."""
        v = IntegerOrKeywordValidator().in_range(0, 100)
        with pytest.raises(ValueError, match='not a valid integer'):
            v.validate_string('invalid')

    def test_with_keywords_returns_new_instance(self):
        """Test that with_keywords returns a new validator."""
        v1 = IntegerOrKeywordValidator()
        v2 = v1.with_keywords({'off': 0})
        assert v1.keywords == {}
        assert v2.keywords == {'off': 0}

    def test_in_range_returns_new_instance(self):
        """Test that in_range returns a new validator."""
        v1 = IntegerOrKeywordValidator()
        v2 = v1.in_range(0, 100)
        assert v1.min_value is None
        assert v2.min_value == 0
        assert v2.max_value == 100

    def test_to_schema_with_keywords(self):
        """Test JSON schema generation with keywords."""
        v = IntegerOrKeywordValidator(keywords={'disable': False}).in_range(0, 4095)
        schema = v.to_schema()
        assert 'oneOf' in schema
        assert schema['oneOf'][0]['type'] == 'integer'
        assert schema['oneOf'][0]['minimum'] == 0
        assert schema['oneOf'][0]['maximum'] == 4095
        assert schema['oneOf'][1]['enum'] == ['disable']

    def test_describe_with_keywords(self):
        """Test describe output with keywords."""
        v = IntegerOrKeywordValidator(keywords={'disable': False}).in_range(0, 4095)
        desc = v.describe()
        assert 'integer (0-4095)' in desc
        assert 'disable' in desc


class TestIntValidators:
    """Tests for IntValidators factory class."""

    def test_graceful_restart_valid_integer(self):
        """Test graceful_restart accepts valid integers."""
        v = IntValidators.graceful_restart()
        assert v.validate_string('0') == 0
        assert v.validate_string('100') == 100
        assert v.validate_string('4095') == 4095

    def test_graceful_restart_disable(self):
        """Test graceful_restart accepts disable keyword."""
        v = IntValidators.graceful_restart()
        assert v.validate_string('disable') is False
        assert v.validate_string('disabled') is False
        assert v.validate_string('DISABLE') is False

    def test_graceful_restart_out_of_range(self):
        """Test graceful_restart rejects out of range values."""
        v = IntValidators.graceful_restart()
        with pytest.raises(ValueError, match='exceeds maximum'):
            v.validate_string('4096')

    def test_hold_time(self):
        """Test hold_time validator."""
        v = IntValidators.hold_time()
        assert v.validate_string('0') == 0
        assert v.validate_string('180') == 180
        assert v.validate_string('65535') == 65535
        with pytest.raises(ValueError):
            v.validate_string('65536')

    def test_ttl(self):
        """Test ttl validator."""
        v = IntValidators.ttl()
        assert v.validate_string('0') == 0
        assert v.validate_string('64') == 64
        assert v.validate_string('255') == 255
        with pytest.raises(ValueError):
            v.validate_string('256')

    def test_port(self):
        """Test port validator."""
        v = IntValidators.port()
        assert v.validate_string('1') == 1
        assert v.validate_string('179') == 179
        assert v.validate_string('65535') == 65535
        with pytest.raises(ValueError):
            v.validate_string('0')
        with pytest.raises(ValueError):
            v.validate_string('65536')

    def test_label(self):
        """Test label validator."""
        v = IntValidators.label()
        assert v.validate_string('0') == 0
        assert v.validate_string('1048575') == 1048575
        with pytest.raises(ValueError):
            v.validate_string('1048576')

    def test_asn(self):
        """Test asn validator."""
        v = IntValidators.asn()
        assert v.validate_string('0') == 0
        assert v.validate_string('65535') == 65535
        assert v.validate_string('4294967295') == 4294967295
        with pytest.raises(ValueError):
            v.validate_string('4294967296')

    def test_med(self):
        """Test med validator."""
        v = IntValidators.med()
        assert v.validate_string('0') == 0
        assert v.validate_string('4294967295') == 4294967295
        with pytest.raises(ValueError):
            v.validate_string('4294967296')

    def test_local_preference(self):
        """Test local_preference validator."""
        v = IntValidators.local_preference()
        assert v.validate_string('0') == 0
        assert v.validate_string('100') == 100
        assert v.validate_string('4294967295') == 4294967295

    def test_range(self):
        """Test generic range factory method."""
        v = IntValidators.range(10, 20)
        assert v.validate_string('10') == 10
        assert v.validate_string('15') == 15
        assert v.validate_string('20') == 20
        with pytest.raises(ValueError):
            v.validate_string('9')
        with pytest.raises(ValueError):
            v.validate_string('21')
