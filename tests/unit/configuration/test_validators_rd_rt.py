"""Test Route Distinguisher and Route Target validators."""

import pytest
from exabgp.configuration.validator import RouteDistinguisherValidator, RouteTargetValidator
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


class TestRouteDistinguisherValidator:
    """Test RouteDistinguisherValidator."""

    def test_type0_2byte_asn(self):
        """Test Type 0: 2-byte ASN + 4-byte number."""
        validator = RouteDistinguisherValidator()
        rd = validator.validate_string('65000:100')
        assert isinstance(rd, RouteDistinguisher)
        assert len(rd) == 8

    def test_type1_ipv4(self):
        """Test Type 1: IPv4 address + 2-byte number."""
        validator = RouteDistinguisherValidator()
        rd = validator.validate_string('192.0.2.1:100')
        assert isinstance(rd, RouteDistinguisher)
        assert len(rd) == 8

    def test_type2_4byte_asn(self):
        """Test Type 2: 4-byte ASN + 2-byte number."""
        validator = RouteDistinguisherValidator()
        rd = validator.validate_string('4200000000:100')
        assert isinstance(rd, RouteDistinguisher)
        assert len(rd) == 8

    def test_invalid_format_no_colon(self):
        """Test validation fails for invalid format (no colon)."""
        validator = RouteDistinguisherValidator()
        with pytest.raises(ValueError, match='not a valid route-distinguisher'):
            validator.validate_string('65000')

    def test_invalid_format_suffix_not_number(self):
        """Test validation fails when suffix is not a number."""
        validator = RouteDistinguisherValidator()
        with pytest.raises(ValueError, match='Suffix must be a number'):
            validator.validate_string('65000:abc')

    def test_invalid_ipv4(self):
        """Test validation fails for invalid IPv4 address."""
        validator = RouteDistinguisherValidator()
        with pytest.raises(ValueError, match='invalid IPv4 address'):
            validator.validate_string('999.0.0.1:100')

    def test_ipv4_suffix_too_large(self):
        """Test validation fails when IPv4 RD suffix exceeds 16 bits."""
        validator = RouteDistinguisherValidator()
        with pytest.raises(ValueError, match='too large for IPv4 RD'):
            validator.validate_string('192.0.2.1:100000')

    def test_to_schema(self):
        """Test JSON Schema generation."""
        validator = RouteDistinguisherValidator()
        schema = validator.to_schema()
        assert schema['type'] == 'string'
        assert 'pattern' in schema
        assert 'examples' in schema

    def test_describe(self):
        """Test human-readable description."""
        validator = RouteDistinguisherValidator()
        desc = validator.describe()
        assert 'route-distinguisher' in desc.lower()


class TestRouteTargetValidator:
    """Test RouteTargetValidator."""

    def test_type0_2byte_asn(self):
        """Test Type 0: 2-byte ASN + 4-byte number."""
        validator = RouteTargetValidator()
        rt = validator.validate_string('65000:100')
        assert isinstance(rt, ExtendedCommunity)

    def test_type0_with_prefix(self):
        """Test Type 0 with 'target:' prefix."""
        validator = RouteTargetValidator()
        rt = validator.validate_string('target:65000:100')
        assert isinstance(rt, ExtendedCommunity)

    def test_type1_ipv4(self):
        """Test Type 1: IPv4 address + 2-byte number."""
        validator = RouteTargetValidator()
        rt = validator.validate_string('192.0.2.1:100')
        assert isinstance(rt, ExtendedCommunity)

    def test_type1_ipv4_with_prefix(self):
        """Test Type 1 IPv4 with 'target:' prefix."""
        validator = RouteTargetValidator()
        rt = validator.validate_string('target:192.0.2.1:100')
        assert isinstance(rt, ExtendedCommunity)

    def test_type2_4byte_asn(self):
        """Test Type 2: 4-byte ASN + 2-byte number."""
        validator = RouteTargetValidator()
        rt = validator.validate_string('4200000000:100')
        assert isinstance(rt, ExtendedCommunity)

    def test_invalid_format_too_many_parts(self):
        """Test validation fails for too many colon-separated parts."""
        validator = RouteTargetValidator()
        with pytest.raises(ValueError, match='not a valid route-target'):
            validator.validate_string('65000:100:200')

    def test_invalid_format_suffix_not_number(self):
        """Test validation fails when suffix is not a number."""
        validator = RouteTargetValidator()
        with pytest.raises(ValueError, match='suffix must be a number'):
            validator.validate_string('65000:abc')

    def test_invalid_ipv4(self):
        """Test validation fails for invalid IPv4 address."""
        validator = RouteTargetValidator()
        with pytest.raises(ValueError, match='invalid IPv4 address'):
            validator.validate_string('999.0.0.1:100')

    def test_ipv4_suffix_too_large(self):
        """Test validation fails when IPv4 RT suffix exceeds 16 bits."""
        validator = RouteTargetValidator()
        with pytest.raises(ValueError, match='too large for IPv4 route-target'):
            validator.validate_string('192.0.2.1:100000')

    def test_to_schema(self):
        """Test JSON Schema generation."""
        validator = RouteTargetValidator()
        schema = validator.to_schema()
        assert schema['type'] == 'string'
        assert 'pattern' in schema
        assert 'examples' in schema

    def test_describe(self):
        """Test human-readable description."""
        validator = RouteTargetValidator()
        desc = validator.describe()
        assert 'route-target' in desc.lower()
