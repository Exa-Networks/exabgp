"""test_configuration_validator.py

Tests for the validator module and schema integration.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import pytest

from exabgp.configuration.validator import (
    StringValidator,
    IntegerValidator,
    BooleanValidator,
    EnumerationValidator,
    PortValidator,
    IPAddressValidator,
    IPPrefixValidator,
    IPRangeValidator,
    ASNValidator,
    OriginValidator,
    MEDValidator,
    LocalPrefValidator,
    NextHopValidator,
    get_validator,
)
from exabgp.configuration.schema import Leaf, LeafList, Container, ValueType, schema_to_json_schema


class TestStringValidator:
    """Tests for StringValidator."""

    def test_basic_string(self):
        v = StringValidator()
        assert v.validate_string('hello') == 'hello'

    def test_empty_string(self):
        v = StringValidator()
        assert v.validate_string('') == ''

    def test_min_length_valid(self):
        v = StringValidator(min_length=3)
        assert v.validate_string('abc') == 'abc'

    def test_min_length_invalid(self):
        v = StringValidator(min_length=3)
        with pytest.raises(ValueError, match='too short'):
            v.validate_string('ab')

    def test_max_length_valid(self):
        v = StringValidator(max_length=5)
        assert v.validate_string('hello') == 'hello'

    def test_max_length_invalid(self):
        v = StringValidator(max_length=5)
        with pytest.raises(ValueError, match='too long'):
            v.validate_string('toolong')

    def test_with_length(self):
        v = StringValidator().with_length(min_len=2, max_len=5)
        assert v.validate_string('abc') == 'abc'

    def test_pattern_valid(self):
        v = StringValidator(pattern=r'^[a-z]+$')
        assert v.validate_string('hello') == 'hello'

    def test_pattern_invalid(self):
        v = StringValidator(pattern=r'^[a-z]+$')
        with pytest.raises(ValueError, match='does not match'):
            v.validate_string('Hello123')

    def test_to_schema(self):
        v = StringValidator(min_length=1, max_length=10, pattern=r'^[a-z]+$')
        schema = v.to_schema()
        assert schema['type'] == 'string'
        assert schema['minLength'] == 1
        assert schema['maxLength'] == 10
        assert schema['pattern'] == r'^[a-z]+$'


class TestIntegerValidator:
    """Tests for IntegerValidator."""

    def test_basic_integer(self):
        v = IntegerValidator()
        assert v.validate_string('42') == 42

    def test_negative_integer(self):
        v = IntegerValidator()
        assert v.validate_string('-10') == -10

    def test_invalid_integer(self):
        v = IntegerValidator()
        with pytest.raises(ValueError, match='not a valid integer'):
            v.validate_string('abc')

    def test_in_range_valid(self):
        v = IntegerValidator().in_range(0, 100)
        assert v.validate_string('50') == 50

    def test_in_range_at_min(self):
        v = IntegerValidator().in_range(0, 100)
        assert v.validate_string('0') == 0

    def test_in_range_at_max(self):
        v = IntegerValidator().in_range(0, 100)
        assert v.validate_string('100') == 100

    def test_in_range_below_min(self):
        v = IntegerValidator().in_range(0, 100)
        with pytest.raises(ValueError, match='below minimum'):
            v.validate_string('-1')

    def test_in_range_above_max(self):
        v = IntegerValidator().in_range(0, 100)
        with pytest.raises(ValueError, match='exceeds maximum'):
            v.validate_string('150')

    def test_positive(self):
        v = IntegerValidator().positive()
        assert v.validate_string('0') == 0
        assert v.validate_string('100') == 100
        with pytest.raises(ValueError, match='below minimum'):
            v.validate_string('-1')

    def test_to_schema(self):
        v = IntegerValidator().in_range(1, 65535)
        schema = v.to_schema()
        assert schema['type'] == 'integer'
        assert schema['minimum'] == 1
        assert schema['maximum'] == 65535

    def test_describe(self):
        v = IntegerValidator().in_range(0, 100)
        assert '0-100' in v.describe()


class TestBooleanValidator:
    """Tests for BooleanValidator."""

    @pytest.mark.parametrize(
        'value,expected',
        [
            ('true', True),
            ('True', True),
            ('TRUE', True),
            ('enable', True),
            ('enabled', True),
            ('yes', True),
            ('1', True),
            ('false', False),
            ('False', False),
            ('FALSE', False),
            ('disable', False),
            ('disabled', False),
            ('no', False),
            ('0', False),
        ],
    )
    def test_valid_booleans(self, value, expected):
        v = BooleanValidator()
        assert v.validate_string(value) == expected

    def test_invalid_boolean(self):
        v = BooleanValidator()
        with pytest.raises(ValueError, match='not a valid boolean'):
            v.validate_string('maybe')

    def test_with_default_empty(self):
        v = BooleanValidator().with_default(True)
        assert v.validate_string('') is True

    def test_to_schema(self):
        v = BooleanValidator().with_default(False)
        schema = v.to_schema()
        assert schema['type'] == 'boolean'
        assert schema['default'] is False


class TestEnumerationValidator:
    """Tests for EnumerationValidator."""

    def test_valid_choice(self):
        v = EnumerationValidator().with_choices(['igp', 'egp', 'incomplete'])
        assert v.validate_string('igp') == 'igp'

    def test_case_insensitive(self):
        v = EnumerationValidator().with_choices(['igp', 'egp', 'incomplete'])
        assert v.validate_string('IGP') == 'igp'
        assert v.validate_string('Egp') == 'egp'

    def test_invalid_choice(self):
        v = EnumerationValidator().with_choices(['igp', 'egp', 'incomplete'])
        with pytest.raises(ValueError, match='not a valid choice'):
            v.validate_string('invalid')

    def test_empty_choices_allows_any(self):
        v = EnumerationValidator()
        assert v.validate_string('anything') == 'anything'

    def test_to_schema(self):
        v = EnumerationValidator().with_choices(['a', 'b', 'c'])
        schema = v.to_schema()
        assert schema['type'] == 'string'
        assert schema['enum'] == ['a', 'b', 'c']

    def test_describe(self):
        v = EnumerationValidator().with_choices(['a', 'b'])
        assert 'a' in v.describe()
        assert 'b' in v.describe()


class TestPortValidator:
    """Tests for PortValidator."""

    def test_valid_port(self):
        v = PortValidator()
        assert v.validate_string('179') == 179
        assert v.validate_string('1') == 1
        assert v.validate_string('65535') == 65535

    def test_port_below_range(self):
        v = PortValidator()
        with pytest.raises(ValueError):
            v.validate_string('0')

    def test_port_above_range(self):
        v = PortValidator()
        with pytest.raises(ValueError):
            v.validate_string('65536')

    def test_invalid_port_format(self):
        v = PortValidator()
        with pytest.raises(ValueError, match='not a valid port'):
            v.validate_string('abc')

    def test_to_schema(self):
        v = PortValidator()
        schema = v.to_schema()
        assert schema['type'] == 'integer'
        assert schema['minimum'] == 1
        assert schema['maximum'] == 65535


class TestIPAddressValidator:
    """Tests for IPAddressValidator."""

    def test_ipv4(self):
        v = IPAddressValidator()
        ip = v.validate_string('192.0.2.1')
        assert str(ip) == '192.0.2.1'

    def test_ipv6(self):
        v = IPAddressValidator()
        ip = v.validate_string('2001:db8::1')
        # IPv6 string representation may vary
        assert ip is not None

    def test_invalid_ip(self):
        v = IPAddressValidator()
        with pytest.raises(ValueError, match='not a valid IP'):
            v.validate_string('not-an-ip')

    def test_ipv4_only(self):
        v = IPAddressValidator().ipv4_only()
        ip = v.validate_string('192.0.2.1')
        assert str(ip) == '192.0.2.1'

    def test_ipv4_only_rejects_ipv6(self):
        v = IPAddressValidator().ipv4_only()
        with pytest.raises(ValueError, match='IPv6 not allowed'):
            v.validate_string('2001:db8::1')

    def test_ipv6_only(self):
        v = IPAddressValidator().ipv6_only()
        ip = v.validate_string('2001:db8::1')
        assert ip is not None

    def test_ipv6_only_rejects_ipv4(self):
        v = IPAddressValidator().ipv6_only()
        with pytest.raises(ValueError, match='IPv4 not allowed'):
            v.validate_string('192.0.2.1')


class TestIPPrefixValidator:
    """Tests for IPPrefixValidator."""

    def test_ipv4_prefix(self):
        v = IPPrefixValidator()
        prefix = v.validate_string('192.0.2.0/24')
        assert prefix is not None

    def test_ipv6_prefix(self):
        v = IPPrefixValidator()
        prefix = v.validate_string('2001:db8::/32')
        assert prefix is not None

    def test_host_bits_not_zero(self):
        v = IPPrefixValidator()
        with pytest.raises(ValueError, match='Host bits'):
            v.validate_string('192.0.2.1/24')

    def test_invalid_prefix(self):
        v = IPPrefixValidator()
        with pytest.raises(ValueError):
            v.validate_string('not-a-prefix')


class TestIPRangeValidator:
    """Tests for IPRangeValidator."""

    def test_ip_without_prefix(self):
        v = IPRangeValidator()
        result = v.validate_string('192.0.2.1')
        assert result is not None

    def test_ip_with_prefix(self):
        v = IPRangeValidator()
        result = v.validate_string('192.0.2.0/24')
        assert result is not None

    def test_invalid_range(self):
        v = IPRangeValidator()
        with pytest.raises(ValueError):
            v.validate_string('invalid')


class TestASNValidator:
    """Tests for ASNValidator."""

    def test_plain_asn(self):
        v = ASNValidator()
        asn = v.validate_string('65001')
        assert int(asn) == 65001

    def test_dotted_asn(self):
        v = ASNValidator()
        asn = v.validate_string('1.1')
        # 1.1 = (1 << 16) + 1 = 65537
        assert int(asn) == 65537

    def test_invalid_asn(self):
        v = ASNValidator()
        with pytest.raises(ValueError):
            v.validate_string('not-an-asn')

    def test_auto_not_allowed_by_default(self):
        v = ASNValidator()
        with pytest.raises(ValueError):
            v.validate_string('auto')

    def test_with_auto(self):
        v = ASNValidator().with_auto()
        assert v.validate_string('auto') is None

    def test_with_auto_still_accepts_number(self):
        v = ASNValidator().with_auto()
        asn = v.validate_string('65001')
        assert int(asn) == 65001


class TestOriginValidator:
    """Tests for OriginValidator."""

    def test_igp(self):
        v = OriginValidator()
        result = v.validate_string('igp')
        assert result is not None

    def test_egp(self):
        v = OriginValidator()
        result = v.validate_string('egp')
        assert result is not None

    def test_incomplete(self):
        v = OriginValidator()
        result = v.validate_string('incomplete')
        assert result is not None

    def test_case_insensitive(self):
        v = OriginValidator()
        result = v.validate_string('IGP')
        assert result is not None

    def test_invalid_origin(self):
        v = OriginValidator()
        with pytest.raises(ValueError, match='not a valid origin'):
            v.validate_string('invalid')


class TestMEDValidator:
    """Tests for MEDValidator."""

    def test_valid_med(self):
        v = MEDValidator()
        result = v.validate_string('100')
        assert result is not None

    def test_zero_med(self):
        v = MEDValidator()
        result = v.validate_string('0')
        assert result is not None

    def test_max_med(self):
        v = MEDValidator()
        result = v.validate_string('4294967295')
        assert result is not None

    def test_invalid_med(self):
        v = MEDValidator()
        with pytest.raises(ValueError, match='not a valid MED'):
            v.validate_string('abc')


class TestLocalPrefValidator:
    """Tests for LocalPrefValidator."""

    def test_valid_local_pref(self):
        v = LocalPrefValidator()
        result = v.validate_string('100')
        assert result is not None

    def test_invalid_local_pref(self):
        v = LocalPrefValidator()
        with pytest.raises(ValueError, match='not a valid local-preference'):
            v.validate_string('abc')


class TestNextHopValidator:
    """Tests for NextHopValidator."""

    def test_ip_next_hop(self):
        v = NextHopValidator()
        ip, nh = v.validate_string('192.0.2.1')
        assert ip is not None
        assert nh is not None

    def test_self_next_hop(self):
        v = NextHopValidator()
        ip, nh = v.validate_string('self')
        assert ip is not None
        assert nh is not None

    def test_invalid_next_hop(self):
        v = NextHopValidator()
        with pytest.raises(ValueError, match='not a valid next-hop'):
            v.validate_string('invalid')


class TestValidatorChaining:
    """Tests for validator chaining with .then()."""

    def test_then_transform(self):
        v = IntegerValidator().then(lambda x: x * 2)
        assert v.validate_string('5') == 10

    def test_then_multiple(self):
        v = IntegerValidator().then(lambda x: x + 1).then(lambda x: x * 2)
        # (5 + 1) * 2 = 12
        assert v.validate_string('5') == 12


class TestGetValidator:
    """Tests for get_validator() registry function."""

    def test_get_integer_validator(self):
        v = get_validator(ValueType.INTEGER)
        assert isinstance(v, IntegerValidator)

    def test_get_boolean_validator(self):
        v = get_validator(ValueType.BOOLEAN)
        assert isinstance(v, BooleanValidator)

    def test_get_port_validator(self):
        v = get_validator(ValueType.PORT)
        assert isinstance(v, PortValidator)

    def test_get_ip_address_validator(self):
        v = get_validator(ValueType.IP_ADDRESS)
        assert isinstance(v, IPAddressValidator)

    def test_get_origin_validator(self):
        v = get_validator(ValueType.ORIGIN)
        assert isinstance(v, OriginValidator)

    def test_get_label_validator(self):
        v = get_validator(ValueType.LABEL)
        assert isinstance(v, IntegerValidator)
        # Should have range 0-1048575
        assert v.validate_string('0') == 0
        assert v.validate_string('1048575') == 1048575


class TestLeafGetValidator:
    """Tests for Leaf.get_validator() integration."""

    def test_integer_with_range(self):
        leaf = Leaf(
            type=ValueType.INTEGER,
            min_value=0,
            max_value=65535,
        )
        v = leaf.get_validator()
        assert v is not None
        assert v.validate_string('1000') == 1000
        with pytest.raises(ValueError):
            v.validate_string('70000')

    def test_enumeration_with_choices(self):
        leaf = Leaf(
            type=ValueType.ENUMERATION,
            choices=['igp', 'egp', 'incomplete'],
        )
        v = leaf.get_validator()
        assert v is not None
        assert v.validate_string('igp') == 'igp'

    def test_port_no_constraints_needed(self):
        leaf = Leaf(type=ValueType.PORT)
        v = leaf.get_validator()
        assert v is not None
        assert v.validate_string('179') == 179

    def test_explicit_validator_override(self):
        custom = IntegerValidator().in_range(1, 10)
        leaf = Leaf(
            type=ValueType.INTEGER,
            validator=custom,
        )
        v = leaf.get_validator()
        assert v is custom


class TestLeafListGetValidator:
    """Tests for LeafList.get_validator() integration."""

    def test_enumeration_with_choices(self):
        leaf_list = LeafList(
            type=ValueType.ENUMERATION,
            choices=['unicast', 'multicast'],
        )
        v = leaf_list.get_validator()
        assert v is not None
        assert v.validate_string('unicast') == 'unicast'


class TestSchemaToJsonSchema:
    """Tests for schema_to_json_schema() function."""

    def test_leaf_integer(self):
        leaf = Leaf(
            type=ValueType.INTEGER,
            description='Test integer',
            min_value=0,
            max_value=100,
        )
        schema = schema_to_json_schema(leaf)
        assert schema['type'] == 'integer'
        assert schema['minimum'] == 0
        assert schema['maximum'] == 100
        assert schema['description'] == 'Test integer'

    def test_leaf_with_default(self):
        leaf = Leaf(
            type=ValueType.PORT,
            default=179,
        )
        schema = schema_to_json_schema(leaf)
        assert schema['default'] == 179

    def test_leaf_list(self):
        leaf_list = LeafList(
            type=ValueType.STRING,
            description='List of strings',
        )
        schema = schema_to_json_schema(leaf_list)
        assert schema['type'] == 'array'
        assert schema['items']['type'] == 'string'
        assert schema['description'] == 'List of strings'

    def test_container(self):
        container = Container(
            description='Test container',
            children={
                'name': Leaf(type=ValueType.STRING, mandatory=True),
                'value': Leaf(type=ValueType.INTEGER),
            },
        )
        schema = schema_to_json_schema(container)
        assert schema['type'] == 'object'
        assert 'name' in schema['properties']
        assert 'value' in schema['properties']
        assert 'name' in schema['required']
        assert 'value' not in schema['required']
        assert schema['description'] == 'Test container'

    def test_nested_container(self):
        container = Container(
            children={
                'outer': Container(
                    children={
                        'inner': Leaf(type=ValueType.STRING),
                    }
                ),
            }
        )
        schema = schema_to_json_schema(container)
        assert schema['properties']['outer']['type'] == 'object'
        assert 'inner' in schema['properties']['outer']['properties']
