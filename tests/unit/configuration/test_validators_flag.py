"""Test FlagValidator for presence-only attributes."""

import pytest
from exabgp.configuration.validator import FlagValidator


class TestFlagValidator:
    """Test FlagValidator."""

    def test_empty_string(self):
        """Test that empty string (presence) returns True."""
        validator = FlagValidator()
        result = validator.validate_string('')
        assert result is True

    def test_true_string(self):
        """Test that 'true' returns True."""
        validator = FlagValidator()
        result = validator.validate_string('true')
        assert result is True

    def test_true_uppercase(self):
        """Test that 'TRUE' returns True."""
        validator = FlagValidator()
        result = validator.validate_string('TRUE')
        assert result is True

    def test_invalid_value(self):
        """Test that non-empty values other than 'true' raise ValueError."""
        validator = FlagValidator()
        with pytest.raises(ValueError, match='not valid for a presence flag'):
            validator.validate_string('false')

    def test_invalid_value_number(self):
        """Test that numbers raise ValueError."""
        validator = FlagValidator()
        with pytest.raises(ValueError, match='not valid for a presence flag'):
            validator.validate_string('1')

    def test_to_schema(self):
        """Test JSON Schema generation."""
        validator = FlagValidator()
        schema = validator.to_schema()
        assert schema['type'] == 'boolean'
        assert schema['const'] is True
        assert 'description' in schema

    def test_describe(self):
        """Test human-readable description."""
        validator = FlagValidator()
        desc = validator.describe()
        assert 'flag' in desc.lower()
        assert 'presence' in desc.lower()
