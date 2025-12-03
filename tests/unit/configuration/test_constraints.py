"""Tests for configuration constraints."""

from exabgp.configuration.constraints import (
    CONSTRAINTS,
    HOLD_TIME_MIN,
    HOLD_TIME_MAX,
    ASN_MAX,
    PORT_MIN,
    PORT_MAX,
    NumericConstraint,
    StringConstraint,
)


class TestNumericConstraint:
    """Test numeric constraint validation."""

    def test_valid_value(self):
        """Test that valid values pass validation."""
        constraint = NumericConstraint(0, 100, 'test-value')
        assert constraint.validate(0) is True
        assert constraint.validate(50) is True
        assert constraint.validate(100) is True

    def test_invalid_value_too_low(self):
        """Test that values below minimum fail validation."""
        constraint = NumericConstraint(10, 100, 'test-value')
        assert constraint.validate(9) is False
        assert constraint.validate(0) is False
        assert constraint.validate(-1) is False

    def test_invalid_value_too_high(self):
        """Test that values above maximum fail validation."""
        constraint = NumericConstraint(0, 100, 'test-value')
        assert constraint.validate(101) is False
        assert constraint.validate(1000) is False

    def test_error_message_with_unit(self):
        """Test error message generation with unit."""
        constraint = NumericConstraint(0, 65535, 'hold-time', 'seconds')
        message = constraint.error_message(70000)
        assert 'hold-time' in message
        assert '70000' in message
        assert 'seconds' in message
        assert '0-65535' in message

    def test_error_message_without_unit(self):
        """Test error message generation without unit."""
        constraint = NumericConstraint(0, 4294967295, 'local-as')
        message = constraint.error_message(-1)
        assert 'local-as' in message
        assert '-1' in message
        assert '0-4294967295' in message


class TestStringConstraint:
    """Test string constraint validation."""

    def test_valid_string(self):
        """Test that valid strings pass validation."""
        constraint = StringConstraint(1, 10, 'hostname')
        assert constraint.validate('a') is True
        assert constraint.validate('localhost') is True
        assert constraint.validate('1234567890') is True

    def test_string_too_short(self):
        """Test that strings below minimum length fail."""
        constraint = StringConstraint(3, 10, 'hostname')
        assert constraint.validate('') is False
        assert constraint.validate('ab') is False

    def test_string_too_long(self):
        """Test that strings above maximum length fail."""
        constraint = StringConstraint(1, 5, 'hostname')
        assert constraint.validate('123456') is False
        assert constraint.validate('1234567890') is False

    def test_error_message(self):
        """Test error message generation."""
        constraint = StringConstraint(1, 255, 'hostname')
        message = constraint.error_message('a' * 300)
        assert 'hostname' in message
        assert '300' in message
        assert '1-255' in message


class TestPredefinedConstraints:
    """Test predefined constraint instances."""

    def test_hold_time_constraint(self):
        """Test hold-time constraint."""
        constraint = CONSTRAINTS['hold-time']
        assert constraint.validate(0) is True  # Disabled
        assert constraint.validate(180) is True  # Default
        assert constraint.validate(HOLD_TIME_MAX) is True
        assert constraint.validate(HOLD_TIME_MAX + 1) is False

    def test_asn_constraint(self):
        """Test AS number constraints."""
        local_as = CONSTRAINTS['local-as']
        peer_as = CONSTRAINTS['peer-as']

        # Both should allow full 4-byte ASN range
        assert local_as.validate(0) is True
        assert local_as.validate(65000) is True
        assert local_as.validate(ASN_MAX) is True
        assert local_as.validate(ASN_MAX + 1) is False

        assert peer_as.validate(65000) is True
        assert peer_as.validate(ASN_MAX) is True

    def test_port_constraint(self):
        """Test port constraint."""
        constraint = CONSTRAINTS['port']
        assert constraint.validate(PORT_MIN) is True
        assert constraint.validate(179) is True  # BGP port
        assert constraint.validate(PORT_MAX) is True
        assert constraint.validate(0) is False
        assert constraint.validate(PORT_MAX + 1) is False

    def test_ttl_constraint(self):
        """Test TTL constraint."""
        constraint = CONSTRAINTS['ttl']
        assert constraint.validate(1) is True
        assert constraint.validate(64) is True
        assert constraint.validate(255) is True
        assert constraint.validate(0) is False
        assert constraint.validate(256) is False

    def test_med_constraint(self):
        """Test MED constraint."""
        constraint = CONSTRAINTS['med']
        assert constraint.validate(0) is True
        assert constraint.validate(100) is True
        assert constraint.validate(4294967295) is True
        assert constraint.validate(4294967296) is False

    def test_local_preference_constraint(self):
        """Test local-preference constraint."""
        constraint = CONSTRAINTS['local-preference']
        assert constraint.validate(0) is True
        assert constraint.validate(100) is True
        assert constraint.validate(4294967295) is True
        assert constraint.validate(4294967296) is False

    def test_label_constraint(self):
        """Test MPLS label constraint."""
        constraint = CONSTRAINTS['label']
        assert constraint.validate(0) is True
        assert constraint.validate(16) is True
        assert constraint.validate(1048575) is True  # 20-bit max
        assert constraint.validate(1048576) is False

    def test_rate_limit_constraint(self):
        """Test rate-limit constraint."""
        constraint = CONSTRAINTS['rate-limit']
        assert constraint.validate(0) is True
        assert constraint.validate(100) is True
        assert constraint.validate(10000) is True
        assert constraint.validate(10001) is False

    def test_hostname_constraint(self):
        """Test hostname constraint."""
        constraint = CONSTRAINTS['hostname']
        assert constraint.validate('localhost') is True
        assert constraint.validate('a' * 255) is True
        assert constraint.validate('') is False
        assert constraint.validate('a' * 256) is False

    def test_domain_name_constraint(self):
        """Test domain-name constraint."""
        constraint = CONSTRAINTS['domain-name']
        assert constraint.validate('example.com') is True
        assert constraint.validate('a' * 255) is True
        assert constraint.validate('') is False
        assert constraint.validate('a' * 256) is False


class TestConstantValues:
    """Test that constant values are correct."""

    def test_hold_time_constants(self):
        """Test hold-time min/max values."""
        assert HOLD_TIME_MIN == 0
        assert HOLD_TIME_MAX == 65535

    def test_asn_constants(self):
        """Test ASN constants."""
        assert ASN_MAX == 4294967295  # 4-byte ASN

    def test_port_constants(self):
        """Test port constants."""
        assert PORT_MIN == 1
        assert PORT_MAX == 65535
